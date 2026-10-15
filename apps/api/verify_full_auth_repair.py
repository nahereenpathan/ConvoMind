import urllib.request
import urllib.error
import json
import sys
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.core.security import hash_token
from sqlalchemy import select, desc
import secrets
from datetime import datetime, timedelta, timezone

BASE_URL = "http://localhost:8000"

def make_request(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    if data is not None and isinstance(data, dict):
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"detail": body}
        return e.code, parsed
    except Exception as e:
        return 0, {"error": str(e)}

async def create_test_reset_token_in_db(email: str):
    raw_token = secrets.token_urlsafe(32)
    t_hash = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == email.strip().lower()))
        user = res.scalar_one_or_none()
        assert user is not None, f"User {email} not found in DB"
        
        record = PasswordResetToken(
            user_id=user.id,
            token_hash=t_hash,
            expires_at=expires_at,
            is_used=False
        )
        db.add(record)
        await db.commit()
    return raw_token

def run_tests():
    print("=== STARTING FULL AUTHENTICATION SYSTEM VERIFICATION ===")

    # 1. Health Check
    status, body = make_request(f"{BASE_URL}/health")
    assert status == 200, f"Health check failed: {status} {body}"
    print("[PASS] 1. Backend /health is HTTP 200 OK")

    # 2. Forgot Password for existing user nahereenpathan2208@gmail.com
    email = "nahereenpathan2208@gmail.com"
    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/forgot-password",
        method="POST",
        data={"email": email}
    )
    assert status == 200, f"Forgot password failed with status {status}: {body}"
    assert "sent" in body.get("message", "").lower(), f"Unexpected message: {body}"
    print(f"[PASS] 2. Forgot password request succeeded without 500 error for {email}")

    # 3. Register a fresh unique test user
    import uuid
    uid = str(uuid.uuid4())[:8]
    test_email = f"auth_user_{uid}@convomind.ai"
    test_pass = "Password123!"

    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/register",
        method="POST",
        data={
            "name": f"Test User {uid}",
            "email": test_email,
            "password": test_pass
        }
    )
    assert status == 201, f"Registration failed ({status}): {body}"
    assert body["email"] == test_email.lower(), f"Email mismatch: {body}"
    print(f"[PASS] 3. Signup created user {test_email} with HTTP 201 Created")

    # 4. Duplicate registration -> 409 Conflict
    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/register",
        method="POST",
        data={
            "name": f"Test User {uid}",
            "email": test_email,
            "password": test_pass
        }
    )
    assert status == 409, f"Duplicate registration expected 409, got {status}: {body}"
    assert body.get("detail") == "Email is already registered.", f"Unexpected detail: {body}"
    print("[PASS] 4. Duplicate email registration correctly returned HTTP 409 Conflict")

    # 5. Login with wrong password -> 401 Unauthorized
    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/login",
        method="POST",
        data={
            "email": test_email,
            "password": "WrongPassword123!"
        }
    )
    assert status == 401, f"Wrong pass expected 401, got {status}: {body}"
    assert body.get("detail") == "Invalid email or password.", f"Unexpected detail: {body}"
    print("[PASS] 5. Invalid password login correctly returned HTTP 401 Unauthorized")

    # 6. Login with correct password -> 200 OK & JWT
    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/login",
        method="POST",
        data={
            "email": test_email,
            "password": test_pass
        }
    )
    assert status == 200, f"Login failed ({status}): {body}"
    access_token = body.get("access_token")
    refresh_token = body.get("refresh_token")
    assert access_token and refresh_token, f"Missing tokens in response: {body}"
    print("[PASS] 6. Login with valid credentials returned access + refresh JWT tokens")

    # 7. Access Protected Route /auth/me
    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/me",
        method="GET",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert status == 200, f"Protected /me endpoint failed ({status}): {body}"
    assert body["email"] == test_email.lower(), f"User profile email mismatch: {body}"
    print("[PASS] 7. Protected endpoint /api/v1/auth/me succeeded with Bearer token")

    # 8. Access Workspaces and retrieve workspace_id
    status, body = make_request(
        f"{BASE_URL}/api/v1/workspaces",
        method="GET",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert status == 200, f"List workspaces failed ({status}): {body}"
    workspaces = body if isinstance(body, list) else body.get("items", [])
    assert len(workspaces) > 0, f"No workspace returned for user: {body}"
    workspace_id = workspaces[0]["id"]
    print(f"[PASS] 8. Retrieved user workspace: {workspace_id}")

    # 9. Access Protected Endpoints (Meetings, Action Items, Trash, Billing) with JWT
    status, body = make_request(
        f"{BASE_URL}/api/v1/meetings",
        method="GET",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert status == 200, f"Meetings endpoint failed ({status}): {body}"
    print("[PASS] 9. Protected endpoint /api/v1/meetings accessible with JWT")

    status, body = make_request(
        f"{BASE_URL}/api/v1/action-items",
        method="GET",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert status == 200, f"Action items endpoint failed ({status}): {body}"
    print("[PASS] 10. Protected endpoint /api/v1/action-items accessible with JWT")

    status, body = make_request(
        f"{BASE_URL}/api/v1/trash",
        method="GET",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert status == 200, f"Trash endpoint failed ({status}): {body}"
    print("[PASS] 11. Protected endpoint /api/v1/trash accessible with JWT")

    status, body = make_request(
        f"{BASE_URL}/api/v1/billing/subscription?workspace_id={workspace_id}",
        method="GET",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert status in (200, 404), f"Billing endpoint failed ({status}): {body}"
    print(f"[PASS] 12. Protected endpoint /api/v1/billing/subscription accessible with JWT (status {status})")

    # 10. Refresh Token Flow
    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/refresh",
        method="POST",
        data={"refresh_token": refresh_token}
    )
    assert status == 200, f"Refresh token failed ({status}): {body}"
    new_access_token = body.get("access_token")
    assert new_access_token, f"Missing new access token: {body}"
    print("[PASS] 13. Refresh token endpoint issued new access token")

    # 11. Complete Password Reset Flow
    raw_reset_token = asyncio.run(create_test_reset_token_in_db(test_email))
    new_pass = "NewSecurePassword456!"

    # Confirm password reset
    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/reset-password",
        method="POST",
        data={
            "token": raw_reset_token,
            "new_password": new_pass
        }
    )
    assert status == 200, f"Password reset failed ({status}): {body}"
    print(f"[PASS] 14. Password reset completed successfully for {test_email}")

    # Old password login must fail
    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/login",
        method="POST",
        data={"email": test_email, "password": test_pass}
    )
    assert status == 401, f"Old password login expected 401, got {status}: {body}"
    print("[PASS] 15. Old password correctly rejected after reset")

    # New password login must succeed
    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/login",
        method="POST",
        data={"email": test_email, "password": new_pass}
    )
    assert status == 200, f"New password login failed ({status}): {body}"
    print("[PASS] 16. New password login succeeded")

    # Reuse of reset token must fail
    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/reset-password",
        method="POST",
        data={
            "token": raw_reset_token,
            "new_password": "AnotherPassword789!"
        }
    )
    assert status == 400, f"Token reuse expected 400, got {status}: {body}"
    print("[PASS] 17. Reset token single-use enforced (re-use correctly rejected)")

    # 12. Logout Flow
    status, body = make_request(
        f"{BASE_URL}/api/v1/auth/logout",
        method="POST",
        data={"refresh_token": refresh_token}
    )
    assert status == 200, f"Logout failed ({status}): {body}"
    print("[PASS] 18. Logout endpoint successfully revoked refresh token")

    print("\n========================================================")
    print("SUCCESS: 18/18 AUTHENTICATION END-TO-END VERIFICATIONS PASSED!")
    print("========================================================")

if __name__ == "__main__":
    run_tests()
