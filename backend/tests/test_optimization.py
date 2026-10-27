"""
Unit tests for Optimization orchestration endpoints.
"""

import uuid
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_headers(client: TestClient):
    email = "optimizer_analyst@retail.com"
    password = "Password123!"
    signup_res = client.post("/api/v1/auth/signup", json={
        "email": email,
        "password": password,
        "full_name": "Optimizer Analyst"
    })
    if signup_res.status_code == 201:
        token = signup_res.json()["access_token"]
    else:
        login_res = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password
        })
        token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_optimization_run_unauthenticated(client: TestClient):
    """Unauthorized run request returns 401."""
    res = client.post("/api/v1/optimization-runs", json={
        "sku_id": "SKU-0001",
        "store_id": "STORE-01",
    })
    assert res.status_code == 401


def test_create_optimization_run_success(client: TestClient, auth_headers: dict):
    """Creating an optimization run executes the ML models and persists candidates."""
    res = client.post("/api/v1/optimization-runs", json={
        "sku_id": "SKU-0001",
        "store_id": "STORE-01",
        "planning_horizon_days": 7
    }, headers=auth_headers)
    assert res.status_code == 201
    data = res.json()
    assert "id" in data
    assert data["sku"] == "SKU-0001"
    assert data["store_id"] == "STORE-01"
    assert data["status"] == "COMPLETED"
    assert "candidates" in data
    assert len(data["candidates"]) > 0

    # Verify candidate attributes
    cand = data["candidates"][0]
    assert "discount_pct" in cand
    assert "candidate_price" in cand
    assert "policy_passed" in cand

    # Model metadata snapshot
    assert "model1_baseline_demand" in data["model_versions"]
    assert "model2_price_sensitivity" in data["model_versions"]
    assert "model3_stockout_risk" in data["model_versions"]


def test_list_optimization_runs(client: TestClient, auth_headers: dict):
    """Listing runs returns recent runs with metadata."""
    res = client.get("/api/v1/optimization-runs", headers=auth_headers)
    assert res.status_code == 200
    runs = res.json()
    assert isinstance(runs, list)
    assert len(runs) >= 1


def test_optimization_run_idempotency(client: TestClient, auth_headers: dict):
    """Providing the same idempotency key returns the existing run without re-evaluating."""
    key = f"idem-test-{uuid.uuid4()}"
    res1 = client.post("/api/v1/optimization-runs", json={
        "sku_id": "SKU-0001",
        "store_id": "STORE-01",
        "idempotency_key": key
    }, headers=auth_headers)
    assert res1.status_code == 201
    run_id1 = res1.json()["id"]

    res2 = client.post("/api/v1/optimization-runs", json={
        "sku_id": "SKU-0001",
        "store_id": "STORE-01",
        "idempotency_key": key
    }, headers=auth_headers)
    assert res2.status_code == 201 or res2.status_code == 200
    run_id2 = res2.json()["id"]
    assert run_id1 == run_id2
