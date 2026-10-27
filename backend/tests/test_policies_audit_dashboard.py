"""
Tests for Pricing Policies, Audit Trail, and Dashboard Summary endpoints.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_headers(client: TestClient):
    email = "audit_tester@retail.com"
    pwd = "Password123!"
    res = client.post("/api/v1/auth/signup", json={
        "email": email,
        "password": pwd,
        "full_name": "Audit Tester"
    })
    if res.status_code == 201:
        token = res.json()["access_token"]
    else:
        token = client.post("/api/v1/auth/login", json={"email": email, "password": pwd}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_policies(client: TestClient, auth_headers: dict):
    res = client.get("/api/v1/policies", headers=auth_headers)
    assert res.status_code == 200
    policies = res.json()
    assert isinstance(policies, list)
    assert len(policies) > 0
    p = policies[0]
    assert "policy_id" in p
    assert "allowed_steps" in p
    assert "is_active" in p


def test_resolve_policy_hierarchy(client: TestClient, auth_headers: dict):
    # Test resolving Category TShirt
    res = client.get("/api/v1/policies/resolve?category=TShirt&date=2024-06-30", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["category"] == "TShirt"
    assert data["matched_policy_id"] == "POL-003"
    assert len(data["allowed_steps"]) > 0

    # Test resolving SKU-level override for SKU-0071
    sku_res = client.get("/api/v1/policies/resolve?category=TShirt&sku=SKU-0071&date=2024-06-30", headers=auth_headers)
    assert sku_res.status_code == 200
    sku_data = sku_res.json()
    assert sku_data["matched_policy_id"] == "POL-009"
    assert "SKU level" in sku_data["rule_source"]


def test_audit_trail(client: TestClient, auth_headers: dict):
    res = client.get("/api/v1/audit", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    if len(data["items"]) > 0:
        assert "outcome" in data["items"][0]


def test_audit_summary(client: TestClient, auth_headers: dict):
    res = client.get("/api/v1/audit/summary", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "successful" in data
    assert "failed" in data
    assert "today" in data
    assert data["total"] >= 0
    assert data["total"] == data["successful"] + data["failed"]


def test_audit_filtering(client: TestClient, auth_headers: dict):
    res = client.get("/api/v1/audit?outcome=SUCCESS&limit=5", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) <= 5


def test_dashboard_summary(client: TestClient, auth_headers: dict):
    res = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_runs" in data
    assert "total_candidates" in data
    assert "pending_approvals" in data
    assert "models_healthy" in data
    assert data["models_healthy"] is True
    assert "models_status" in data
    assert "recent_events" in data
