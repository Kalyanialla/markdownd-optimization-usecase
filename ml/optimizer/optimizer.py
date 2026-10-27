"""
UC-RT-03: Deterministic Markdown Optimizer.

Integrates:
- Model 1: Baseline / Demand forecast estimates
- Model 2: Price-response counterfactual estimates
- Model 3: 7-day stockout risk alerts
- Pricing Policies: Feasibility filtering (margins, steps, cadence, min prices)
- Governance: Human-in-the-loop approval workflow and auditable decision logging
"""

import os
import sys
import json
import logging
import joblib
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from ml.optimizer.pricing_rules import PricingPolicyEngine, PriceHistoryService
from ml.optimizer.profit_calculator import MarkdownProfitCalculator
from ml.optimizer.model_service import OptimizerModelService
from ml.optimizer.audit_service import OptimizerAuditService
from ml.common.feature_contract import STORE_OPENING_FEATURES_66, CATEGORICAL_FEATURES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
ARTIFACTS_DIR = os.path.join(REPO_ROOT, "ml/artifacts")
REPORTS_DIR = os.path.join(REPO_ROOT, "data/reports/optimizer")

class DeterministicMarkdownOptimizer:
    def __init__(self):
        self.policy_engine = PricingPolicyEngine()
        self.profit_calc = MarkdownProfitCalculator()
        self.price_history_service = PriceHistoryService()
        
        logger.info("Initializing model service...")
        self.model_service = OptimizerModelService(artifacts_dir=ARTIFACTS_DIR)
        
        # Maintain direct references for backwards compatibility with tests and callers
        self.m1_model = self.model_service.m1_model
        self.m1_encoder = self.model_service.m1_encoder
        self.m2_model = self.model_service.m2_model
        self.m2_encoder = self.model_service.m2_encoder
        self.m3_model = self.model_service.m3_model
        self.m3_encoder = self.model_service.m3_encoder
        
        self.features_66 = self.model_service.features_66
        self.cat_cols = self.model_service.cat_cols

    def optimize_sku_day(
        self,
        row: pd.Series,
        human_approver: Optional[str] = None,
        planning_horizon_days: int = 7,
        objective_mode: str = "MAX_PROFIT",
        clearance_holding_cost_rate: float = 0.15
    ) -> Dict[str, Any]:
        """
        Runs candidate enumeration, constraint filtering, demand prediction,
        expected profit ranking, and governance audit trail.
        
        Note: Generating a recommendation always leaves approval_status as
        PENDING_APPROVAL (or None if no feasible candidate). Recommendations are
        never auto-approved merely because a username is supplied.
        """
        sku_id = str(row["sku_id"])
        store_id = str(row["store_id"])
        category = str(row["category"])
        date_str = str(row["date"])
        reg_p = float(row["regular_price"])
        unit_c = float(row["unit_cost"])
        opening_stock = float(row["opening_stock_units"])
        comp_p = float(row["competitor_price"])
        
        # 1. Resolve Policy
        policy = self.policy_engine.resolve_policy(sku_id, store_id, category, date_str)
        allowed_steps = policy.get("allowed_steps_list")
        if not allowed_steps or not isinstance(allowed_steps, (list, tuple)):
            candidate_discounts = []
        else:
            candidate_discounts = sorted(list(set([float(s) for s in allowed_steps if s >= 0])))
        
        # 2. Get verified price-change cadence
        days_since_last_change = self.price_history_service.get_days_since_last_change(sku_id, store_id, date_str)
        has_history = (days_since_last_change is not None)
        
        # 3. Model 1 baseline demand reference & Model 3 baseline stockout risk
        baseline_demand_m1 = self.model_service.predict_baseline_demand(row)
        baseline_stockout_prob = self.model_service.predict_stockout_risk(row[self.features_66].to_frame().T)
        
        # 4. Evaluate each candidate discount step defined by policy
        evaluated_candidates = []
        for disc in candidate_discounts:
            p_price = round(reg_p * (1.0 - disc / 100.0), 2)
            
            # Policy validation with cadence enforcement
            val_res = self.policy_engine.validate_candidate(
                candidate_price=p_price,
                discount_pct=disc,
                regular_price=reg_p,
                unit_cost=unit_c,
                policy=policy,
                days_since_last_change=days_since_last_change,
                has_history=has_history
            )
            
            # Build fresh, independent candidate feature row
            cand_feat_df = self.model_service.build_candidate_features(
                baseline_row=row,
                candidate_price=p_price,
                discount_pct=disc,
                regular_price=reg_p,
                unit_cost=unit_c,
                competitor_price=comp_p
            )
            
            # Predict candidate demand (Model 2: observational scenario estimate)
            try:
                pred_demand = self.model_service.predict_candidate_demand(cand_feat_df)
            except Exception as e:
                logger.warning(f"Model 2 failure on discount {disc}%: {e}")
                pred_demand = None
            
            # Predict candidate-specific stockout risk (Model 3)
            try:
                cand_stockout_prob = self.model_service.predict_stockout_risk(cand_feat_df)
            except Exception as e:
                logger.warning(f"Model 3 failure on discount {disc}%: {e}")
                cand_stockout_prob = None
            
            # Calculate financial metrics using candidate-specific stockout probability
            if pred_demand is not None and cand_stockout_prob is not None:
                fin = self.profit_calc.calculate_candidate_financials(
                    candidate_price=p_price,
                    unit_cost=unit_c,
                    predicted_daily_demand=pred_demand,
                    opening_stock=opening_stock,
                    stockout_prob=cand_stockout_prob,
                    planning_horizon_days=planning_horizon_days,
                    objective_mode=objective_mode,
                    clearance_holding_cost_rate=clearance_holding_cost_rate
                )
            else:
                fin = None

            evaluated_candidates.append({
                "discount_pct": disc,
                "candidate_price": p_price,
                "is_feasible": val_res["is_feasible"],
                "rejection_reason": val_res["rejection_reason"],
                "candidate_stockout_probability": cand_stockout_prob,
                "predicted_candidate_demand": pred_demand,
                "expected_fulfilled_units": fin["expected_fulfilled_units"] if fin else None,
                "expected_terminal_stock": fin["expected_terminal_stock"] if fin else None,
                "sell_through_pct": fin["sell_through_pct"] if fin else None,
                "residual_holding_cost": fin["residual_holding_cost"] if fin else None,
                "clearance_adjusted_profit": fin["clearance_adjusted_profit"] if fin else None,
                "ranking_score": fin["ranking_score"] if fin else None,
                "explanation": fin["explanation"] if fin else None,
                "financials": fin
            })
            
        # 5. Rank feasible candidates by ranking score (risk-adjusted profit or clearance-adjusted profit).
        # Candidates must be both policy-feasible and have successfully evaluated financials.
        policy_feasible_candidates = [c for c in evaluated_candidates if c["is_feasible"]]
        feasible_candidates = [
            c for c in policy_feasible_candidates
            if c.get("financials") is not None and c["financials"].get("ranking_score") is not None
        ]
        
        mode_clean = str(objective_mode).strip().upper() if objective_mode else "MAX_PROFIT"
        
        best_choice = None
        if not policy_feasible_candidates:
            # Policy blocked all candidates (e.g. cadence or margin floor)
            recommendation_status = "NO_FEASIBLE_CANDIDATE"
            recommended_disc = None
            recommended_price = None
            expected_daily_sales = 0.0
            expected_7d_profit = 0.0
            risk_adjusted_7d_profit = 0.0
            clearance_adjusted_profit = 0.0
            expected_terminal_stock = opening_stock
            expected_fulfilled_units = 0.0
            sell_through_pct = 0.0 if opening_stock > 0 else None
            recommended_stockout_prob = baseline_stockout_prob
            recommendation_explanation = "No markdown candidate satisfied binding pricing policies (minimum gross margin floor or cadence cooldown)."
            approval_status = None
        elif not feasible_candidates:
            # Policy had eligible candidates, but model inference or financial evaluation failed
            recommendation_status = "MODEL_INFERENCE_FAILED"
            recommended_disc = None
            recommended_price = None
            expected_daily_sales = 0.0
            expected_7d_profit = 0.0
            risk_adjusted_7d_profit = 0.0
            clearance_adjusted_profit = 0.0
            expected_terminal_stock = opening_stock
            expected_fulfilled_units = 0.0
            sell_through_pct = 0.0 if opening_stock > 0 else None
            recommended_stockout_prob = baseline_stockout_prob
            recommendation_explanation = "Model inference or financial evaluation failed across all candidates."
            approval_status = None
        else:
            best_choice = max(feasible_candidates, key=lambda c: c["financials"]["ranking_score"])
            recommendation_status = "RECOMMENDED"
            recommended_disc = best_choice["discount_pct"]
            recommended_price = best_choice["candidate_price"]
            expected_daily_sales = best_choice["financials"]["predicted_daily_demand"]
            expected_7d_profit = best_choice["financials"]["expected_gross_profit_7d"]
            risk_adjusted_7d_profit = best_choice["financials"]["risk_adjusted_profit_7d"]
            clearance_adjusted_profit = best_choice["financials"]["clearance_adjusted_profit"]
            expected_terminal_stock = best_choice["financials"]["expected_terminal_stock_7d"]
            expected_fulfilled_units = best_choice["financials"]["expected_fulfilled_units_7d"]
            sell_through_pct = best_choice["financials"]["sell_through_pct"]
            recommended_stockout_prob = best_choice["candidate_stockout_probability"]
            recommendation_explanation = best_choice["financials"]["explanation"]
            approval_status = "PENDING_APPROVAL"

        for c in evaluated_candidates:
            c["is_recommended"] = bool(best_choice is not None and c["discount_pct"] == best_choice["discount_pct"])
            
        # 6. Audit Record
        audit_record = {
            "date": date_str,
            "store_id": store_id,
            "sku_id": sku_id,
            "category": category,
            "policy_id_applied": policy.get("policy_id"),
            "regular_price": reg_p,
            "unit_cost": unit_c,
            "opening_stock_units": opening_stock,
            "baseline_demand_forecast_m1": baseline_demand_m1,
            "baseline_stockout_probability": baseline_stockout_prob,
            "seven_day_stockout_probability": recommended_stockout_prob,
            "stockout_risk_level": "HIGH" if recommended_stockout_prob >= 0.5 else "LOW",
            "model2_is_observational_scenario": True,
            "recommendation_status": recommendation_status,
            "objective_mode": mode_clean,
            "clearance_holding_cost_rate": float(clearance_holding_cost_rate),
            "recommended_discount_pct": recommended_disc,
            "recommended_price": recommended_price,
            "expected_daily_sales": expected_daily_sales,
            "expected_7d_profit": expected_7d_profit,
            "risk_adjusted_7d_profit": risk_adjusted_7d_profit,
            "clearance_adjusted_profit": clearance_adjusted_profit,
            "expected_terminal_stock_7d": expected_terminal_stock,
            "expected_fulfilled_units_7d": expected_fulfilled_units,
            "sell_through_pct": sell_through_pct,
            "recommendation_explanation": recommendation_explanation,
            "days_since_last_change": days_since_last_change,
            "last_price_change_date": self.price_history_service.get_last_price_change_date(sku_id, store_id, date_str).strftime("%Y-%m-%d") if self.price_history_service.get_last_price_change_date(sku_id, store_id, date_str) is not None else None,
            "has_price_history": has_history,
            "approval_required": bool(policy.get("requires_approval", 1)),
            "approval_status": approval_status,
            "approver_id": None,
            "approved_by": None,
            "approved_at": None,
            "candidate_evaluations": evaluated_candidates
        }
        return audit_record


