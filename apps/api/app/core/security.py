"""Security, cryptography, and token handling utilities."""

import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, Union
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

# Initialize Argon2 password hasher with secure defaults
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against an Argon2 hash. Returns False on mismatch/invalid hash."""
    if not hashed_password or not plain_password:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_strength(password: str) -> None:
    """Validate password strength according to security policy.

    Raises ValueError with a clear message if requirements are not met.
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(password) > 128:
        raise ValueError("Password must not exceed 128 characters.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one digit.")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", password):
        raise ValueError(
            "Password must contain at least one special character (!@#$%^&* etc.)."
        )


def create_access_token(
    user_id: Union[UUID, str],
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a short-lived JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "exp": expire,
        "iat": now,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    user_id: Union[UUID, str],
) -> Tuple[str, str, datetime]:
    """Generate a long-lived JWT refresh token with unique JTI.

    Returns:
        Tuple of (token_string, jti, expiration_datetime)
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    token_jti = str(uuid.uuid4())
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": token_jti,
        "exp": expire,
        "iat": now,
    }
    token_str = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token_str, token_jti, expire


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token signature and expiration.

    Raises:
        jwt.ExpiredSignatureError: If token is expired.
        jwt.PyJWTError: If token is malformed or invalid.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def hash_token(token: str) -> str:
    """Calculate SHA-256 digest of a token string for safe database lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
