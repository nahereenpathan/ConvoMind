"""API authentication and authorization dependencies."""

import uuid
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

# HTTPBearer security scheme for OpenAPI documentation and token extraction
http_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Provide the JWT Bearer access token: Bearer <token>",
)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that extracts and validates the JWT access token and loads the authenticated user."""
    unauthorized_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (jwt.PyJWTError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Access token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise unauthorized_exc

    try:
        user_uuid = uuid.UUID(sub)
    except ValueError as exc:
        raise unauthorized_exc from exc

    stmt = select(User).where(User.id == user_uuid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise unauthorized_exc

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


# Re-export workspace dependencies for convenience
from app.api.dependencies.workspace import (  # noqa: E402
    get_workspace_and_membership,
    require_workspace_admin_or_owner,
    require_workspace_member,
    require_workspace_owner,
    require_workspace_role,
)

# Re-export meeting dependencies for convenience
from app.api.dependencies.meeting import (  # noqa: E402
    get_any_meeting_and_membership,
    get_meeting_and_membership,
    get_trashed_meeting_and_membership,
    require_meeting_delete_permission,
    require_meeting_update_permission,
    require_trashed_meeting_permission,
)


