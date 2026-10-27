"""
Security utilities: password hashing with bcrypt, JWT token issuance, and token hashing.
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
from jose import jwt, JWTError

from backend.app.core.config import settings
from backend.app.core.exceptions import UnauthorizedException


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt."""
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a bcrypt hash."""
    try:
        pw_bytes = plain_password.encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False


def hash_token(token: str) -> str:
    """Computes SHA-256 hash of a refresh token to safely store in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_secure_token(length: int = 48) -> str:
    """Generates a cryptographically secure random token string."""
    return secrets.token_urlsafe(length)


def create_access_token(
    user_id: Any,
    role: str,
    email: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Creates a signed, expiring JWT access token with type='access' claim."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT access token signature, expiration, and type."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "access":
            raise UnauthorizedException("Invalid token type; access token required.")
        return payload
    except JWTError as err:
        raise UnauthorizedException(f"Invalid or expired token: {err}")