def apply_human_approval(
    audit_record: Dict[str, Any],
    approver_id: str,
    decision: str = "APPROVED",
    notes: str = ""
) -> Dict[str, Any]:
    """
    Applies an explicit human approval or rejection action to a pending recommendation.
    Rejects actions on NO_FEASIBLE_CANDIDATE records.
    
    Note: Enterprise IAM / SSO integration is a pending system dependency.
    The caller-provided approver_id is recorded for audit logging.
    """
    if audit_record.get("recommendation_status") == "NO_FEASIBLE_CANDIDATE":
        raise ValueError("Cannot approve or reject: no valid recommendation was produced (NO_FEASIBLE_CANDIDATE).")
    if decision not in ["APPROVED", "REJECTED"]:
        raise ValueError(f"Invalid approval decision '{decision}'; must be 'APPROVED' or 'REJECTED'")
    if not approver_id or not str(approver_id).strip():
        raise ValueError("approver_id is required to record a human approval action")
        
    rec = audit_record.copy()
    rec["approval_status"] = f"{decision}_BY_HUMAN"
    rec["approver_id"] = str(approver_id).strip()
    rec["approved_by"] = str(approver_id).strip()
    rec["approved_at"] = pd.Timestamp.now().isoformat()
    rec["approval_notes"] = str(notes)
    return rec


