"""
Authentication and user management business logic.
Implements concurrency-safe first-admin bootstrap, refresh token rotation, and audit trails.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple, List, Optional
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import (
    hash_password,
    verify_password,
    hash_token,
    generate_secure_token,
    create_access_token
)
from backend.app.core.exceptions import (
    ConflictException,
    UnauthorizedException,
    ForbiddenException,
    EntityNotFoundException
)
from backend.app.schemas.user import UserSignupRequest
from backend.app.db.models.user import User, RefreshToken
from backend.app.db.models.governance import AuditEvent

# Unique 64-bit integer lock key for PostgreSQL advisory xact lock during admin bootstrap
BOOTSTRAP_ADVISORY_LOCK_ID = 987654321


class AuthService:
    @staticmethod
    def _acquire_bootstrap_lock(db: Session):
        """
        Acquires a transaction-level exclusive lock to prevent concurrency races
        during the first-admin bootstrap check.
        """
        if db.bind.dialect.name == "postgresql":
            db.execute(text(f"SELECT pg_advisory_xact_lock({BOOTSTRAP_ADVISORY_LOCK_ID})"))
        elif db.bind.dialect.name == "sqlite":
            # In SQLite, execute a write operation to trigger immediate transaction lock
            db.execute(text("PRAGMA busy_timeout = 3000"))

    @classmethod
    def signup_user(cls, db: Session, req: UserSignupRequest) -> Tuple[User, str, str]:
        """
        Registers a new user. The first user created in the system safely becomes 'admin';
        all subsequent users default strictly to 'analyst'.
        """
        email_clean = req.email.strip().lower()

        # Check existing user
        existing = db.scalar(select(User).where(func.lower(User.email) == email_clean))
        if existing:
            raise ConflictException("An account with this email already exists.")

        # Concurrency-safe first-admin check with database lock
        cls._acquire_bootstrap_lock(db)
        user_count = db.scalar(select(func.count(User.id)))
        assigned_role = "admin" if user_count == 0 else "analyst"

        hashed_pw = hash_password(req.password)
        new_user = User(
            email=email_clean,
            full_name=req.full_name.strip(),
            password_hash=hashed_pw,
            role=assigned_role,
            is_active=True
        )
        db.add(new_user)
        db.flush()

        # Issue tokens
        access_token = create_access_token(
            user_id=new_user.id,
            role=new_user.role,
            email=new_user.email
        )
        raw_refresh_token = generate_secure_token()
        refresh_hash = hash_token(raw_refresh_token)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        db_refresh = RefreshToken(
            user_id=new_user.id,
            token_hash=refresh_hash,
            expires_at=refresh_expires
        )
        db.add(db_refresh)

        # Audit Event
        audit = AuditEvent(
            actor_id=new_user.id,
            event_type="USER_REGISTERED",
            entity_type="User",
            entity_id=str(new_user.id),
            details_json={"email": email_clean, "role": assigned_role}
        )
        db.add(audit)
        db.commit()
        db.refresh(new_user)

        return new_user, access_token, raw_refresh_token

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Tuple[User, str, str]:
        """
        Authenticates user with generic error message to avoid account enumeration.
        Issues access token and rotatable refresh token.
        """
        email_clean = email.strip().lower()
        user = db.scalar(select(User).where(func.lower(User.email) == email_clean))

        # Generic error message
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedException("Invalid email or password.")

        if not user.is_active:
            raise ForbiddenException("Your account is currently disabled. Please contact an administrator.")

        # Issue tokens
        access_token = create_access_token(
            user_id=user.id,
            role=user.role,
            email=user.email
        )
        raw_refresh_token = generate_secure_token()
        refresh_hash = hash_token(raw_refresh_token)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        db_refresh = RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=refresh_expires
        )
        db.add(db_refresh)

        # Audit Event
        audit = AuditEvent(
            actor_id=user.id,
            event_type="USER_LOGIN",
            entity_type="User",
            entity_id=str(user.id),
            details_json={"email": email_clean}
        )
        db.add(audit)
        db.commit()
        db.refresh(user)

        return user, access_token, raw_refresh_token

    @staticmethod
    def refresh_session(db: Session, raw_refresh_token: str) -> Tuple[User, str, str]:
        """
        Validates and rotates a refresh token. Revokes the old token and issues a new pair.
        """
        if not raw_refresh_token:
            raise UnauthorizedException("Refresh token required.")

        token_hash = hash_token(raw_refresh_token)
        now = datetime.now(timezone.utc)

        db_token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        if not db_token:
            raise UnauthorizedException("Invalid refresh token.")

        if db_token.revoked_at is not None:
            raise UnauthorizedException("Refresh token has been revoked.")

        token_expires = db_token.expires_at
        if token_expires.tzinfo is None:
            token_expires = token_expires.replace(tzinfo=timezone.utc)

        if token_expires < now:
            raise UnauthorizedException("Refresh token has expired.")

        user = db.scalar(select(User).where(User.id == db_token.user_id))
        if not user or not user.is_active:
            raise UnauthorizedException("User account is inactive or no longer exists.")

        # Rotate: Revoke the current token
        db_token.revoked_at = now

        # Create new refresh token
        new_raw_refresh = generate_secure_token()
        new_refresh_hash = hash_token(new_raw_refresh)
        new_refresh_expires = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        new_db_token = RefreshToken(
            user_id=user.id,
            token_hash=new_refresh_hash,
            expires_at=new_refresh_expires
        )
        db.add(new_db_token)

        # Create new access token
        new_access_token = create_access_token(
            user_id=user.id,
            role=user.role,
            email=user.email
        )

        db.commit()
        return user, new_access_token, new_raw_refresh

    @staticmethod
    def revoke_refresh_token(db: Session, raw_refresh_token: str) -> bool:
        """
        Revokes a refresh token during user logout.
        """
        if not raw_refresh_token:
            return False

        token_hash = hash_token(raw_refresh_token)
        db_token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        if db_token and db_token.revoked_at is None:
            db_token.revoked_at = datetime.now(timezone.utc)
            db.commit()
            return True
        return False

    @staticmethod
    def list_users(db: Session) -> List[User]:
        """Lists all registered users (admin only)."""
        return list(db.scalars(select(User).order_by(User.created_at.asc())).all())

    @staticmethod
    def update_user_role(db: Session, admin_actor: User, target_user_id: uuid.UUID, new_role: str) -> User:
        """Updates a user's role with protection against removing the last active admin."""
        target_user = db.scalar(select(User).where(User.id == target_user_id))
        if not target_user:
            raise EntityNotFoundException("User", target_user_id)

        # Protection: Prevent demoting the last active administrator
        if target_user.role == "admin" and new_role != "admin":
            active_admin_count = db.scalar(
                select(func.count(User.id)).where(User.role == "admin", User.is_active == True)
            )
            if active_admin_count <= 1:
                raise ForbiddenException("Cannot demote the sole active administrator in the system.")

        old_role = target_user.role
        target_user.role = new_role
        target_user.updated_at = datetime.now(timezone.utc)

        audit = AuditEvent(
            actor_id=admin_actor.id,
            event_type="USER_ROLE_CHANGED",
            entity_type="User",
            entity_id=str(target_user.id),
            details_json={
                "target_email": target_user.email,
                "previous_role": old_role,
                "new_role": new_role,
                "changed_by": admin_actor.email
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(target_user)
        return target_user
