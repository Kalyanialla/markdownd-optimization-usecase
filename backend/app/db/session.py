"""
Database session management, resilient connectivity, and schema initialization.
"""

from typing import Generator
from urllib.parse import urlparse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from backend.app.core.config import settings
from backend.app.core.logging import logger


def ensure_database_exists(db_url: str) -> None:
    """
    Connects to PostgreSQL maintenance database to ensure target database exists.
    Creates target database if it does not exist yet.
    """
    if not db_url or "sqlite" in db_url:
        return

    try:
        clean_url = (
            db_url.replace("postgresql+psycopg://", "postgresql://")
            .replace("postgresql+psycopg2://", "postgresql://")
        )
        parsed = urlparse(clean_url)
        target_db = parsed.path.lstrip("/")
        if not target_db or target_db in ("postgres", "template1"):
            return

        base_url = clean_url.rsplit("/", 1)[0]
        maintenance_url = f"{base_url}/postgres"

        try:
            import psycopg
            with psycopg.connect(maintenance_url, autocommit=True, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
                    if not cur.fetchone():
                        logger.info(f"Target database '{target_db}' does not exist. Creating...")
                        cur.execute(f'CREATE DATABASE "{target_db}"')
                        logger.info(f"Database '{target_db}' created successfully.")
                    else:
                        logger.debug(f"Target database '{target_db}' already exists.")
        except Exception as exc:
            logger.debug(f"psycopg maintenance check note: {exc}")
            # Try psycopg2 as alternate
            try:
                import psycopg2
                from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
                conn2 = psycopg2.connect(maintenance_url, connect_timeout=5)
                conn2.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                cur2 = conn2.cursor()
                cur2.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
                if not cur2.fetchone():
                    cur2.execute(f'CREATE DATABASE "{target_db}"')
                    logger.info(f"Database '{target_db}' created successfully via psycopg2.")
                cur2.close()
                conn2.close()
            except Exception as exc2:
                logger.debug(f"psycopg2 maintenance check note: {exc2}")
    except Exception as e:
        logger.debug(f"ensure_database_exists general note: {e}")


def get_engine_args(url: str):
    args = {}
    if url.startswith("sqlite"):
        args["connect_args"] = {"check_same_thread": False}
    else:
        args["pool_pre_ping"] = True
        args["pool_size"] = 10
        args["max_overflow"] = 20
    return args


def create_resilient_engine(url: str):
    ensure_database_exists(url)
    try:
        return create_engine(url, **get_engine_args(url))
    except Exception as exc:
        if "+psycopg" in url and "+psycopg2" not in url:
            alt = url.replace("+psycopg", "+psycopg2")
            try:
                return create_engine(alt, **get_engine_args(alt))
            except Exception:
                pass
        raise exc


engine = create_resilient_engine(settings.RESOLVED_DATABASE_URL)
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
