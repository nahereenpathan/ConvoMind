"""Comprehensive integration and unit tests for Authentication and User Management."""

import uuid
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from sqlalchemy import update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.main import app
from app.models.user import User


@pytest.mark.asyncio
async def test_successful_registration():
    """Verify registration creates a user, returns 201, and excludes password."""
    unique_email = f"reg_success_{uuid.uuid4().hex[:8]}@convomind.ai"
    payload = {
        "name": "Sarah Connor",
        "email": unique_email,
        "password": "Password123!",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == unique_email.lower()
    assert data["full_name"] == "Sarah Connor"
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_duplicate_email_registration():
    """Verify registering an already registered email returns 400 Bad Request."""
    unique_email = f"duplicate_{uuid.uuid4().hex[:8]}@convomind.ai"
    payload = {
        "name": "John Connor",
        "email": unique_email,
        "password": "SecurePassword1!",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # First registration
        resp1 = await client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        # Second registration with same email
        resp2 = await client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 409
        assert "already registered" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_email_format():
    """Verify invalid email formats are rejected with 422 Unprocessable Entity."""
    payload = {
        "name": "Invalid Email User",
        "email": "not-an-email",
        "password": "StrongPassword1!",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "weak_password,reason",
    [
        ("Short1!", "too short"),
        ("lowercase1!", "missing uppercase"),
        ("UPPERCASE1!", "missing lowercase"),
        ("NoDigitsHere!", "missing digit"),
        ("NoSpecialChar1", "missing special character"),
    ],
)
async def test_weak_password_validation(weak_password, reason):
    """Verify weak passwords failing security policy return 422."""
    payload = {
        "name": "Policy User",
        "email": f"policy_{uuid.uuid4().hex[:6]}@convomind.ai",
        "password": weak_password,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_successful_login_and_token_structure():
    """Verify login issues valid access and refresh tokens."""
    email = f"login_test_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "CorrectPassword123!"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Register user
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={"name": "Alice Wonderland", "email": email, "password": password},
        )
        assert reg_resp.status_code == 201

        # Login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )

    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["expires_in"] == settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


@pytest.mark.asyncio
async def test_login_wrong_password():
    """Verify invalid credentials return 401 Unauthorized."""
    email = f"wrong_pwd_{uuid.uuid4().hex[:8]}@convomind.ai"
    correct_password = "CorrectPassword123!"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/auth/register",
            json={"name": "Bob", "email": email, "password": correct_password},
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword999!"},
        )

    assert response.status_code == 401
    assert "invalid email or password" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_nonexistent_user():
    """Verify non-existent user login returns 401 Unauthorized."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@convomind.ai", "password": "RandomPassword1!"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_me_endpoint_success():
    """Verify GET /api/v1/auth/me returns current authenticated user profile."""
    email = f"me_test_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "MySecurePass123!"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/auth/register",
            json={"name": "Diana Prince", "email": email, "password": password},
        )

        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        access_token = login_resp.json()["access_token"]

        # Call /me with Bearer token
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert me_resp.status_code == 200
    user_data = me_resp.json()
    assert user_data["email"] == email.lower()
    assert user_data["full_name"] == "Diana Prince"
    assert "hashed_password" not in user_data


@pytest.mark.asyncio
async def test_protected_me_endpoint_missing_or_invalid_token():
    """Verify accessing /me without or with invalid token returns 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # No header
        resp1 = await client.get("/api/v1/auth/me")
        assert resp1.status_code == 401

        # Invalid bearer format
        resp2 = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_protected_me_endpoint_expired_token():
    """Verify expired token returns 401 with expiration error."""
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    expired_payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "exp": expired_time,
        "iat": expired_time - timedelta(minutes=30),
    }
    expired_token = jwt.encode(
        expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_token_flow():
    """Verify refresh token issues a new access token, and rejects invalid token types."""
    email = f"refresh_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "RefreshTokenPass1!"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/auth/register",
            json={"name": "Bruce Wayne", "email": email, "password": password},
        )
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        tokens = login_resp.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # Attempt to use access_token at refresh endpoint (must fail)
        bad_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert bad_refresh.status_code == 401
        assert "refresh token required" in bad_refresh.json()["detail"].lower()

        # Valid refresh token
        good_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert good_refresh.status_code == 200
        new_tokens = good_refresh.json()
        assert "access_token" in new_tokens
        assert new_tokens["access_token"] != access_token

        # Verify new access token works on /me
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
        )
        assert me_resp.status_code == 200


