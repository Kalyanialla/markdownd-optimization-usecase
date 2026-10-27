"""
Authentication endpoints: signup, login, logout, refresh, and current user profile.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Response, Request, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.permissions import get_current_user
from backend.app.db.session import get_db
from backend.app.db.models.user import User
from backend.app.schemas.user import (
    UserSignupRequest,
    UserLoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse
)
from backend.app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Sets secure, HttpOnly SameSite cookies for browser sessions."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )


def clear_auth_cookies(response: Response):
    """Clears authentication cookies upon logout."""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(req: UserSignupRequest, response: Response, db: Session = Depends(get_db)):
    """
    Public signup. Discards client-supplied roles; first user created becomes admin,
    subsequent users default to analyst. Returns bearer tokens and sets cookies.
    """
    user, access_token, refresh_token = AuthService.signup_user(db, req)
    set_auth_cookies(response, access_token, refresh_token)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: UserLoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    Authenticates user and returns JWT access token and rotatable refresh token.
    """
    user, access_token, refresh_token = AuthService.authenticate_user(db, req.email, req.password)
    set_auth_cookies(response, access_token, refresh_token)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    body: Optional[RefreshTokenRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Rotates a valid refresh token and issues a new access token.
    Accepts token via JSON body or HttpOnly cookie.
    """
    raw_token = None
    if body and body.refresh_token:
        raw_token = body.refresh_token
    elif "refresh_token" in request.cookies:
        raw_token = request.cookies.get("refresh_token")

    user, new_access, new_refresh = AuthService.refresh_session(db, raw_token)
    set_auth_cookies(response, new_access, new_refresh)
    
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    body: Optional[RefreshTokenRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Revokes the refresh token in the database and clears cookies.
    """
    raw_token = None
    if body and body.refresh_token:
        raw_token = body.refresh_token
    elif "refresh_token" in request.cookies:
        raw_token = request.cookies.get("refresh_token")

    AuthService.revoke_refresh_token(db, raw_token)
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the authenticated user's profile and active role.
    """
    return UserResponse.model_validate(current_user)
