"""
Application configuration using Pydantic Settings.
Loads configuration from environment variables and backend/.env file.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_ENV: str = "development"
    APP_NAME: str = "Markdown Intelligence Console"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # Primary Database Configuration
    DATABASE_URL: str = "postgresql+psycopg://markdown_app:replace_password@localhost:5432/markdown_optimization"
    
    # Optional Explicit Test Database URL (strictly for automated test suites)
    TEST_DATABASE_URL: Optional[str] = None

    # JWT Authentication
    JWT_SECRET_KEY: str = "local_dev_secret_key_needs_override_in_production_environments_1234567890"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # File and ML Artifact Paths
    PROJECT_ROOT_PATH: Path = PROJECT_ROOT
    ML_ARTIFACT_ROOT: Path = PROJECT_ROOT / "ml" / "artifacts"
    DATA_ROOT: Path = PROJECT_ROOT / "data"
    REPORT_ROOT: Path = PROJECT_ROOT / "data" / "reports" / "optimizer" / "runs"


settings = Settings()
