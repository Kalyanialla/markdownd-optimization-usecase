"""
Regression tests for Optimizer Safety, Cadence Enforcement, Policy Validation,
and Decoupled Human Approval.
UC-RT-03 Markdown Optimization
"""

import os
import pytest
import pandas as pd
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from ml.optimizer.pricing_rules import (
    PricingPolicyEngine,
    PriceHistoryService,
    validate_policy_configuration
)
from ml.optimizer.optimizer import (
    DeterministicMarkdownOptimizer,
    apply_human_approval
)


@pytest.fixture(scope="module")
def optimizer():
    return DeterministicMarkdownOptimizer()


@pytest.fixture(scope="module")
def engine():
    return PricingPolicyEngine()


@pytest.fixture(scope="module")
def price_history():
    return PriceHistoryService()


@pytest.fixture(scope="module")
def sample_row():
    test_csv = os.path.join(REPO_ROOT, "data/processed/test.csv")
    df = pd.read_csv(test_csv, nrows=1)
    return df.iloc[0].copy()


# ==============================================================================
# 1. Infeasible Candidate Handling (No Unsafe Fallback)
# ==============================================================================

def test_no_feasible_candidate_returns_explicit_result(optimizer, sample_row):
    """When all candidates are infeasible, return NO_FEASIBLE_CANDIDATE and None for prices."""
    # Create an impossible row where unit_cost exceeds regular_price (e.g., negative margin on all steps)
    row = sample_row.copy()
    row["unit_cost"] = row["regular_price"] * 1.5  # Cost 150% of regular price
    
    rec = optimizer.optimize_sku_day(row)
    assert rec["recommendation_status"] == "NO_FEASIBLE_CANDIDATE"
    assert rec["recommended_discount_pct"] is None
    assert rec["recommended_price"] is None
    assert rec["approval_status"] is None  # No valid recommendation to approve
    assert rec["expected_daily_sales"] == 0.0
    assert rec["expected_7d_profit"] == 0.0


# ==============================================================================
# 2. Price History & Cadence Constraint Tests
# ==============================================================================

def test_missing_price_history_blocks_markdown(engine):
    """When price history is missing, candidate markdowns (>0%) must be rejected."""
    policy = {
        "allowed_steps_list": [0, 10, 20],
        "maximum_discount_pct": 30.0,
        "minimum_price": 100.0,
        "minimum_margin_pct": 10.0,
        "minimum_days_between_changes": 14
    }
    # 0% discount permitted without history
    res_zero = engine.validate_candidate(1000, 0.0, 1000, 500, policy, has_history=False)
    assert res_zero["is_feasible"] is True
    
    # Markdown discount blocked when history is missing
    res_disc = engine.validate_candidate(900, 10.0, 1000, 500, policy, has_history=False)
    assert res_disc["is_feasible"] is False
    assert "Missing or unverified price-change history" in res_disc["rejection_reason"]


def test_markdown_attempted_before_interval_rejected(engine):
    """A markdown requested before minimum_days_between_changes must be rejected."""
    policy = {
        "allowed_steps_list": [0, 10, 20],
        "maximum_discount_pct": 30.0,
        "minimum_price": 100.0,
        "minimum_margin_pct": 10.0,
        "minimum_days_between_changes": 14
    }
    # Only 5 days since last change (minimum 14 required)
    res = engine.validate_candidate(
        candidate_price=900, discount_pct=10.0, regular_price=1000, unit_cost=500,
        policy=policy, days_since_last_change=5, has_history=True
    )
    assert res["is_feasible"] is False
    assert "Only 5 days since last change" in res["rejection_reason"]


def test_markdown_permitted_after_interval(engine):
    """A markdown requested after minimum_days_between_changes is accepted."""
    policy = {
        "allowed_steps_list": [0, 10, 20],
        "maximum_discount_pct": 30.0,
        "minimum_price": 100.0,
        "minimum_margin_pct": 10.0,
        "minimum_days_between_changes": 14
    }
    # 20 days since last change (> 14 days)
    res = engine.validate_candidate(
        candidate_price=900, discount_pct=10.0, regular_price=1000, unit_cost=500,
        policy=policy, days_since_last_change=20, has_history=True
    )
    assert res["is_feasible"] is True
    assert res["rejection_reason"] is None


