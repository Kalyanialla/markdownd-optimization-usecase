"""
Authentication dependencies and Role-Based Access Control (RBAC).
"""

import uuid
from typing import List, Optional
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.security import decode_access_token
from backend.app.core.exceptions import UnauthorizedException, ForbiddenException
from backend.app.db.session import get_db
from backend.app.db.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Validates JWT access token from Authorization header or HttpOnly cookie.
    Retrieves and returns the active User object.
    """
    token = None
    if auth and auth.credentials:
        token = auth.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise UnauthorizedException("Authentication token required.")

    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException("Invalid token payload: subject missing.")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise UnauthorizedException("Invalid user identifier in token.")

    user = db.scalar(select(User).where(User.id == user_uuid))
    if not user:
        raise UnauthorizedException("User associated with this token no longer exists.")
    if not user.is_active:
        raise ForbiddenException("User account is inactive.")

    return user


def require_roles(allowed_roles: List[str]):
    """
    Dependency factory enforcing role requirements (e.g. ['admin'], ['admin', 'approver']).
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                f"Action requires one of the following roles: {', '.join(allowed_roles)}. Your role is '{current_user.role}'."
            )
        return current_user

    return role_checker
