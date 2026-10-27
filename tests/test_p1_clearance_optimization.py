"""
Tests for P1 Seasonal Inventory Clearance Optimization.
UC-RT-03 Markdown Optimization

Validates:
1. Zero stock safe handling (sell_through_pct is None, zero fulfilled units).
2. Economic terminal holding cost formula (terminal_stock * unit_cost * alpha).
3. Objective mode switching: MAX_PROFIT vs CLEAR_INVENTORY.
4. Objective-driven ranking inversion when leftover holding cost outweighs marginal profit.
5. Deterministic policy guardrails strictly prevent ineligible candidates from winning in CLEAR_INVENTORY mode.
6. End-to-end optimizer integration and audit trail logging.
"""

import os
import pytest
import pandas as pd
from ml.optimizer.profit_calculator import MarkdownProfitCalculator
from ml.optimizer.optimizer import DeterministicMarkdownOptimizer

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def sample_row():
    test_csv = os.path.join(REPO_ROOT, "data/processed/test.csv")
    df = pd.read_csv(test_csv, nrows=1)
    return df.iloc[0].copy()


def test_zero_opening_stock_sell_through_safe():
    """Verify opening_stock=0 avoids ZeroDivisionError and safely returns None."""
    calc = MarkdownProfitCalculator()
    fin = calc.calculate_candidate_financials(
        candidate_price=50.0,
        unit_cost=20.0,
        predicted_daily_demand=5.0,
        opening_stock=0.0,
        stockout_prob=0.0,
        planning_horizon_days=7,
        objective_mode="CLEAR_INVENTORY",
        clearance_holding_cost_rate=0.15,
    )
    assert fin["expected_fulfilled_units"] == 0.0
    assert fin["expected_terminal_stock"] == 0.0
    assert fin["sell_through_pct"] is None
    assert fin["expected_revenue"] == 0.0
    assert fin["residual_holding_cost"] == 0.0
    assert fin["clearance_adjusted_profit"] == 0.0
    assert "Seasonal Clearance" in fin["explanation"]


def test_full_sell_through():
    """Verify 100% sell-through when unconstrained demand exceeds stock."""
    calc = MarkdownProfitCalculator()
    fin = calc.calculate_candidate_financials(
        candidate_price=100.0,
        unit_cost=40.0,
        predicted_daily_demand=10.0, # 7d demand = 70
        opening_stock=50.0,
        stockout_prob=0.8,
        planning_horizon_days=7,
        objective_mode="CLEAR_INVENTORY",
        clearance_holding_cost_rate=0.15,
    )
    assert fin["expected_fulfilled_units"] == 50.0
    assert fin["expected_terminal_stock"] == 0.0
    assert fin["sell_through_pct"] == 100.0
    assert fin["residual_holding_cost"] == 0.0
    assert fin["clearance_adjusted_profit"] == fin["risk_adjusted_profit"]


def test_partial_sell_through_and_residual_holding_cost():
    """Verify residual holding cost = terminal_stock * unit_cost * alpha."""
    calc = MarkdownProfitCalculator()
    opening_stock = 100.0
    daily_demand = 5.0 # 7d demand = 35.0
    unit_cost = 20.0
    alpha = 0.15

    fin = calc.calculate_candidate_financials(
        candidate_price=50.0,
        unit_cost=unit_cost,
        predicted_daily_demand=daily_demand,
        opening_stock=opening_stock,
        stockout_prob=0.0,
        planning_horizon_days=7,
        objective_mode="CLEAR_INVENTORY",
        clearance_holding_cost_rate=alpha,
    )
    assert fin["expected_fulfilled_units"] == 35.0
    assert fin["expected_terminal_stock"] == 65.0
    assert fin["sell_through_pct"] == 35.0
    
    expected_residual_cost = round(65.0 * 20.0 * 0.15, 2) # 195.0
    assert fin["residual_holding_cost"] == expected_residual_cost
    assert fin["clearance_adjusted_profit"] == round(fin["risk_adjusted_profit"] - expected_residual_cost, 2)
    assert fin["ranking_score"] == fin["clearance_adjusted_profit"]