def test_price_history_service_resolves_dates_accurately(price_history):
    """PriceHistoryService accurately retrieves approved events and computes elapsed days."""
    # SKU-0016 at STORE-01 has initial event on 2024-01-01
    last_dt = price_history.get_last_price_change_date("SKU-0016", "STORE-01", "2024-01-20")
    assert last_dt == pd.Timestamp("2024-01-01")
    
    days = price_history.get_days_since_last_change("SKU-0016", "STORE-01", "2024-01-20")
    assert days == 19
    
    # As of 2023-12-01 (prior to dataset), history should be None
    assert price_history.get_last_price_change_date("SKU-0016", "STORE-01", "2023-12-01") is None
    assert price_history.get_days_since_last_change("SKU-0016", "STORE-01", "2023-12-01") is None


# ==============================================================================
# 3. Policy Parsing & Malformed Configuration Rejection
# ==============================================================================

def test_malformed_policy_rejected_explicitly():
    """Policies with malformed step syntax, negative steps, or contradictory margins must be rejected."""
    # Missing/empty steps
    with pytest.raises(ValueError, match="allowed_steps_list must be a non-empty list"):
        validate_policy_configuration({"allowed_steps_list": []})
        
    # Non-numeric steps
    with pytest.raises(ValueError, match="Invalid discount step"):
        validate_policy_configuration({"allowed_steps_list": ["invalid", 10], "maximum_discount_pct": 30})
        
    # Negative steps
    with pytest.raises(ValueError, match="Invalid discount step"):
        validate_policy_configuration({"allowed_steps_list": [-10, 20], "maximum_discount_pct": 30})
        
    # Contradictory / negative maximum discount
    with pytest.raises(ValueError, match="Invalid maximum_discount_pct"):
        validate_policy_configuration({"allowed_steps_list": [0, 10], "maximum_discount_pct": -5})


def test_validate_candidate_handles_malformed_policy_safely(engine):
    """validate_candidate safely rejects candidates when passed a malformed policy dict."""
    bad_policy = {"allowed_steps_list": "not_a_list"}
    res = engine.validate_candidate(900, 10.0, 1000, 400, bad_policy)
    assert res["is_feasible"] is False
    assert "Malformed or invalid policy configuration" in res["rejection_reason"]


# ==============================================================================
# 4. Decoupled Human Approval Workflow Tests
# ==============================================================================

def test_recommendation_generated_as_pending_approval(optimizer, sample_row):
    """Recommendations must be generated in PENDING_APPROVAL status without auto-approval."""
    # Even if human_approver is passed, the recommendation generation itself leaves it pending
    rec = optimizer.optimize_sku_day(sample_row, human_approver="Pricing_Director")
    assert rec["recommendation_status"] == "RECOMMENDED"
    assert rec["approval_status"] == "PENDING_APPROVAL"
    assert rec["approved_by"] is None
    assert rec["approved_at"] is None


def test_apply_human_approval_records_valid_approval():
    """Explicit human approval action transitions record to APPROVED_BY_HUMAN."""
    audit_rec = {
        "recommendation_status": "RECOMMENDED",
        "recommended_discount_pct": 10.0,
        "recommended_price": 900.0,
        "approval_status": "PENDING_APPROVAL"
    }
    approved = apply_human_approval(audit_rec, approver_id="Merchandiser_M42", decision="APPROVED", notes="Seasonal promo")
    assert approved["approval_status"] == "APPROVED_BY_HUMAN"
    assert approved["approved_by"] == "Merchandiser_M42"
    assert approved["approval_notes"] == "Seasonal promo"
    assert approved["approved_at"] is not None


def test_cannot_approve_no_feasible_candidate():
    """Attempting to approve a NO_FEASIBLE_CANDIDATE record must raise ValueError."""
    infeasible_rec = {
        "recommendation_status": "NO_FEASIBLE_CANDIDATE",
        "recommended_discount_pct": None,
        "recommended_price": None,
        "approval_status": None
    }
    with pytest.raises(ValueError, match="Cannot approve or reject: no valid recommendation was produced"):
        apply_human_approval(infeasible_rec, approver_id="Director_D1", decision="APPROVED")


# ==============================================================================
# 5. Policy Precedence Hierarchy
# ==============================================================================

def test_policy_precedence_hierarchy(engine):
    """Verify SKU > STORE > CATEGORY > CHAIN hierarchy resolution."""
    # 1. SKU level: SKU-0071 has POL-009 (max discount 30)
    p_sku = engine.resolve_policy("SKU-0071", "STORE-01", "Jacket", "2025-04-01")
    assert p_sku["policy_id"] == "POL-009"
    assert p_sku["maximum_discount_pct"] == 30
    
    # 2. STORE level: STORE-04 has POL-008 (max discount 50)
    p_store = engine.resolve_policy("SKU-XXXX", "STORE-04", "TShirt", "2025-04-01")
    assert p_store["policy_id"] == "POL-008"
    
    # 3. CATEGORY level: Jeans has POL-004
    p_cat = engine.resolve_policy("SKU-XXXX", "STORE-01", "Jeans", "2025-04-01")
    assert p_cat["policy_id"] == "POL-004"
    
    # 4. CHAIN level: Dress has POL-005, but unknown category falls back to chain
    p_chain = engine.resolve_policy("SKU-XXXX", "STORE-01", "UnknownCategory", "2025-04-01")
    assert p_chain["policy_id"] in ["POL-002", "DEFAULT"]


