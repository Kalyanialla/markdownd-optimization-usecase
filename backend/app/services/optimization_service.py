"""
Optimization orchestration service.
Integrates ML models, pricing rules, and financial calculator to execute
and persist markdown optimization runs and candidates.
"""

import os
import uuid
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.exceptions import NotFoundException, ValidationException, ConflictException
from backend.app.db.models.optimization import OptimizationRun, OptimizationCandidate
from backend.app.db.models.governance import AuditEvent
from backend.app.db.models.user import User
from backend.app.schemas.optimization import (
    OptimizationRunCreateRequest,
    OptimizationRunResponse,
    OptimizationRunDetailResponse,
    CandidateResponse,
)
from backend.app.services.product_service import ProductService

# ML Optimizer Imports
from ml.optimizer.optimizer import DeterministicMarkdownOptimizer
from ml.common.feature_contract import STORE_OPENING_FEATURES_66

_optimizer_lock = threading.Lock()
_optimizer_instance: Optional[DeterministicMarkdownOptimizer] = None
_canonical_df: Optional[pd.DataFrame] = None


def get_optimizer() -> DeterministicMarkdownOptimizer:
    global _optimizer_instance
    with _optimizer_lock:
        if _optimizer_instance is None:
            _optimizer_instance = DeterministicMarkdownOptimizer()
        return _optimizer_instance


def get_canonical_df() -> Optional[pd.DataFrame]:
    global _canonical_df
    with _optimizer_lock:
        if _canonical_df is None:
            path = settings.DATA_ROOT / "processed" / "markdown_features_canonical.csv"
            if path.exists():
                try:
                    # Load indexed by sku_id and store_id
                    _canonical_df = pd.read_csv(path)
                except Exception:
                    _canonical_df = None
        return _canonical_df


