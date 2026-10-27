"""
Tests for health and readiness endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.db.base import Base

TEST_HEALTH_DB_URL = "sqlite:///:memory:"

@pytest.fixture
def client():
    engine = create_engine(TEST_HEALTH_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_endpoint(client):
    """Liveness probe must return 200 and 'ok' status."""
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "timestamp" in data


def test_readiness_endpoint_connected(client):
    """Readiness probe returns 200 when database connectivity succeeds."""
    response = client.get("/api/v1/system/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_readiness_endpoint_disconnected(monkeypatch):
    """Readiness probe returns 503 when database connectivity fails."""
    import backend.app.main as main_module
    
    # Mock check_db_connectivity to simulate database outage
    monkeypatch.setattr(
        main_module,
        "check_db_connectivity",
        lambda db: (False, "Connection to PostgreSQL at localhost:5432 refused.")
    )

    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/system/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "disconnected"
        assert "refused" in data["error"]