def run_pilot_optimization():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    logger.info("Initializing Deterministic Markdown Optimizer...")
    optimizer = DeterministicMarkdownOptimizer()
    
    # Load sample from test dataset representing different categories & stock situations
    test_csv = os.path.join(REPO_ROOT, "data/processed/test.csv")
    test_df = pd.read_csv(test_csv)
    
    # Select 10 diverse representative items
    pilot_sample = test_df.drop_duplicates(subset=["store_id", "category"]).head(10).copy()
    
    logger.info(f"Running optimization on {len(pilot_sample)} pilot SKU-store combinations...")
    audit_logs = []
    summary_rows = []
    
    for idx, row in pilot_sample.iterrows():
        rec = optimizer.optimize_sku_day(row, human_approver="Retail_Category_Lead_S9")
        audit_logs.append(rec)
        summary_rows.append({
            "Date": rec["date"],
            "Store": rec["store_id"],
            "SKU": rec["sku_id"],
            "Category": rec["category"],
            "Regular_Price": f"₹{rec['regular_price']}",
            "Unit_Cost": f"₹{rec['unit_cost']}",
            "Opening_Stock": rec["opening_stock_units"],
            "Stockout_Risk": f"{rec['seven_day_stockout_probability'] * 100:.1f}% ({rec['stockout_risk_level']})",
            "Policy": rec["policy_id_applied"],
            "Rec_Discount": f"{rec['recommended_discount_pct']}%",
            "Rec_Price": f"₹{rec['recommended_price']}",
            "Exp_7D_Sales": rec["expected_daily_sales"] * 7,
            "Exp_7D_Profit": f"₹{rec['expected_7d_profit']:.2f}",
            "Terminal_Stock": rec["expected_terminal_stock_7d"],
            "Status": rec["approval_status"]
        })
        
    summary_df = pd.DataFrame(summary_rows)
    
    # Initialize isolated run directory via audit service
    audit_service = OptimizerAuditService(base_reports_dir=REPORTS_DIR)
    run_info = audit_service.initialize_run(run_tag="pilot")
    
    # Generate Markdown Report
    report_md = f"""# Deterministic Markdown Optimizer: Pilot Execution Report

- **Run ID**: `{run_info['run_id']}`
- **Run Timestamp**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Scope**: Pilot optimization across representative test-period store-SKU inventory states
- **Constraints Applied**: Pricing policy hierarchy, minimum margin threshold, allowed steps, stockout risk bounds
- **Approval Workflow**: Explicit Human-in-the-Loop approval gate enforced

---

## 1. Pilot Recommendations Summary Table

| Date | Store | SKU | Category | Reg Price | Cost | Opening Stock | 7D Stockout Risk | Policy Applied | Recommended Markdown | Rec Price | Expected 7D Profit | Terminal Stock | Approval Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for idx, r in summary_df.iterrows():
        report_md += f"| {r['Date']} | {r['Store']} | {r['SKU']} | {r['Category']} | {r['Regular_Price']} | {r['Unit_Cost']} | {r['Opening_Stock']} | {r['Stockout_Risk']} | {r['Policy']} | **{r['Rec_Discount']}** | **{r['Rec_Price']}** | {r['Exp_7D_Profit']} | {r['Terminal_Stock']} | `{r['Status']}` |\n"

    report_md += """
---

## 2. Decision Logic and Policy Precedence Verified

1. **Policy Hierarchy**: SKU-specific overrides (e.g. `POL-009` through `POL-013` with 30% discount cap) override category and chain rules.
2. **Margin Constraint**: Candidates violating `minimum_margin_pct` (e.g., 10% to 15%) are rejected deterministically before profit ranking.
3. **Inventory & Stockout Guardrails**: Items with candidate-specific stockout risk (>60%) receive an inventory risk penalty, discouraging aggressive markdowns on scarce stock.
4. **Audit Trail**: Every evaluated candidate, rejected step, and financial calculation is logged in an isolated, versioned audit run directory.
"""
    # Persist artifacts into isolated run directory via audit service
    saved_paths = audit_service.save_run_artifacts(
        run_info=run_info,
        audit_records=audit_logs,
        summary_df=summary_df,
        report_markdown=report_md,
        extra_metadata={"model2_scenario_notes": "observational demand estimates"}
    )
    
    logger.info(f"Optimizer pilot execution finished. Saved to isolated run directory: {run_info['run_dir']}")
    return run_info, saved_paths

if __name__ == "__main__":
    run_pilot_optimization()