@pytest.mark.asyncio
async def test_logout_and_revocation_flow():
    """Verify logout revokes the refresh token and prevents further refreshing."""
    email = f"logout_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "LogoutPassword1!"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/auth/register",
            json={"name": "Clark Kent", "email": email, "password": password},
        )
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Log out with refresh token
        logout_resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert logout_resp.status_code == 200
        assert "logged out" in logout_resp.json()["message"].lower()

        # Attempt to use revoked refresh token
        refresh_after_logout = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_after_logout.status_code == 401
        assert "revoked" in refresh_after_logout.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deactivated_user_blocked_from_login():
    """Verify deactivated user receives 403 Forbidden on login attempt."""
    email = f"deact_login_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "DeactivatedUserPass1!"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={"name": "Inactive User", "email": email, "password": password},
        )
        assert reg_resp.status_code == 201
        user_id = uuid.UUID(reg_resp.json()["id"])

        # Deactivate user directly in the database
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(User).where(User.id == user_id).values(is_active=False)
            )
            await session.commit()

        # Attempt login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 403
        assert "deactivated" in login_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deactivated_user_blocked_from_protected_endpoint():
    """Verify deactivated user's access token is rejected with 403 on protected routes."""
    email = f"deact_me_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "DeactivatedMePass1!"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/auth/register",
            json={"name": "Inactive Me", "email": email, "password": password},
        )
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        access_token = login_resp.json()["access_token"]
        user_id = uuid.UUID(login_resp.json().get("user_id") or jwt.decode(
            access_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )["sub"])

        # Deactivate user in database
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(User).where(User.id == user_id).values(is_active=False)
            )
            await session.commit()

        # Attempt to access /me
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_resp.status_code == 403
        assert "deactivated" in me_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deactivated_user_cannot_refresh_token():
    """Verify refresh token of a deactivated user is rejected with 401."""
    email = f"deact_refresh_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "DeactivatedRefreshPass1!"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/auth/register",
            json={"name": "Inactive Refresh", "email": email, "password": password},
        )
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        tokens = login_resp.json()
        refresh_token = tokens["refresh_token"]
        payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = uuid.UUID(payload["sub"])

        # Deactivate user in database
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(User).where(User.id == user_id).values(is_active=False)
            )
            await session.commit()

        # Attempt refresh
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 401
        assert "inactive" in refresh_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_malformed_refresh_token():
    """Verify invalid format or non-JWT refresh token is rejected with 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not.a.valid.jwt"},
        )
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_token_malformed_sub_claim():
    """Verify forged refresh token with invalid UUID sub claim returns 401."""
    now = datetime.now(timezone.utc)
    forged_payload = {
        "sub": "not-a-valid-uuid",
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "exp": now + timedelta(days=7),
        "iat": now,
    }
    forged_token = jwt.encode(
        forged_payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": forged_token},
        )
        assert resp.status_code == 401
        assert "revoked or is invalid" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_forgot_and_reset_password_flow():
    """Verify forgot password request, reset token confirmation, and new password login."""
    email = f"reset_{uuid.uuid4().hex[:8]}@convomind.ai"
    old_password = "OldPassword123!"
    new_password = "NewPassword456!"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Register
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={"name": "Reset Test User", "email": email, "password": old_password},
        )
        assert reg_resp.status_code == 201

        # 2. Forgot password request
        forgot_resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": email},
        )
        assert forgot_resp.status_code == 200
        assert "password reset link has been sent" in forgot_resp.json()["message"].lower()

        # Fetch reset token directly from DB for test confirmation
        from app.models.password_reset_token import PasswordResetToken
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            stmt = select(PasswordResetToken).order_by(PasswordResetToken.created_at.desc())
            res = await session.execute(stmt)
            token_record = res.scalars().first()
            assert token_record is not None

        # 3. Reset password using generated token
        # Using service layer confirm directly or secret token
        from app.services.auth_service import auth_service
        from app.schemas.auth import ResetPasswordRequest
        # Create a fresh reset token via service
        import secrets
        from app.core.security import hash_token
        from datetime import datetime, timedelta, timezone

        raw_token = secrets.token_urlsafe(32)
        t_hash = hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        async with AsyncSessionLocal() as session:
            user_stmt = select(User).where(User.email == email.lower())
            user_res = await session.execute(user_stmt)
            usr = user_res.scalar_one()

            rt = PasswordResetToken(user_id=usr.id, token_hash=t_hash, expires_at=expires_at, is_used=False)
            session.add(rt)
            await session.commit()

        reset_resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw_token, "new_password": new_password},
        )
        assert reset_resp.status_code == 200

        # 4. Old password fails
        old_login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": old_password},
        )
        assert old_login.status_code == 401

        # 5. New password succeeds
        new_login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": new_password},
        )
        assert new_login.status_code == 200
        assert "access_token" in new_login.json()


@pytest.mark.asyncio
async def test_case_insensitive_email_login():
    """Verify signup with mixed-case email allows login with uppercase/lowercase email variants."""
    mixed_email = f"MixCase_{uuid.uuid4().hex[:6]}@ConvoMind.AI"
    password = "MixedCasePass1!"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Register with mixed case
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={"name": "Mixed Case User", "email": mixed_email, "password": password},
        )
        assert reg_resp.status_code == 201

        # Login with ALL UPPERCASE
        login_upper = await client.post(
            "/api/v1/auth/login",
            json={"email": mixed_email.upper(), "password": password},
        )
        assert login_upper.status_code == 200

        # Login with all lowercase
        login_lower = await client.post(
            "/api/v1/auth/login",
            json={"email": mixed_email.lower(), "password": password},
        )
        assert login_lower.status_code == 200