def test_baseline_parity_under_max_profit():
    """In MAX_PROFIT mode, ranking_score must exactly match P0 risk_adjusted_profit."""
    calc = MarkdownProfitCalculator()
    fin = calc.calculate_candidate_financials(
        candidate_price=60.0,
        unit_cost=25.0,
        predicted_daily_demand=4.0,
        opening_stock=100.0,
        stockout_prob=0.1,
        planning_horizon_days=7,
        objective_mode="MAX_PROFIT",
    )
    assert fin["ranking_score"] == fin["risk_adjusted_profit"]
    assert "Margin Maximization" in fin["explanation"]


def test_objective_flips_ranking_in_clearance_mode():
    """
    Demonstrate that high leftover holding cost flips the winner:
    Candidate Low-Discount (Price $80):
      Demand = 2/day -> 14 units sold. Gross margin $50/unit -> gross profit $700.
      Leftover = 86 units * unit_cost $30 * 0.15 = $387 holding penalty.
      Risk adjusted profit: ~$680. Clearance profit: $680 - $387 = $293.
    Candidate High-Discount (Price $55):
      Demand = 10/day -> 70 units sold. Gross margin $25/unit -> gross profit $1750.
      Leftover = 30 units * unit_cost $30 * 0.15 = $135 holding penalty.
      Clearance profit: ~$1600.
    In CLEAR_INVENTORY mode, High-Discount easily beats Low-Discount due to terminal clearance.
    """
    calc = MarkdownProfitCalculator()
    opening_stock = 100.0
    unit_cost = 30.0

    low_disc = calc.calculate_candidate_financials(
        candidate_price=80.0,
        unit_cost=unit_cost,
        predicted_daily_demand=2.0,
        opening_stock=opening_stock,
        stockout_prob=0.01,
        planning_horizon_days=7,
        objective_mode="CLEAR_INVENTORY",
        clearance_holding_cost_rate=0.15,
    )

    high_disc = calc.calculate_candidate_financials(
        candidate_price=55.0,
        unit_cost=unit_cost,
        predicted_daily_demand=10.0,
        opening_stock=opening_stock,
        stockout_prob=0.15,
        planning_horizon_days=7,
        objective_mode="CLEAR_INVENTORY",
        clearance_holding_cost_rate=0.15,
    )

    assert low_disc["sell_through_pct"] == 14.0
    assert high_disc["sell_through_pct"] == 70.0
    assert high_disc["ranking_score"] > low_disc["ranking_score"]


def test_policy_feasibility_strictly_enforced_in_clearance_mode(sample_row):
    """Policy violation cannot win even in CLEAR_INVENTORY mode."""
    optimizer = DeterministicMarkdownOptimizer()
    row = sample_row.copy()

    # Run optimizer in CLEAR_INVENTORY mode
    result = optimizer.optimize_sku_day(
        row=row,
        objective_mode="CLEAR_INVENTORY",
        clearance_holding_cost_rate=0.15,
    )

    if result["recommendation_status"] == "PENDING_APPROVAL":
        # Any chosen recommendation must have strictly passed policy
        rec = next((c for c in result["candidate_evaluations"] if c["is_recommended"]), None)
        assert rec is not None
        assert rec["is_feasible"] is True

    # Blocked candidates can never be recommended
    for cand in result["candidate_evaluations"]:
        if not cand["is_feasible"]:
            assert cand["is_recommended"] is False


def test_end_to_end_optimizer_clearance_audit(sample_row):
    """Verify objective mode and clearance metrics are captured in audit record."""
    optimizer = DeterministicMarkdownOptimizer()
    row = sample_row.copy()

    result = optimizer.optimize_sku_day(
        row=row,
        objective_mode="CLEAR_INVENTORY",
        clearance_holding_cost_rate=0.15,
    )

    assert result["objective_mode"] == "CLEAR_INVENTORY"
    assert result["clearance_holding_cost_rate"] == 0.15
    assert "sell_through_pct" in result
    assert "clearance_adjusted_profit" in result
    assert "recommendation_explanation" in result
    assert len(result["candidate_evaluations"]) > 0
