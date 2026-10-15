"""Authentication API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, http_bearer
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.schemas.user import UserResponse
from app.services.auth_service import auth_service

router = APIRouter(tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with Argon2 password hashing.",
)
@limiter.limit("10/minute")
async def register(
    request: Request,
    data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register a new user account with rate limiting."""
    user = await auth_service.register_user(db=db, data=data)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in user",
    description="Authenticate user with email and password to receive access and refresh tokens.",
)
@limiter.limit("15/minute")
async def login(
    request: Request,
    data: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user credentials and issue tokens with rate limiting."""
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    _, token_response = await auth_service.authenticate_user(
        db=db,
        data=data,
        user_agent=user_agent,
        ip_address=client_ip,
    )
    return token_response


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Validate refresh token and generate a new access token.",
)
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Issue a new access token using a valid, non-revoked refresh token."""
    return await auth_service.refresh_access_token(
        db=db,
        refresh_token_str=data.refresh_token,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Log out user",
    description="Revoke the provided refresh token or all user refresh sessions.",
)
async def logout(
    data: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Revoke refresh token and invalidate user session."""
    await auth_service.logout_user(
        db=db,
        refresh_token_str=data.refresh_token,
    )
    return MessageResponse(message="Successfully logged out.")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Retrieve the profile of the currently authenticated user.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the authenticated user profile."""
    return UserResponse.model_validate(current_user)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Request a secure password reset link via email.",
)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Request password reset link."""
    return await auth_service.request_password_reset(db=db, data=data)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm password reset",
    description="Confirm password reset using token and new password.",
)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Complete password reset using valid reset token."""
    return await auth_service.confirm_password_reset(db=db, data=data)

