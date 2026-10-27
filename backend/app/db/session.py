"""
Database session management and connectivity verification.
"""

from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from backend.app.core.config import settings
from backend.app.core.logging import logger

def get_engine_args(url: str):
    args = {}
    if url.startswith("sqlite"):
        args["connect_args"] = {"check_same_thread": False}
    else:
        args["pool_pre_ping"] = True
        args["pool_size"] = 10
        args["max_overflow"] = 20
    return args

engine = create_engine(settings.DATABASE_URL, **get_engine_args(settings.DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a scoped database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connectivity(db: Session = None) -> tuple[bool, str]:
    """
    Verifies that the database is reachable and accepts queries.
    Returns (True, 'Connected') on success, (False, error_message) on failure.
    """
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        db.execute(text("SELECT 1"))
        return True, "Connected"
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False, str(e)
    finally:
        if close_session:
            db.close()
