"""
Tests for Deterministic Markdown Optimizer and Policy Enforcement.
UC-RT-03 Markdown Optimization
"""

import os
import pytest
from ml.optimizer.pricing_rules import PricingPolicyEngine
from ml.optimizer.profit_calculator import MarkdownProfitCalculator

def test_policy_resolution_hierarchy():
    engine = PricingPolicyEngine()
    # Test SKU level override (SKU-0071 has POL-009 max discount 30%)
    sku_pol = engine.resolve_policy(sku_id="SKU-0071", store_id="STORE-01", category="Jacket", date_str="2025-04-01")
    assert sku_pol["policy_id"] == "POL-009"
    assert sku_pol["maximum_discount_pct"] == 30
    
    # Test Category level
    cat_pol = engine.resolve_policy(sku_id="SKU-9999", store_id="STORE-01", category="Jeans", date_str="2025-04-01")
    assert cat_pol["policy_id"] == "POL-004"
    assert cat_pol["maximum_discount_pct"] == 50

def test_margin_and_discount_constraints():
    engine = PricingPolicyEngine()
    policy = {
        "allowed_steps_list": [0, 10, 20, 30],
        "maximum_discount_pct": 30.0,
        "minimum_price": 500.0,
        "minimum_margin_pct": 15.0
    }
    
    # 1. Reject disallowed step
    res1 = engine.validate_candidate(candidate_price=800, discount_pct=25, regular_price=1000, unit_cost=400, policy=policy)
    assert not res1["is_feasible"]
    assert "not in allowed markdown steps" in res1["rejection_reason"]
    
    # 2. Reject margin violation
    res2 = engine.validate_candidate(candidate_price=700, discount_pct=30, regular_price=1000, unit_cost=650, policy=policy)
    assert not res2["is_feasible"]
    assert "below minimum required" in res2["rejection_reason"]
    
    # 3. Accept valid candidate
    res3 = engine.validate_candidate(candidate_price=800, discount_pct=20, regular_price=1000, unit_cost=400, policy=policy)
    assert res3["is_feasible"]

def test_inventory_capped_profit_calculation():
    calc = MarkdownProfitCalculator()
    fin = calc.calculate_candidate_financials(
        candidate_price=1000.0,
        unit_cost=500.0,
        predicted_daily_demand=10.0,
        opening_stock=25.0, # 7-day demand is 70, but opening stock is only 25
        stockout_prob=0.8,
        planning_horizon_days=7
    )
    assert fin["expected_fulfilled_units_7d"] == 25.0
    assert fin["expected_terminal_stock_7d"] == 0.0
    assert fin["stockout_risk_penalty"] > 0
