"""
Tests for Financial Scoring Transparency and Edge-Case Handling.
UC-RT-03 Markdown Optimization
"""

import pytest
from ml.optimizer.profit_calculator import MarkdownProfitCalculator


@pytest.fixture(scope="module")
def calc():
    return MarkdownProfitCalculator()


def test_zero_inventory_edge_case(calc):
    """When opening stock is zero, fulfilled units, revenue, and profit must all be zero."""
    fin = calc.calculate_candidate_financials(
        candidate_price=1000.0,
        unit_cost=500.0,
        predicted_daily_demand=10.0,
        opening_stock=0.0,
        stockout_prob=0.8,
        planning_horizon_days=7
    )
    assert fin["expected_fulfilled_units_7d"] == 0.0
    assert fin["expected_revenue_7d"] == 0.0
    assert fin["expected_gross_profit_7d"] == 0.0
    assert fin["risk_adjusted_profit_7d"] == 0.0
    assert fin["expected_terminal_stock_7d"] == 0.0


def test_very_low_inventory_cap(calc):
    """When demand is high (e.g. 10/day -> 70 total) and stock is 1, fulfilled units must cap at 1."""
    fin = calc.calculate_candidate_financials(
        candidate_price=800.0,
        unit_cost=400.0,
        predicted_daily_demand=10.0,
        opening_stock=1.0,
        stockout_prob=0.9,
        planning_horizon_days=7
    )
    assert fin["expected_fulfilled_units_7d"] == 1.0
    assert fin["expected_terminal_stock_7d"] == 0.0
    assert fin["expected_revenue_7d"] == 800.0
    assert fin["expected_gross_profit_7d"] == 400.0


def test_zero_margin_edge_case(calc):
    """When candidate price equals unit cost, gross profit must be zero."""
    fin = calc.calculate_candidate_financials(
        candidate_price=500.0,
        unit_cost=500.0,
        predicted_daily_demand=5.0,
        opening_stock=50.0,
        stockout_prob=0.2,
        planning_horizon_days=7
    )
    assert fin["unit_margin"] == 0.0
    assert fin["expected_gross_profit_7d"] == 0.0
    assert fin["risk_adjusted_profit_7d"] == 0.0


def test_transparency_fields_and_notes_present(calc):
    """Financial calculations must return all individual components and explicit assumption notes."""
    fin = calc.calculate_candidate_financials(
        candidate_price=900.0,
        unit_cost=450.0,
        predicted_daily_demand=3.0,
        opening_stock=30.0,
        stockout_prob=0.7,
        planning_horizon_days=7
    )
    assert "unit_margin" in fin
    assert "predicted_daily_demand" in fin
    assert "effective_demand_7d_approximation" in fin
    assert "expected_fulfilled_units_7d" in fin
    assert "expected_revenue_7d" in fin
    assert "expected_gross_profit_7d" in fin
    assert "risk_adjusted_profit_7d" in fin
    assert "expected_terminal_stock_7d" in fin
    assert "stockout_probability" in fin
    assert "stockout_risk_penalty" in fin
    assert "horizon_approximation_note" in fin
    assert "stockout_penalty_heuristic_note" in fin
    assert fin["effective_demand_7d_approximation"] == 21.0


def test_negative_margin_penalty_cannot_be_negative(calc):
    """When candidate price is below cost and stockout risk is high, penalty must remain 0.0 and not become negative."""
    fin = calc.calculate_candidate_financials(
        candidate_price=300.0,
        unit_cost=500.0,
        predicted_daily_demand=5.0,
        opening_stock=20.0,
        stockout_prob=0.9,
        planning_horizon_days=7
    )
    assert fin["unit_margin"] == -200.0
    assert fin["stockout_risk_penalty"] == 0.0
    assert fin["expected_gross_profit_7d"] == -4000.0
    assert fin["risk_adjusted_profit_7d"] == -4000.0
