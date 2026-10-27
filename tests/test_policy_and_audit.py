"""
Tests for Deterministic Policy Conflict Resolution and Audit Run Isolation.
UC-RT-03 Markdown Optimization
"""

import os
import json
import pytest
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from ml.optimizer.pricing_rules import PricingPolicyEngine
from ml.optimizer.audit_service import OptimizerAuditService


# ==============================================================================
# 1. Deterministic Policy Selection & Conflict Resolution
# ==============================================================================

def test_higher_policy_version_selected_over_lower():
    """When multiple policies match a scope, the one with higher policy_version wins."""
    matches = pd.DataFrame([
        {
            "policy_id": "POL-OLD",
            "policy_version": 1.0,
            "scope_type": "CATEGORY",
            "scope_id": "TestCat",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "minimum_margin_pct": 10.0,
            "minimum_price": 0.0,
            "maximum_discount_pct": 40.0,
            "allowed_steps_list": [0, 10, 20, 30, 40],
            "minimum_days_between_changes": 14,
            "requires_approval": 1,
            "policy_status": "ACTIVE"
        },
        {
            "policy_id": "POL-NEW",
            "policy_version": 2.0,
            "scope_type": "CATEGORY",
            "scope_id": "TestCat",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "minimum_margin_pct": 15.0,
            "minimum_price": 0.0,
            "maximum_discount_pct": 30.0,
            "allowed_steps_list": [0, 10, 20, 30],
            "minimum_days_between_changes": 14,
            "requires_approval": 1,
            "policy_status": "ACTIVE"
        }
    ])
    
    selected = PricingPolicyEngine._select_deterministic_policy(matches, "CATEGORY", "TestCat")
    assert selected["policy_id"] == "POL-NEW"
    assert selected["policy_version"] == 2.0
    assert selected["maximum_discount_pct"] == 30.0


def test_ambiguous_policy_conflict_raises_error():
    """
    When multiple policies have identical version and effective date but conflicting
    rules, the engine must fail closed and raise ValueError.
    """
    conflicting_matches = pd.DataFrame([
        {
            "policy_id": "POL-CONF-A",
            "policy_version": 1.0,
            "scope_type": "STORE",
            "scope_id": "STORE-99",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "minimum_margin_pct": 10.0,
            "minimum_price": 0.0,
            "maximum_discount_pct": 50.0,
            "allowed_steps_list": [0, 10, 20, 30, 40, 50],
            "minimum_days_between_changes": 14,
            "requires_approval": 1,
            "policy_status": "ACTIVE"
        },
        {
            "policy_id": "POL-CONF-B",
            "policy_version": 1.0,
            "scope_type": "STORE",
            "scope_id": "STORE-99",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "minimum_margin_pct": 20.0,  # Conflict: 20% vs 10%
            "minimum_price": 0.0,
            "maximum_discount_pct": 30.0,  # Conflict: 30% vs 50%
            "allowed_steps_list": [0, 10, 20, 30],
            "minimum_days_between_changes": 14,
            "requires_approval": 1,
            "policy_status": "ACTIVE"
        }
    ])
    
    with pytest.raises(ValueError, match="Ambiguous policy conflict at STORE=STORE-99"):
        PricingPolicyEngine._select_deterministic_policy(conflicting_matches, "STORE", "STORE-99")


def test_identical_tied_policies_resolve_safely():
    """When tied policies have identical constraints, resolution succeeds without error."""
    identical_matches = pd.DataFrame([
        {
            "policy_id": "POL-ID-1",
            "policy_version": 1.0,
            "scope_type": "CHAIN",
            "scope_id": "ALL",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "minimum_margin_pct": 10.0,
            "minimum_price": 0.0,
            "maximum_discount_pct": 50.0,
            "allowed_steps_list": [0, 10, 20, 30, 40, 50],
            "minimum_days_between_changes": 14,
            "requires_approval": 1,
            "policy_status": "ACTIVE"
        },
        {
            "policy_id": "POL-ID-2",
            "policy_version": 1.0,
            "scope_type": "CHAIN",
            "scope_id": "ALL",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "minimum_margin_pct": 10.0,
            "minimum_price": 0.0,
            "maximum_discount_pct": 50.0,
            "allowed_steps_list": [0, 10, 20, 30, 40, 50],
            "minimum_days_between_changes": 14,
            "requires_approval": 1,
            "policy_status": "ACTIVE"
        }
    ])
    
    selected = PricingPolicyEngine._select_deterministic_policy(identical_matches, "CHAIN", "ALL")
    assert selected["maximum_discount_pct"] == 50.0


# ==============================================================================
# 2. Audit Trail Isolation & Overwrite Protection
# ==============================================================================

def test_audit_service_isolates_consecutive_runs(tmp_path):
    """Multiple runs write to distinct directories; run 1 evidence is never overwritten."""
    audit_svc = OptimizerAuditService(base_reports_dir=str(tmp_path))
    
    # Run 1
    run1 = audit_svc.initialize_run(run_tag="pilot")
    records1 = [{"item": 1, "recommendation_status": "RECOMMENDED"}]
    df1 = pd.DataFrame([{"item": 1, "price": 100}])
    report1 = "# Run 1 Report"
    
    paths1 = audit_svc.save_run_artifacts(run1, records1, df1, report1)
    
    # Run 2
    run2 = audit_svc.initialize_run(run_tag="pilot")
    records2 = [{"item": 2, "recommendation_status": "NO_FEASIBLE_CANDIDATE"}]
    df2 = pd.DataFrame([{"item": 2, "price": 200}])
    report2 = "# Run 2 Report"
    
    paths2 = audit_svc.save_run_artifacts(run2, records2, df2, report2)
    
    # Check isolation
    assert run1["run_id"] != run2["run_id"]
    assert run1["run_dir"] != run2["run_dir"]
    assert os.path.exists(paths1["audit_json"])
    assert os.path.exists(paths2["audit_json"])
    
    # Verify Run 1 artifacts were preserved exactly
    with open(paths1["audit_json"], "r", encoding="utf-8") as f:
        saved1 = json.load(f)
    assert saved1 == records1
    
    with open(paths2["audit_json"], "r", encoding="utf-8") as f:
        saved2 = json.load(f)
    assert saved2 == records2
