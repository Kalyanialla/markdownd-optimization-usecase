"""
AWS Secrets Manager helper.
Fetches secrets from AWS Secrets Manager if configured,
falling back gracefully to environment variables and .env.
"""

import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger("secrets_manager")


def fetch_aws_secrets(secret_name: str, region_name: str = "us-east-1") -> Dict[str, Any]:
    """
    Fetch secret values from AWS Secrets Manager.
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

    try:
        client = boto3.client(
            service_name="secretsmanager",
            region_name=region_name,
        )
        response = client.get_secret_value(SecretId=secret_name)
        if "SecretString" in response:
            secret_data = json.loads(response["SecretString"])
            logger.info("Successfully fetched secrets from AWS Secrets Manager: %s", secret_name)
            return secret_data
    except (ClientError, NoCredentialsError, Exception) as exc:
        logger.info(
            "Could not retrieve secret '%s' from AWS Secrets Manager (%s). Using local/env fallback.",
            secret_name,
            str(exc),
        )

    return {}


def load_secrets_into_environment(
    secret_name: str = "Markdown-Intelligence-Console",
    region_name: str = "us-east-1"
) -> None:
    """
    Retrieves secrets and populates os.environ for any keys not already explicitly set.
    """
    # Allow overriding secret name and region via environment
    sec_name = os.getenv("AWS_SECRET_NAME", secret_name)
    reg_name = os.getenv("AWS_REGION", region_name)

    secrets = fetch_aws_secrets(secret_name=sec_name, region_name=reg_name)
    for key, value in secrets.items():
        if key not in os.environ and value is not None:
            os.environ[key] = str(value)
