"""Authentication request and response schemas."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import validate_password_strength


class UserRegisterRequest(BaseModel):
    """User registration payload."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Full name of the user",
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Strong password meeting complexity requirements",
    )

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """Normalize email address to lowercase and trimmed."""
        return str(v).strip().lower()

    @field_validator("name", mode="after")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        """Trim whitespace from user name."""
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Name must be at least 2 characters long.")
        return trimmed

    @field_validator("password", mode="after")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength rules."""
        validate_password_strength(v)
        return v


class UserLoginRequest(BaseModel):
    """User login credential payload."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="User password")

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()


class TokenResponse(BaseModel):
    """JWT access and refresh token response."""

    access_token: str = Field(..., description="Short-lived JWT access token")
    refresh_token: str = Field(..., description="Long-lived JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type identifier")
    expires_in: int = Field(
        ...,
        description="Access token validity duration in seconds",
    )


class RefreshTokenRequest(BaseModel):
    """Token refresh payload."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., description="Valid JWT refresh token")


class LogoutRequest(BaseModel):
    """Logout payload optionally containing the specific refresh token to revoke."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: Optional[str] = Field(
        default=None,
        description="Optional refresh token to revoke",
    )


class MessageResponse(BaseModel):
    """Generic status message response."""

    message: str


class ForgotPasswordRequest(BaseModel):
    """Payload for requesting a password reset email."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(..., description="Registered account email address")

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()


class ResetPasswordRequest(BaseModel):
    """Payload for completing password reset with secret token."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., description="Password reset token received via email")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New strong password",
    )

    @field_validator("new_password", mode="after")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        validate_password_strength(v)
        return v

