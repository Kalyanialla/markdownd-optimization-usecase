"""
Unit and integration tests for Recommendation and Approval workflows.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.db.models.user import User


@pytest.fixture
def test_users(client: TestClient, db: Session):
    """
    Creates an analyst user and an approver user.
    """
    users = {}
    for role, email in [("analyst", "analyst_rec@retail.com"), ("approver", "approver_rec@retail.com")]:
        pwd = "Password123!"
        res = client.post("/api/v1/auth/signup", json={
            "email": email,
            "password": pwd,
            "full_name": f"Test {role.capitalize()}"
        })
        if res.status_code == 201:
            token = res.json()["access_token"]
        else:
            token = client.post("/api/v1/auth/login", json={"email": email, "password": pwd}).json()["access_token"]

        # Ensure role in DB
        u = db.execute(select(User).where(User.email == email)).scalar_one()
        u.role = role
        db.commit()

        users[role] = {"headers": {"Authorization": f"Bearer {token}"}, "user": u}
    return users


def test_recommendation_lifecycle(client: TestClient, test_users: dict):
    analyst_headers = test_users["analyst"]["headers"]
    approver_headers = test_users["approver"]["headers"]

    # 1. Run optimization to get candidates
    run_res = client.post("/api/v1/optimization-runs", json={
        "sku_id": "SKU-0001",
        "store_id": "STORE-01",
        "planning_horizon_days": 7
    }, headers=analyst_headers)
    assert run_res.status_code == 201
    run_data = run_res.json()
    run_id = run_data["id"]
    candidates = run_data["candidates"]
    assert len(candidates) > 0
    selected_cand = candidates[0]
    candidate_id = selected_cand["id"]

    # 2. Analyst submits candidate as recommendation
    sub_res = client.post("/api/v1/recommendations", json={
        "run_id": run_id,
        "candidate_id": candidate_id,
        "rationale": "High predicted elasticity and low inventory clearance risk."
    }, headers=analyst_headers)
    assert sub_res.status_code == 201
    rec_data = sub_res.json()
    rec_id = rec_data["id"]
    assert rec_data["status"] == "PENDING_APPROVAL"
    assert rec_data["sku"] == "SKU-0001"
    assert rec_data["store_id"] == "STORE-01"

    # 3. Duplicate submission prevention
    dup_res = client.post("/api/v1/recommendations", json={
        "run_id": run_id,
        "candidate_id": candidate_id,
        "rationale": "Duplicate attempt"
    }, headers=analyst_headers)
    assert dup_res.status_code == 409

    # 4. Analyst attempts to approve (must be forbidden 403)
    analyst_approve_res = client.post(
        f"/api/v1/recommendations/{rec_id}/approve",
        json={"notes": "Analyst trying to self-approve"},
        headers=analyst_headers
    )
    assert analyst_approve_res.status_code == 403

    # 5. Approver approves recommendation
    appr_res = client.post(
        f"/api/v1/recommendations/{rec_id}/approve",
        json={"notes": "Approved for upcoming promotional cycle."},
        headers=approver_headers
    )
    assert appr_res.status_code == 200
    appr_data = appr_res.json()
    assert appr_data["status"] == "APPROVED"
    assert appr_data["reviewer_name"] is not None

    # 6. Listing recommendations
    list_res = client.get("/api/v1/recommendations?status=APPROVED", headers=analyst_headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1
