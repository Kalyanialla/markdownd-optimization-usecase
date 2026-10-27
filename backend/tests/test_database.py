"""
Automated unit tests for database models, migrations, and CRUD operations.
Uses an explicit test-only database configuration.
"""

import os
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

from backend.app.db.base import Base
from backend.app.db.models import (
    User,
    RefreshToken,
    OptimizationRun,
    OptimizationCandidate,
    Recommendation,
    ApprovalEvent,
    AuditEvent,
    ReportArtifact
)

TEST_DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_db.sqlite"))
TEST_DB_URL = f"sqlite:///{TEST_DB_FILE}"


@pytest.fixture(scope="module")
def db_engine():
    # Clean previous test db if exists
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass

    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    
    # Run Alembic migrations programmatically on test DB
    alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    alembic_cfg = Config(alembic_ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    alembic_cfg.set_main_option("script_location", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic")))
    
    command.upgrade(alembic_cfg, "head")

    yield engine

    engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ==============================================================================
# 1. Model Metadata & Table Definitions Test
# ==============================================================================

def test_all_models_registered_in_metadata():
    """Verify that all 8 required application tables exist in Base.metadata."""
    expected_tables = {
        "users",
        "refresh_tokens",
        "optimization_runs",
        "optimization_candidates",
        "recommendations",
        "approval_events",
        "audit_events",
        "report_artifacts"
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}"


# ==============================================================================
# 2. First-Admin Bootstrap & User Creation Test
# ==============================================================================

def test_first_admin_bootstrap_and_user_creation(db_session):
    """
    Test transaction-safe role assignment:
    First user created gets 'admin' role; second user defaults to 'analyst'.
    """
    def create_user_with_safe_bootstrap(email, full_name, password_hash):
        # Transaction-safe check of total user count
        count = db_session.scalar(select(func.count(User.id)))
        assigned_role = "admin" if count == 0 else "analyst"
        
        user = User(
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            role=assigned_role
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    # First user
    admin_user = create_user_with_safe_bootstrap("admin@retail.com", "Chief Admin", "hashed_pw_1")
    assert admin_user.role == "admin"
    assert admin_user.email == "admin@retail.com"
    assert isinstance(admin_user.id, uuid.UUID)

    # Second user
    analyst_user = create_user_with_safe_bootstrap("analyst1@retail.com", "Pricing Operator", "hashed_pw_2")
    assert analyst_user.role == "analyst"
    assert analyst_user.email == "analyst1@retail.com"


# ==============================================================================
# 3. Optimization Run, Candidate, Recommendation, and Audit CRUD Test
# ==============================================================================

def test_full_optimization_lifecycle_persistence(db_session):
    """Verify persisting a complete optimization run, candidates, recommendation, and audit trail."""
    user = db_session.scalar(select(User).limit(1))
    
    # 1. Create OptimizationRun
    run = OptimizationRun(
        requested_by=user.id,
        store_id="STORE-01",
        sku="SKU-0016",
        status="COMPLETED",
        input_snapshot={"regular_price": 1199, "unit_cost": 600, "stock": 45},
        model_versions={"model1": "1.0", "model2": "1.0", "model3": "1.0"},
        policy_snapshot={"policy_id": "POL-002", "allowed_steps": [0, 10, 20, 30, 40, 50]},
        idempotency_key=str(uuid.uuid4())
    )
    db_session.add(run)
    db_session.flush()

    assert isinstance(run.id, uuid.UUID)

    # 2. Add Candidate evaluations
    cand1 = OptimizationCandidate(
        run_id=run.id,
        discount_pct=0.0,
        candidate_price=1199.0,
        predicted_demand=1.02,
        stockout_risk=0.26,
        unit_margin=599.0,
        estimated_revenue=8393.0,
        estimated_gross_profit=4193.0,
        risk_adjusted_profit=4193.0,
        policy_passed=True
    )
    cand2 = OptimizationCandidate(
        run_id=run.id,
        discount_pct=10.0,
        candidate_price=1079.1,
        predicted_demand=1.28,
        stockout_risk=0.25,
        unit_margin=479.1,
        estimated_revenue=9711.9,
        estimated_gross_profit=4311.9,
        risk_adjusted_profit=4311.9,
        policy_passed=True
    )
    db_session.add_all([cand1, cand2])
    db_session.flush()

    # 3. Create Recommendation
    rec = Recommendation(
        run_id=run.id,
        candidate_id=cand2.id,
        status="PENDING_APPROVAL",
        submitted_by=user.id
    )
    db_session.add(rec)
    db_session.flush()

    # 4. Record ApprovalEvent
    app_evt = ApprovalEvent(
        recommendation_id=rec.id,
        actor_id=user.id,
        action="SUBMIT",
        reason="Seasonal clearance",
        previous_status=None,
        new_status="PENDING_APPROVAL"
    )
    db_session.add(app_evt)

    # 5. Record AuditEvent
    audit_evt = AuditEvent(
        actor_id=user.id,
        event_type="OPTIMIZATION_RUN_CREATED",
        entity_type="OptimizationRun",
        entity_id=str(run.id),
        details_json={"store_id": "STORE-01", "sku": "SKU-0016"}
    )
    db_session.add(audit_evt)

    # 6. Record ReportArtifact
    artifact = ReportArtifact(
        run_id=run.id,
        artifact_type="json",
        relative_path="runs/test_run/audit.json",
        sha256="abc123def456"
    )
    db_session.add(artifact)

    db_session.commit()

    # Verify retrieval
    retrieved_run = db_session.scalar(select(OptimizationRun).where(OptimizationRun.id == run.id))
    assert retrieved_run is not None
    assert len(retrieved_run.candidates) == 2
    assert len(retrieved_run.recommendations) == 1
    assert len(retrieved_run.artifacts) == 1
    assert retrieved_run.recommendations[0].status == "PENDING_APPROVAL"
