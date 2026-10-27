"""
Tests for Optimizer stockout-penalty threshold sensitivity and policy-conflict resolution.
UC-RT-03 Markdown Optimization
"""

import os
import pytest
import sys
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from ml.optimizer.pricing_rules import PricingPolicyEngine
from ml.optimizer.profit_calculator import MarkdownProfitCalculator


POLICY = {
    "allowed_steps_list": [0, 10, 20, 30, 40, 50],
    "maximum_discount_pct": 50.0,
    "minimum_price": 0.0,
    "minimum_margin_pct": 10.0,
    "minimum_days_between_changes": 14,
}


# ---- Policy hierarchy tests ------------------------------------------------

def test_sku_policy_overrides_category():
    engine = PricingPolicyEngine()
    pol = engine.resolve_policy("SKU-0071", "STORE-01", "Jacket", "2025-04-01")
    assert pol["policy_id"] == "POL-009", f"Expected POL-009, got {pol['policy_id']}"
    assert int(pol["maximum_discount_pct"]) == 30


def test_category_policy_applied_when_no_sku_match():
    engine = PricingPolicyEngine()
    pol = engine.resolve_policy("SKU-XXXX", "STORE-01", "Jeans", "2025-04-01")
    assert pol["policy_id"] == "POL-004"
    assert int(pol["maximum_discount_pct"]) == 50


def test_store_policy_applied_store04():
    """STORE-04 has its own policy (POL-008, max discount 50) with no SKU/category override."""
    engine = PricingPolicyEngine()
    pol = engine.resolve_policy("SKU-XXXX", "STORE-04", "TShirt", "2025-04-01")
    # TShirt has POL-003 (category) and STORE-04 has POL-008 (store).
    # Store > Category, so expect POL-008.
    assert pol["policy_id"] == "POL-008", f"Expected POL-008 (store beats category), got {pol['policy_id']}"


# ---- Profit calculator threshold-sensitivity tests -------------------------

def test_no_penalty_below_60pct_threshold():
    calc = MarkdownProfitCalculator()
    fin = calc.calculate_candidate_financials(1000, 500, 5.0, 40.0, stockout_prob=0.59)
    assert fin["stockout_risk_penalty"] == 0.0, "No penalty expected below 60% threshold"


def test_penalty_applied_above_60pct_threshold():
    calc = MarkdownProfitCalculator()
    fin = calc.calculate_candidate_financials(1000, 500, 5.0, 40.0, stockout_prob=0.80)
    assert fin["stockout_risk_penalty"] > 0.0, "Penalty expected above 60% threshold"


def test_penalty_does_not_make_profit_negative_for_positive_margin():
    """Penalty must not turn a profitable action into a negative-profit decision
    for moderate discount scenarios — it adjusts, not reverses."""
    calc = MarkdownProfitCalculator()
    fin = calc.calculate_candidate_financials(1000, 500, 5.0, 100.0, stockout_prob=0.99)
    # Even at extreme stockout risk, gross profit (500*100=50000) is far larger than penalty
    assert fin["risk_adjusted_profit_7d"] > 0, "Risk-adjusted profit should remain positive here"


def test_threshold_sensitivity_at_exactly_60pct():
    """Boundary: stockout_prob == 0.60 should yield zero penalty."""
    calc = MarkdownProfitCalculator()
    fin = calc.calculate_candidate_financials(1000, 500, 5.0, 35.0, stockout_prob=0.60)
    assert fin["stockout_risk_penalty"] == 0.0


def test_inventory_cap_limits_fulfilled_units():
    calc = MarkdownProfitCalculator()
    fin = calc.calculate_candidate_financials(
        candidate_price=1000, unit_cost=400,
        predicted_daily_demand=20.0, opening_stock=10.0,  # 7d demand 140 > 10 stock
        stockout_prob=0.1,
    )
    assert fin["expected_fulfilled_units_7d"] == pytest.approx(10.0), \
        "Fulfilled units must be capped at opening_stock"
    assert fin["expected_terminal_stock_7d"] == pytest.approx(0.0)
    assert fin["expected_gross_profit_7d"] == pytest.approx(10 * (1000 - 400))


def test_infeasible_discount_above_max():
    engine = PricingPolicyEngine()
    res = engine.validate_candidate(700, 30.0, 1000, 400, POLICY)
    # max allowed is 50%, so 30% should be feasible
    assert res["is_feasible"] is True
    res2 = engine.validate_candidate(400, 60.0, 1000, 400, POLICY)
    assert res2["is_feasible"] is False
    assert "exceed" in res2["rejection_reason"].lower() or "not in" in res2["rejection_reason"].lower()


