"""
User management endpoints (admin only).
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.permissions import require_roles
from backend.app.db.session import get_db
from backend.app.db.models.user import User
from backend.app.schemas.user import UserResponse, UserRoleUpdateRequest
from backend.app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_model=List[UserResponse])
async def list_users(
    admin_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Lists all registered users in the system. Requires 'admin' role.
    """
    users = AuthService.list_users(db)
    return [UserResponse.model_validate(u) for u in users]


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    req: UserRoleUpdateRequest,
    admin_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Updates a user's role (admin, analyst, approver). Requires 'admin' role.
    Prevents demoting the last active administrator.
    """
    updated_user = AuthService.update_user_role(db, admin_user, user_id, req.role)
    return UserResponse.model_validate(updated_user)
