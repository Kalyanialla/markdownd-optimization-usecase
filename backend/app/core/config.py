"""
Application configuration using Pydantic Settings.
Loads configuration from AWS Secrets Manager, environment variables, and root .env file.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.app.core.secrets import load_secrets_into_environment, format_db_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = PROJECT_ROOT / ".env"
BACKEND_ENV_FILE = BACKEND_DIR / ".env"

# Fetch secrets from AWS Secrets Manager (Key: 'Markdown-Intelligence-Console') with graceful fallback
load_secrets_into_environment(
    secret_name=os.getenv("AWS_SECRET_NAME", "Markdown-Intelligence-Console"),
    region_name=os.getenv("AWS_REGION", "us-east-1")
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(ENV_FILE), str(BACKEND_ENV_FILE)],
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_ENV: str = "development"
    APP_NAME: str = "Markdown Intelligence Console"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # AWS Secrets Manager Configuration
    AWS_SECRET_NAME: str = "Markdown-Intelligence-Console"
    AWS_REGION: str = "us-east-1"

    # Primary Database Configuration
    DATABASE_URL: str = "postgresql+psycopg://postgres:Dhani2710@host.docker.internal:5432/markdown_optimization_db"
    
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

    @property
    def RESOLVED_DATABASE_URL(self) -> str:
        raw = os.getenv("DATABASE_URL", self.DATABASE_URL)
        return format_db_url(raw)


settings = Settings()
