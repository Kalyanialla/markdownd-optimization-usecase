"""
Pydantic schemas for authentication and user management.
"""

import uuid
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserSignupRequest(BaseModel):
    # Note: Public signup does NOT accept a role; role is assigned safely by the backend.
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Password must be at least 8 characters")
    full_name: str = Field(..., min_length=2, max_length=255)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # in seconds
    user: UserResponse


class UserRoleUpdateRequest(BaseModel):
    role: Literal["admin", "analyst", "approver"]
