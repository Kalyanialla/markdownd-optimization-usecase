"""
AWS Secrets Manager helper.
Fetches secrets from AWS Secrets Manager across regions,
falling back gracefully to environment variables and .env.
"""

import json
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger("secrets_manager")


def fetch_aws_secrets(secret_name: str, region_name: str = "us-east-1") -> Dict[str, Any]:
    """
    Fetch secret values from AWS Secrets Manager.
    Tries the configured region, then common AWS regions (us-east-1, us-east-2, ap-south-1).
    Returns a dict of key-value pairs parsed from JSON, or an empty dict on error.
    """
    if not secret_name:
        return {}

    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        logger.warning("boto3 is not installed; skipping AWS Secrets Manager lookup.")
        return {}

    regions_to_try = [
        region_name,
        os.getenv("AWS_REGION"),
        os.getenv("AWS_DEFAULT_REGION"),
        "us-east-1",
        "us-east-2",
        "ap-south-1",
        "us-west-2",
    ]
    unique_regions = list(dict.fromkeys([r for r in regions_to_try if r]))

    secret_names_to_try = [
        secret_name,
        secret_name.strip(),
        secret_name.lower(),
        f"Usecase-{secret_name}",
        f"usecase-{secret_name}",
    ]
    unique_names = list(dict.fromkeys([n for n in secret_names_to_try if n]))

    client_kwargs: Dict[str, Any] = {"service_name": "secretsmanager"}
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token = os.getenv("AWS_SESSION_TOKEN")

    if aws_access_key and aws_secret_key:
        client_kwargs["aws_access_key_id"] = aws_access_key
        client_kwargs["aws_secret_access_key"] = aws_secret_key
        if aws_session_token:
            client_kwargs["aws_session_token"] = aws_session_token

    for r in unique_regions:
        try:
            client = boto3.client(**{**client_kwargs, "region_name": r})
            for sname in unique_names:
                try:
                    response = client.get_secret_value(SecretId=sname)
                    if "SecretString" in response:
                        raw = response["SecretString"]
                        try:
                            secret_data = json.loads(raw)
                        except Exception:
                            secret_data = {"DATABASE_URL": raw.strip()}
                        logger.info(f"Successfully loaded AWS Secret '{sname}' from region {r}")
                        return secret_data
                except ClientError as e:
                    code = e.response.get("Error", {}).get("Code", "")
                    if code == "ResourceNotFoundException":
                        continue
                    else:
                        logger.debug(f"AWS Secret '{sname}' in {r} returned {code}: {e}")
                except Exception as e:
                    logger.debug(f"Error fetching '{sname}' in {r}: {e}")
        except Exception as e:
            logger.debug(f"Could not initialize boto3 client in region {r}: {e}")

    logger.info("Could not retrieve secret from AWS Secrets Manager. Using fallback.")
    return {}


def format_db_url(url: str) -> str:
    """Ensures database URL has an explicit psycopg driver."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and not (url.startswith("postgresql+psycopg://") or url.startswith("postgresql+psycopg2://")):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def load_secrets_into_environment(
    secret_name: str = "Markdown-Intelligence-Console",
    region_name: str = "us-east-1",
    override_existing: bool = True
) -> None:
    """
    Retrieves secrets and populates os.environ.
    AWS Secrets Manager takes priority for centralized database credentials.
    """
    sec_name = os.getenv("AWS_SECRET_NAME", secret_name)
    reg_name = os.getenv("AWS_REGION", region_name)

    secrets = fetch_aws_secrets(secret_name=sec_name, region_name=reg_name)
    if not secrets:
        # Also try default fallback name
        secrets = fetch_aws_secrets(secret_name="Markdown-Intelligence-Console", region_name=reg_name)

    # 1. Check for direct URL key in Secrets Manager
    direct_url = (
        secrets.get("DATABASE_URL")
        or secrets.get("url")
        or secrets.get("connection_string")
        or secrets.get("db_url")
        or secrets.get("SQLALCHEMY_DATABASE_URI")
    )
    if direct_url:
        formatted = format_db_url(str(direct_url))
        os.environ["DATABASE_URL"] = formatted
        logger.info("Configured DATABASE_URL directly from AWS Secrets Manager.")

    # 2. Support individual database credential keys returned from Secrets Manager
    db_user = (
        secrets.get("username")
        or secrets.get("user")
        or secrets.get("dbUser")
        or secrets.get("DB_USER")
        or secrets.get("POSTGRES_USER")
    )
    db_pass = (
        secrets.get("password")
        or secrets.get("dbPassword")
        or secrets.get("DB_PASSWORD")
        or secrets.get("POSTGRES_PASSWORD")
    )
    db_host = (
        secrets.get("host")
        or secrets.get("endpoint")
        or secrets.get("address")
        or secrets.get("server")
        or secrets.get("DB_HOST")
        or secrets.get("POSTGRES_HOST")
    )
    db_port = (
        secrets.get("port")
        or secrets.get("dbPort")
        or secrets.get("DB_PORT")
        or secrets.get("POSTGRES_PORT")
        or "5432"
    )
    db_name = (
        secrets.get("dbname")
        or secrets.get("database")
        or secrets.get("dbName")
        or secrets.get("dbInstanceIdentifier")
        or secrets.get("DB_NAME")
        or secrets.get("POSTGRES_DB")
    )

    if db_user and db_pass and db_host and db_name:
        url = f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        os.environ["DATABASE_URL"] = url
        logger.info(f"Configured DATABASE_URL from AWS Secrets Manager components ({db_user}@{db_host}:{db_port}/{db_name}).")

    # 3. Populate other secret keys
    for key, value in secrets.items():
        if value is not None and key != "DATABASE_URL":
            if override_existing or key not in os.environ:
                os.environ[key] = str(value)