def test_infeasible_price_violates_minimum_margin():
    """Candidates that breach minimum gross margin percentage must be rejected."""
    engine = PricingPolicyEngine()
    # regular 1000, cost 950. A 10% discount gives price 900 < cost 950 (-5.5% margin, below min 10%)
    res = engine.validate_candidate(900, 10.0, 1000, 950, POLICY)
    assert res["is_feasible"] is False
    assert "margin" in res["rejection_reason"].lower()


def test_human_approval_gate_unattended_is_pending():
    """Unattended optimization runs must remain PENDING_APPROVAL and cannot autonomously deploy."""
    from ml.optimizer.optimizer import DeterministicMarkdownOptimizer
    optimizer = DeterministicMarkdownOptimizer()
    
    test_csv = os.path.join(REPO_ROOT, "data/processed/test.csv")
    test_df = pd.read_csv(test_csv, nrows=1)
    row = test_df.iloc[0]
    
    # Run with human_approver=None
    audit_rec = optimizer.optimize_sku_day(row, human_approver=None)
    assert audit_rec["approval_status"] == "PENDING_APPROVAL", \
        f"Expected PENDING_APPROVAL, got {audit_rec['approval_status']}"
    assert audit_rec["approver_id"] is None


def test_monotonic_penalty_increase_with_stockout_risk():
    """Penalty must increase monotonically as stockout probability exceeds 0.60."""
    calc = MarkdownProfitCalculator()
    p_low = calc.calculate_candidate_financials(800, 400, 2.0, 20.0, stockout_prob=0.65)["stockout_risk_penalty"]
    p_mid = calc.calculate_candidate_financials(800, 400, 2.0, 20.0, stockout_prob=0.75)["stockout_risk_penalty"]
    p_high = calc.calculate_candidate_financials(800, 400, 2.0, 20.0, stockout_prob=0.90)["stockout_risk_penalty"]
    assert 0.0 < p_low < p_mid < p_high, "Risk penalty must strictly increase as stockout probability rises above 0.60"


# ---- Planning horizon tests (7, 14, 30 days) --------------------------------

def test_planning_horizon_scales_demand_and_profit():
    calc = MarkdownProfitCalculator()
    f7 = calc.calculate_candidate_financials(1000, 600, predicted_daily_demand=10.0, opening_stock=1000.0, stockout_prob=0.2, planning_horizon_days=7)
    f14 = calc.calculate_candidate_financials(1000, 600, predicted_daily_demand=10.0, opening_stock=1000.0, stockout_prob=0.2, planning_horizon_days=14)
    f30 = calc.calculate_candidate_financials(1000, 600, predicted_daily_demand=10.0, opening_stock=1000.0, stockout_prob=0.2, planning_horizon_days=30)

    assert f7["expected_fulfilled_units_7d"] == 70.0
    assert f14["expected_fulfilled_units_7d"] == 140.0
    assert f30["expected_fulfilled_units_7d"] == 300.0

    assert f7["expected_gross_profit_7d"] == 70.0 * 400.0
    assert f14["expected_gross_profit_7d"] == 140.0 * 400.0
    assert f30["expected_gross_profit_7d"] == 300.0 * 400.0


# ---- Cadence validation tests (5d, 13d, 14d, missing history) ---------------

def test_cadence_validation_5_days_blocked():
    engine = PricingPolicyEngine()
    res = engine.validate_candidate(900, 10.0, 1000, 500, POLICY, days_since_last_change=5, has_history=True)
    assert res["is_feasible"] is False
    assert "5 days" in res["rejection_reason"]


def test_cadence_validation_13_days_blocked():
    engine = PricingPolicyEngine()
    res = engine.validate_candidate(900, 10.0, 1000, 500, POLICY, days_since_last_change=13, has_history=True)
    assert res["is_feasible"] is False
    assert "13 days" in res["rejection_reason"]


def test_cadence_validation_14_days_eligible():
    engine = PricingPolicyEngine()
    res = engine.validate_candidate(900, 10.0, 1000, 500, POLICY, days_since_last_change=14, has_history=True)
    assert res["is_feasible"] is True
    assert res["rejection_reason"] is None


def test_cadence_validation_missing_history_blocks_markdown_permits_base():
    engine = PricingPolicyEngine()
    # 0% discount (base price) is always allowed regardless of history
    res_base = engine.validate_candidate(1000, 0.0, 1000, 500, POLICY, days_since_last_change=None, has_history=False)
    assert res_base["is_feasible"] is True

    # Any discount > 0% is blocked when history is missing
    res_disc = engine.validate_candidate(900, 10.0, 1000, 500, POLICY, days_since_last_change=None, has_history=False)
    assert res_disc["is_feasible"] is False
    assert "Missing or unverified price-change history" in res_disc["rejection_reason"]

