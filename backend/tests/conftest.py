"""
Shared pytest fixtures for backend unit and API tests.
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure project root is in sys.path
workspace_root = str(Path(__file__).resolve().parents[2])
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

import backend.app.db.models
from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.db.base import Base

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(engine):
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db_sess = TestingSession()
        try:
            yield db_sess
        finally:
            db_sess.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