# ==============================================================================
# 6. Recommendation Approval Gate Hardening & Invariant Tests
# ==============================================================================

def test_approval_gate_rejects_ineligible_candidate():
    """Approval endpoint must reject candidates that fail binding policy constraints, recording an audit event."""
    import uuid
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from fastapi import HTTPException
    from backend.app.db.base import Base
    from backend.app.db.models.user import User
    from backend.app.db.models.optimization import OptimizationRun, OptimizationCandidate, Recommendation
    from backend.app.db.models.governance import AuditEvent
    from backend.app.services.recommendation_service import RecommendationService

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()

    approver = User(id=uuid.uuid4(), email="approver@corp.com", role="approver", password_hash="h", full_name="Approver", is_active=True)
    db.add(approver)

    run = OptimizationRun(
        id=uuid.uuid4(), requested_by=approver.id, store_id="STORE-01", sku="SKU-0141", status="COMPLETED",
        input_snapshot={"sku_id": "SKU-0141", "store_id": "STORE-01", "category": "TShirt", "regular_price": 799.0, "unit_cost": 310.0, "inventory_effective_date": "2025-06-30"},
        model_versions={"model1": "v1"}, policy_snapshot={"policy_id": "POL-003"}
    )
    db.add(run)

    # Ineligible candidate (e.g. 10% discount blocked by 14-day cadence)
    cand = OptimizationCandidate(
        id=uuid.uuid4(), run_id=run.id, discount_pct=10.0, candidate_price=719.10, policy_passed=False,
        rejection_reasons="Only 5 days since last change (minimum 14 required)"
    )
    db.add(cand)

    rec = Recommendation(id=uuid.uuid4(), run_id=run.id, candidate_id=cand.id, status="PENDING_APPROVAL", submitted_by=approver.id)
    db.add(rec)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        RecommendationService.approve_recommendation(db, approver, rec.id)
    assert exc_info.value.status_code == 422
    assert "Policy constraint revalidation failed" in exc_info.value.detail

    # Verify failed approval attempt audit event was recorded
    fail_audit = db.query(AuditEvent).filter(AuditEvent.event_type == "APPROVAL_ATTEMPT_REJECTED").first()
    assert fail_audit is not None
    assert fail_audit.details_json["approver"] == "approver@corp.com"


def test_approval_gate_rejects_mismatched_run_and_candidate():
    """Approval must be rejected if candidate does not belong to the linked optimization run."""
    import uuid
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from fastapi import HTTPException
    from backend.app.db.base import Base
    from backend.app.db.models.user import User
    from backend.app.db.models.optimization import OptimizationRun, OptimizationCandidate, Recommendation
    from backend.app.services.recommendation_service import RecommendationService

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()

    approver = User(id=uuid.uuid4(), email="approver@corp.com", role="approver", password_hash="h", full_name="Approver", is_active=True)
    db.add(approver)

    run = OptimizationRun(
        id=uuid.uuid4(), requested_by=approver.id, store_id="STORE-01", sku="SKU-0141", status="COMPLETED",
        input_snapshot={"sku_id": "SKU-0141", "store_id": "STORE-01", "category": "TShirt", "regular_price": 799.0, "unit_cost": 310.0, "inventory_effective_date": "2025-06-30"},
        model_versions={}, policy_snapshot={}
    )
    db.add(run)

    # Candidate belongs to a completely different run
    cand_foreign = OptimizationCandidate(
        id=uuid.uuid4(), run_id=uuid.uuid4(), discount_pct=0.0, candidate_price=799.0, policy_passed=True
    )
    db.add(cand_foreign)

    rec = Recommendation(id=uuid.uuid4(), run_id=run.id, candidate_id=cand_foreign.id, status="PENDING_APPROVAL", submitted_by=approver.id)
    db.add(rec)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        RecommendationService.approve_recommendation(db, approver, rec.id)
    assert exc_info.value.status_code == 422
    assert "Candidate record missing or mismatched" in exc_info.value.detail