class OptimizationService:
    @staticmethod
    def get_baseline_row(sku_id: str, store_id: str) -> pd.Series:
        """
        Locates or constructs the feature row for the SKU and store.
        """
        product = ProductService.get_product_by_sku(sku_id, store_id=store_id)

        df = get_canonical_df()
        if df is not None:
            match = df[(df["sku_id"].str.upper() == sku_id.upper()) & (df["store_id"].str.upper() == store_id.upper())]
            if not match.empty:
                row = match.sort_values(by="date", ascending=False).iloc[0].copy()
                hist_stock = float(row.get("opening_stock_units", 0))
                row["_inventory_source"] = "HISTORICAL_PROCESSED_DATASET"
                row["_inventory_effective_date"] = str(row.get("date"))
                row["_catalog_stock_reference"] = float(product.current_stock) if product else None
                # If historical row has 0 stock but current product catalog has available stock, sync it transparently
                if hist_stock <= 0 and product and product.current_stock > 0:
                    row["opening_stock_units"] = float(product.current_stock)
                    row["_inventory_source"] = "CATALOG_ACTIVE_INVENTORY_SYNCED"
                return row

            # Match on SKU alone across any store
            sku_match = df[df["sku_id"].str.upper() == sku_id.upper()]
            if not sku_match.empty:
                row = sku_match.sort_values(by="date", ascending=False).iloc[0].copy()
                row["store_id"] = store_id
                hist_stock = float(row.get("opening_stock_units", 0))
                row["_inventory_source"] = "CROSS_STORE_DATASET_FALLBACK"
                row["_inventory_effective_date"] = str(row.get("date"))
                row["_catalog_stock_reference"] = float(product.current_stock) if product else None
                if hist_stock <= 0 and product and product.current_stock > 0:
                    row["opening_stock_units"] = float(product.current_stock)
                    row["_inventory_source"] = "CATALOG_ACTIVE_INVENTORY_SYNCED"
                return row

        # Synthesize from product catalog
        synthetic_dict: Dict[str, Any] = {
            "sku_id": product.sku_id,
            "store_id": store_id,
            "category": product.category,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "regular_price": product.regular_price,
            "unit_cost": product.unit_cost,
            "opening_stock_units": float(max(10, product.current_stock or 50)),
            "competitor_price": round(product.regular_price * 0.95, 2),
            "selling_price": product.regular_price,
            "discount_pct": 0.0,
            "markdown_flag": 0,
            "seasonality_sin": 0.5,
            "seasonality_cos": 0.86,
            "month": datetime.now(timezone.utc).month,
            "day_of_week": datetime.now(timezone.utc).weekday(),
            "_inventory_source": "CATALOG_SYNTHETIC_FALLBACK",
            "_inventory_effective_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "_catalog_stock_reference": float(product.current_stock) if product else None,
        }

        # Fill remaining required 66 features with 0.0 defaults if not present
        for feat in STORE_OPENING_FEATURES_66:
            if feat not in synthetic_dict:
                synthetic_dict[feat] = 0.0

        return pd.Series(synthetic_dict)

    @staticmethod
    def execute_run(
        db: Session,
        user: User,
        request: OptimizationRunCreateRequest
    ) -> OptimizationRunDetailResponse:
        now = datetime.now(timezone.utc)
        sku_clean = request.sku_id.strip().upper()
        store_clean = request.store_id.strip().upper()

        # Idempotency check
        if request.idempotency_key:
            existing = db.scalar(
                select(OptimizationRun).where(OptimizationRun.idempotency_key == request.idempotency_key)
            )
            if existing:
                return OptimizationService.get_run_detail(db, existing.id)

        # Validate product existence
        product = ProductService.get_product_by_sku(sku_clean, store_id=store_clean)

        optimizer = get_optimizer()
        baseline_row = OptimizationService.get_baseline_row(sku_clean, store_clean)

        # Execute optimization
        obj_mode = getattr(request, "objective_mode", "MAX_PROFIT") or "MAX_PROFIT"
        holding_rate = getattr(request, "clearance_holding_cost_rate", 0.15)
        if holding_rate is None:
            holding_rate = 0.15

        try:
            result = optimizer.optimize_sku_day(
                row=baseline_row,
                planning_horizon_days=request.planning_horizon_days,
                objective_mode=obj_mode,
                clearance_holding_cost_rate=holding_rate
            )
        except Exception as e:
            # Create failed run record
            failed_run = OptimizationRun(
                requested_by=user.id,
                store_id=store_clean,
                sku=sku_clean,
                status="FAILED",
                input_snapshot={
                    "sku_id": sku_clean,
                    "store_id": store_clean,
                    "planning_horizon_days": request.planning_horizon_days,
                    "objective_mode": obj_mode,
                    "clearance_holding_cost_rate": holding_rate,
                },
                model_versions={
                    "model1": "XGBoost Baseline Demand",
                    "model2": "XGBoost Price Response",
                    "model3": "XGBoost Stockout Risk",
                },
                policy_snapshot={},
                started_at=now,
                completed_at=datetime.now(timezone.utc),
                error_code=str(e),
                idempotency_key=request.idempotency_key,
            )
            db.add(failed_run)
            db.commit()
            raise ValidationException(f"Optimization engine failure: {e}")

        # Snapshots
        policy_info = result.get("policy", {})
        input_snapshot = {
            "sku_id": sku_clean,
            "product_name": product.product_name,
            "store_id": store_clean,
            "category": product.category,
            "regular_price": float(baseline_row["regular_price"]),
            "unit_cost": float(baseline_row["unit_cost"]),
            "opening_stock_units": float(baseline_row["opening_stock_units"]),
            "competitor_price": float(baseline_row["competitor_price"]),
            "planning_horizon_days": request.planning_horizon_days,
            "objective_mode": obj_mode,
            "clearance_holding_cost_rate": holding_rate,
            "inventory_source": str(baseline_row.get("_inventory_source", "HISTORICAL_DATASET")),
            "inventory_effective_date": str(baseline_row.get("_inventory_effective_date", baseline_row.get("date", "N/A"))),
            "catalog_stock_reference": float(baseline_row.get("_catalog_stock_reference")) if baseline_row.get("_catalog_stock_reference") is not None else None,
        }
        model_versions = {
            "model1_baseline_demand": "certified-artifact-v1",
            "model2_price_sensitivity": "certified-artifact-v1",
            "model3_stockout_risk": "certified-artifact-v1",
            "feature_contract": "canonical_66_features",
        }

        policy_info = result.get("policy") or {
            "policy_id_applied": result.get("policy_id_applied"),
            "approval_required": result.get("approval_required"),
            "days_since_last_change": result.get("days_since_last_change"),
            "last_price_change_date": result.get("last_price_change_date"),
        }

        db_run = OptimizationRun(
            requested_by=user.id,
            store_id=store_clean,
            sku=sku_clean,
            status="COMPLETED",
            input_snapshot=input_snapshot,
            model_versions=model_versions,
            policy_snapshot=policy_info if isinstance(policy_info, dict) else {"details": str(policy_info)},
            started_at=now,
            completed_at=datetime.now(timezone.utc),
            idempotency_key=request.idempotency_key,
        )
        db.add(db_run)
        db.flush()

        best_discount = result.get("recommended_discount_pct")

        candidate_objs: List[OptimizationCandidate] = []
        candidates_raw = result.get("candidate_evaluations") or result.get("evaluated_candidates") or []
        for cand in candidates_raw:
            disc = float(cand["discount_pct"])
            p_price = float(cand["candidate_price"])
            is_feas = bool(cand.get("is_feasible", False))
            fin = cand.get("financials") or {}

            db_cand = OptimizationCandidate(
                run_id=db_run.id,
                discount_pct=disc,
                candidate_price=p_price,
                predicted_demand=float(cand.get("predicted_candidate_demand")) if cand.get("predicted_candidate_demand") is not None else None,
                stockout_risk=float(cand.get("candidate_stockout_probability")) if cand.get("candidate_stockout_probability") is not None else None,
                unit_margin=round(p_price - product.unit_cost, 2),
                estimated_revenue=float(fin.get("expected_revenue_7d")) if fin.get("expected_revenue_7d") is not None else None,
                estimated_gross_profit=float(fin.get("expected_gross_profit_7d")) if fin.get("expected_gross_profit_7d") is not None else None,
                risk_adjusted_profit=float(fin.get("risk_adjusted_profit_7d")) if fin.get("risk_adjusted_profit_7d") is not None else None,
                policy_passed=is_feas,
                rejection_reasons=str(cand.get("rejection_reason")) if cand.get("rejection_reason") else None,
                score_details={
                    "is_recommended": (best_discount is not None and disc == float(best_discount)),
                    "expected_terminal_stock": fin.get("expected_terminal_stock_7d"),
                    "expected_fulfilled_units": fin.get("expected_fulfilled_units_7d"),
                    "sell_through_pct": fin.get("sell_through_pct"),
                    "residual_holding_cost": fin.get("residual_holding_cost"),
                    "clearance_adjusted_profit": fin.get("clearance_adjusted_profit"),
                    "ranking_score": fin.get("ranking_score"),
                    "stockout_penalty": fin.get("stockout_penalty"),
                    "objective_mode": obj_mode,
                    "explanation": fin.get("explanation"),
                },
            )
            db.add(db_cand)
            candidate_objs.append(db_cand)

        # Audit event
        audit = AuditEvent(
            actor_id=user.id,
            event_type="OPTIMIZATION_RUN_CREATED",
            entity_type="OptimizationRun",
            entity_id=str(db_run.id),
            details_json={
                "sku": sku_clean,
                "store_id": store_clean,
                "objective_mode": obj_mode,
                "recommended_discount_pct": best_discount,
                "recommended_price": result.get("recommended_price"),
                "recommended_sell_through_pct": result.get("sell_through_pct"),
                "recommended_clearance_adjusted_profit": result.get("clearance_adjusted_profit"),
                "candidates_evaluated": len(candidate_objs),
            },
        )
        db.add(audit)
        db.commit()
        db.refresh(db_run)

        return OptimizationService.get_run_detail(db, db_run.id)

    @staticmethod
    def get_run_detail(db: Session, run_id: uuid.UUID) -> OptimizationRunDetailResponse:
        run = db.scalar(select(OptimizationRun).where(OptimizationRun.id == run_id))
        if not run:
            raise NotFoundException(f"Optimization run '{run_id}' not found.")

        candidates = db.scalars(
            select(OptimizationCandidate)
            .where(OptimizationCandidate.run_id == run_id)
            .order_by(OptimizationCandidate.discount_pct.asc())
        ).all()

        cand_responses = [
            CandidateResponse(
                id=c.id,
                run_id=c.run_id,
                discount_pct=c.discount_pct,
                candidate_price=c.candidate_price,
                predicted_demand=c.predicted_demand,
                stockout_risk=c.stockout_risk,
                unit_margin=c.unit_margin,
                estimated_revenue=c.estimated_revenue,
                estimated_gross_profit=c.estimated_gross_profit,
                risk_adjusted_profit=c.risk_adjusted_profit,
                expected_fulfilled_units=c.score_details.get("expected_fulfilled_units") if c.score_details else None,
                expected_terminal_stock=c.score_details.get("expected_terminal_stock") if c.score_details else None,
                sell_through_pct=c.score_details.get("sell_through_pct") if c.score_details else None,
                residual_holding_cost=c.score_details.get("residual_holding_cost") if c.score_details else None,
                clearance_adjusted_profit=c.score_details.get("clearance_adjusted_profit") if c.score_details else None,
                ranking_score=c.score_details.get("ranking_score") if c.score_details else None,
                explanation=c.score_details.get("explanation") if c.score_details else None,
                policy_passed=c.policy_passed,
                rejection_reasons=c.rejection_reasons,
                is_recommended=bool(c.score_details.get("is_recommended")) if c.score_details else False,
                score_details=c.score_details,
            )
            for c in candidates
        ]

        # Recommended discount/price
        rec_cand = next((c for c in cand_responses if c.is_recommended), None)

        snap = run.input_snapshot or {}
        return OptimizationRunDetailResponse(
            id=run.id,
            sku=run.sku,
            store_id=run.store_id,
            status=run.status,
            requested_by=run.requested_by,
            started_at=run.started_at,
            completed_at=run.completed_at,
            error_code=run.error_code,
            input_snapshot=run.input_snapshot,
            model_versions=run.model_versions,
            policy_snapshot=run.policy_snapshot,
            candidates_count=len(cand_responses),
            objective_mode=snap.get("objective_mode", "MAX_PROFIT"),
            recommended_discount_pct=rec_cand.discount_pct if rec_cand else None,
            recommended_price=rec_cand.candidate_price if rec_cand else None,
            recommended_sell_through_pct=rec_cand.sell_through_pct if rec_cand else None,
            recommended_explanation=rec_cand.explanation if rec_cand else None,
            candidates=cand_responses,
        )

    @staticmethod
    def list_runs(
        db: Session,
        sku: Optional[str] = None,
        store_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[OptimizationRunResponse]:
        query = select(OptimizationRun).order_by(desc(OptimizationRun.started_at)).limit(limit)
        if sku:
            query = query.where(OptimizationRun.sku.ilike(f"%{sku.strip()}%"))
        if store_id and store_id != "ALL":
            query = query.where(OptimizationRun.store_id == store_id.strip())

        runs = db.scalars(query).all()
        return [
            OptimizationRunResponse(
                id=r.id,
                sku=r.sku,
                store_id=r.store_id,
                status=r.status,
                requested_by=r.requested_by,
                started_at=r.started_at,
                completed_at=r.completed_at,
                error_code=r.error_code,
                input_snapshot=r.input_snapshot,
                model_versions=r.model_versions,
                policy_snapshot=r.policy_snapshot,
                candidates_count=len(r.candidates),
                objective_mode=(r.input_snapshot or {}).get("objective_mode", "MAX_PROFIT"),
            )
            for r in runs
        ]
