"""Authentication business logic and session management."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.enums import WorkspaceRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
import secrets
from app.models.password_reset_token import PasswordResetToken
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
from app.services.email import get_email_provider
from app.services.workspace_service import WorkspaceService


class AuthService:
    """Service handling user registration, authentication, token lifecycle, logout, and password resets."""

    @staticmethod
    async def register_user(
        db: AsyncSession,
        data: UserRegisterRequest,
    ) -> User:
        """Register a new user with Argon2 password hashing, duplicate prevention, and default workspace creation."""
        normalized_email = str(data.email).strip().lower()
        stmt = select(User).where(func.lower(User.email) == normalized_email)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered.",
            )

        hashed_pw = hash_password(data.password)
        new_user = User(
            email=normalized_email,
            full_name=data.name.strip(),
            hashed_password=hashed_pw,
            is_active=True,
            is_superuser=False,
        )

        try:
            db.add(new_user)
            await db.flush()  # Obtain new_user.id for workspace assignment

            # Atomically create default workspace and assign user as OWNER
            workspace_name = f"{data.name.strip()}'s Workspace" if data.name else "My Workspace"
            workspace_slug = await WorkspaceService.generate_unique_slug(db=db, name=workspace_name)

            new_workspace = Workspace(
                name=workspace_name,
                slug=workspace_slug,
                created_by_id=new_user.id,
            )
            db.add(new_workspace)
            await db.flush()  # Obtain new_workspace.id

            owner_membership = WorkspaceMember(
                workspace_id=new_workspace.id,
                user_id=new_user.id,
                role=WorkspaceRole.OWNER,
            )
            db.add(owner_membership)

            await db.commit()
            await db.refresh(new_user)
            return new_user
        except Exception as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Registration transaction failed: {exc}",
            ) from exc

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        data: UserLoginRequest,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[User, TokenResponse]:
        """Authenticate user credentials and issue access + persistent refresh tokens."""
        normalized_email = str(data.email).strip().lower()
        stmt = select(User).where(func.lower(User.email) == normalized_email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        invalid_credentials_exc = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

        if user is None or not user.hashed_password:
            raise invalid_credentials_exc

        if not verify_password(data.password, user.hashed_password):
            raise invalid_credentials_exc

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated.",
            )

        # Generate tokens
        access_token = create_access_token(user.id)
        refresh_token_str, jti, expire = create_refresh_token(user.id)

        # Persist refresh token in database for server-side revocation
        token_record = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token_str),
            jti=jti,
            expires_at=expire,
            is_revoked=False,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db.add(token_record)
        await db.commit()

        token_response = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return user, token_response

    @staticmethod
    async def refresh_access_token(
        db: AsyncSession,
        refresh_token_str: str,
    ) -> TokenResponse:
        """Validate refresh token and issue a fresh access token."""
        try:
            payload = decode_token(refresh_token_str)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired refresh token: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        token_type = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type. Refresh token required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        jti = payload.get("jti")
        sub = payload.get("sub")
        if not jti or not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed refresh token claims.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check database record by token hash
        t_hash = hash_token(refresh_token_str)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == t_hash)
        result = await db.execute(stmt)
        token_record = result.scalar_one_or_none()

        if token_record is None or token_record.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked or is invalid.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        now = datetime.now(timezone.utc)
        expires_at = token_record.expires_at
        if expires_at.tzinfo is None:
            now_cmp = now.replace(tzinfo=None)
        else:
            now_cmp = now
        if expires_at < now_cmp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate user account
        try:
            user_uuid = uuid.UUID(sub)
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed user ID in refresh token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        user_stmt = select(User).where(User.id == user_uuid)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User associated with token not found or inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Generate new access token
        new_access_token = create_access_token(user.id)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_token_str,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    async def logout_user(
        db: AsyncSession,
        refresh_token_str: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Revoke refresh token(s) upon user logout."""
        if refresh_token_str:
            t_hash = hash_token(refresh_token_str)
            stmt = (
                update(RefreshToken)
                .where(RefreshToken.token_hash == t_hash)
                .values(is_revoked=True)
            )
            await db.execute(stmt)
            await db.commit()
        elif user_id:
            stmt = (
                update(RefreshToken)
                .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False)
                .values(is_revoked=True)
            )
            await db.execute(stmt)
            await db.commit()

    @staticmethod
    async def request_password_reset(
        db: AsyncSession,
        data: ForgotPasswordRequest,
    ) -> MessageResponse:
        """Issue password reset token and dispatch email notification."""
        normalized_email = str(data.email).strip().lower()
        stmt = select(User).where(func.lower(User.email) == normalized_email)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        # Always return generic success message to prevent user enumeration attacks
        success_msg = MessageResponse(
            message="If an account with that email exists, a password reset link has been sent."
        )

        if user is None or not user.is_active:
            return success_msg

        # Generate secure reset token
        raw_token = secrets.token_urlsafe(32)
        t_hash = hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        reset_record = PasswordResetToken(
            user_id=user.id,
            token_hash=t_hash,
            expires_at=expires_at,
            is_used=False,
        )
        db.add(reset_record)
        await db.commit()

        reset_link = f"{settings.APP_BASE_URL}/reset-password?token={raw_token}"
        try:
            email_provider = get_email_provider()
            await email_provider.send_email(
                to_email=user.email,
                subject="Reset Your ConvoMind Password",
                body_text=f"Hello {user.full_name},\n\nYou requested a password reset for your ConvoMind account.\n\nPlease click the link below to set a new password:\n{reset_link}\n\nThis link expires in 1 hour.",
            )
        except Exception:
            pass

        return success_msg

    @staticmethod
    async def confirm_password_reset(
        db: AsyncSession,
        data: ResetPasswordRequest,
    ) -> MessageResponse:
        """Verify token and update user password securely."""
        t_hash = hash_token(data.token)
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == t_hash,
            PasswordResetToken.is_used == False,
        )
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if record is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token.",
            )

        now = datetime.now(timezone.utc)
        record_expiry = record.expires_at
        if record_expiry.tzinfo is None:
            record_expiry = record_expiry.replace(tzinfo=timezone.utc)

        if record_expiry < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset token has expired.",
            )

        # Load associated user
        user_stmt = select(User).where(User.id == record.user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one_or_none()

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User associated with token is not active or found.",
            )

        # Update password hash and mark token as used
        new_hash = hash_password(data.new_password)
        user.hashed_password = new_hash
        record.is_used = True

        # Revoke existing refresh sessions for security
        revoke_stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id)
            .values(is_revoked=True)
        )
        await db.execute(revoke_stmt)
        await db.commit()

        return MessageResponse(
            message="Password has been successfully reset. You may now log in with your new password."
        )


auth_service = AuthService()