def test_approval_gate_prevents_repeated_or_conflicting_approval():
    """A recommendation that is already APPROVED cannot be re-approved."""
    import uuid
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from fastapi import HTTPException
    from backend.app.db.base import Base
    from backend.app.db.models.user import User
    from backend.app.db.models.optimization import OptimizationRun, OptimizationCandidate, Recommendation
    from backend.app.services.recommendation_service import RecommendationService

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()

    approver = User(id=uuid.uuid4(), email="approver@corp.com", role="approver", password_hash="h", full_name="Approver", is_active=True)
    db.add(approver)

    run = OptimizationRun(
        id=uuid.uuid4(), requested_by=approver.id, store_id="STORE-01", sku="SKU-0141", status="COMPLETED",
        input_snapshot={"sku_id": "SKU-0141", "store_id": "STORE-01", "category": "TShirt", "regular_price": 799.0, "unit_cost": 310.0, "inventory_effective_date": "2025-06-30"},
        model_versions={}, policy_snapshot={}
    )
    db.add(run)

    cand = OptimizationCandidate(id=uuid.uuid4(), run_id=run.id, discount_pct=0.0, candidate_price=799.0, policy_passed=True)
    db.add(cand)

    rec = Recommendation(id=uuid.uuid4(), run_id=run.id, candidate_id=cand.id, status="PENDING_APPROVAL", submitted_by=approver.id)
    db.add(rec)
    db.commit()

    # First approval succeeds
    approved = RecommendationService.approve_recommendation(db, approver, rec.id, notes="Approved base price")
    assert approved.status == "APPROVED"

    # Second concurrent or duplicate approval fails
    with pytest.raises(HTTPException) as exc_info:
        RecommendationService.approve_recommendation(db, approver, rec.id)
    assert exc_info.value.status_code == 400
    assert "Cannot approve recommendation in 'APPROVED' status" in exc_info.value.detail


def test_approval_transaction_rollback_preserves_pending_state():
    """If an unhandled exception or abort occurs during approval processing,
    the transaction rollback must ensure that the recommendation status remains
    PENDING_APPROVAL, and no orphan ApprovalEvent or AuditEvent is committed."""
    import uuid
    from unittest.mock import patch
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from backend.app.db.base import Base
    from backend.app.db.models.user import User
    from backend.app.db.models.optimization import OptimizationRun, OptimizationCandidate, Recommendation
    from backend.app.db.models.governance import ApprovalEvent, AuditEvent
    from backend.app.services.recommendation_service import RecommendationService

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()

    approver = User(id=uuid.uuid4(), email="approver@corp.com", role="approver", password_hash="h", full_name="Approver", is_active=True)
    db.add(approver)

    run = OptimizationRun(
        id=uuid.uuid4(), requested_by=approver.id, store_id="STORE-01", sku="SKU-0141", status="COMPLETED",
        input_snapshot={"sku_id": "SKU-0141", "store_id": "STORE-01", "category": "TShirt", "regular_price": 799.0, "unit_cost": 310.0, "inventory_effective_date": "2025-06-30"},
        model_versions={}, policy_snapshot={}
    )
    db.add(run)

    cand = OptimizationCandidate(id=uuid.uuid4(), run_id=run.id, discount_pct=0.0, candidate_price=799.0, policy_passed=True)
    db.add(cand)

    rec = Recommendation(id=uuid.uuid4(), run_id=run.id, candidate_id=cand.id, status="PENDING_APPROVAL", submitted_by=approver.id)
    db.add(rec)
    db.commit()

    # Simulate database commit failure
    with patch.object(db, "commit", side_effect=RuntimeError("Simulated DB connection drop")):
        try:
            RecommendationService.approve_recommendation(db, approver, rec.id, notes="Will fail")
        except RuntimeError:
            db.rollback()

    # Verify rollback integrity: status must remain PENDING_APPROVAL
    fresh_rec = db.scalar(select(Recommendation).where(Recommendation.id == rec.id))
    assert fresh_rec.status == "PENDING_APPROVAL", "Status must remain PENDING_APPROVAL on failed commit"
    assert fresh_rec.reviewed_by is None
    assert fresh_rec.reviewed_at is None

    # Verify zero orphan approval or audit events were committed
    appr_events = db.scalars(select(ApprovalEvent).where(ApprovalEvent.recommendation_id == rec.id, ApprovalEvent.action == "APPROVE")).all()
    assert len(appr_events) == 0, "No APPROVE ApprovalEvent should exist after rollback"

    audit_events = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == str(rec.id), AuditEvent.event_type == "RECOMMENDATION_APPROVED")).all()
    assert len(audit_events) == 0, "No RECOMMENDATION_APPROVED AuditEvent should exist after rollback"

