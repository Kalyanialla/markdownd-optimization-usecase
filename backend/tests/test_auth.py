"""
Automated unit tests for Authentication, JWT rotation, Revocation, and RBAC permissions.
"""

import uuid
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.db.models  # Ensure all models are registered in Base.metadata
from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.db.base import Base
from backend.app.core.security import create_access_token

# Fixtures are provided by conftest.py


# ==============================================================================
# 1. Signup and First-Admin Bootstrap Tests
# ==============================================================================

def test_signup_first_user_becomes_admin(client):
    """The first user registered in the system must be granted the 'admin' role."""
    payload = {
        "email": "first_admin@retail.com",
        "password": "Password123!",
        "full_name": "First Executive Admin"
    }
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["role"] == "admin"
    assert data["user"]["email"] == "first_admin@retail.com"
    assert "access_token" in data
    assert "refresh_token" in data


def test_signup_second_user_becomes_analyst(client):
    """Subsequent registrations must strictly default to the 'analyst' role."""
    payload = {
        "email": "second_user@retail.com",
        "password": "Password123!",
        "full_name": "Standard Pricing Analyst"
    }
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["role"] == "analyst"
    assert data["user"]["email"] == "second_user@retail.com"


def test_public_signup_cannot_forge_privileged_role(client):
    """Public signup must ignore any client-supplied 'role' attribute."""
    payload = {
        "email": "hacker@retail.com",
        "password": "Password123!",
        "full_name": "Privilege Escalation Attempt",
        "role": "admin"  # Attempt to inject role
    }
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["role"] == "analyst"


def test_signup_duplicate_email_rejected(client):
    """Registering an existing email must return 409 Conflict."""
    payload = {
        "email": "first_admin@retail.com",
        "password": "Password123!",
        "full_name": "Duplicate Admin"
    }
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["error"]["message"]


# ==============================================================================
# 2. Login, Verification, and Generic Error Tests
# ==============================================================================

def test_login_successful(client):
    """Valid credentials return bearer tokens and user profile."""
    payload = {
        "email": "first_admin@retail.com",
        "password": "Password123!"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "first_admin@retail.com"
    assert data["token_type"] == "bearer"
    assert "access_token" in data


def test_login_invalid_password_returns_generic_error(client):
    """Invalid password returns generic 401 error message."""
    payload = {
        "email": "first_admin@retail.com",
        "password": "WrongPassword123!"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["error"]["message"]


def test_login_nonexistent_email_returns_identical_generic_error(client):
    """Non-existent email returns identical generic 401 error to prevent enumeration."""
    payload = {
        "email": "unknown_ghost@retail.com",
        "password": "Password123!"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["error"]["message"]


# ==============================================================================
# 3. Protected /me Endpoint & Token Validation
# ==============================================================================

def test_get_me_with_valid_token(client):
    """GET /auth/me returns current user profile with valid Bearer token."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "first_admin@retail.com",
        "password": "Password123!"
    })
    token = login_res.json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "first_admin@retail.com"
    assert response.json()["role"] == "admin"


def test_get_me_without_token_unauthorized(client):
    """Accessing /auth/me without token returns 401 Unauthorized."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_get_me_with_expired_token(client):
    """Expired access token returns 401 Unauthorized."""
    # Issue a token expired 5 minutes ago
    expired_token = create_access_token(
        user_id=uuid.uuid4(),
        role="analyst",
        email="test@retail.com",
        expires_delta=timedelta(minutes=-5)
    )
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


# ==============================================================================
# 4. Refresh Token Rotation and Revocation Tests
# ==============================================================================

def test_refresh_token_rotation_and_revocation(client):
    """
    Refreshing session issues new token pair and revokes old refresh token.
    Re-using the old refresh token fails.
    """
    login_res = client.post("/api/v1/auth/login", json={
        "email": "second_user@retail.com",
        "password": "Password123!"
    })
    old_refresh = login_res.json()["refresh_token"]

    # First refresh: succeeds
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_res.status_code == 200
    new_data = refresh_res.json()
    new_refresh = new_data["refresh_token"]
    assert new_refresh != old_refresh

    # Replay old refresh token: must fail with 401
    replay_res = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay_res.status_code == 401
    assert "revoked" in replay_res.json()["error"]["message"].lower()


def test_logout_revokes_refresh_token(client):
    """Logout revokes refresh token; refreshing with it afterwards fails."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "second_user@retail.com",
        "password": "Password123!"
    })
    refresh_token = login_res.json()["refresh_token"]

    # Logout
    logout_res = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_res.status_code == 200

    # Attempt to refresh
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 401


# ==============================================================================
# 5. Role-Based Access Control (RBAC) Tests
# ==============================================================================

def test_admin_only_endpoints_enforce_role(client):
    """Analysts cannot list all users or change roles; admins can."""
    # Admin token
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "first_admin@retail.com",
        "password": "Password123!"
    })
    admin_token = admin_login.json()["access_token"]

    # Analyst token
    analyst_login = client.post("/api/v1/auth/login", json={
        "email": "second_user@retail.com",
        "password": "Password123!"
    })
    analyst_token = analyst_login.json()["access_token"]
    analyst_id = analyst_login.json()["user"]["id"]

    # Analyst tries to call GET /api/v1/users -> 403 Forbidden
    res_forbidden = client.get("/api/v1/users", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res_forbidden.status_code == 403

    # Admin calls GET /api/v1/users -> 200 OK
    res_admin = client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert len(res_admin.json()) >= 2

    # Admin promotes analyst to approver
    promote_res = client.patch(
        f"/api/v1/users/{analyst_id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "approver"}
    )
    assert promote_res.status_code == 200
    assert promote_res.json()["role"] == "approver"
