"""Live HTTP Verification Script for ConvoMind Authentication.

Executes real HTTP requests against the running FastAPI application
using Python's standard urllib to verify all auth flows end-to-end.
"""

import json
import sys
import urllib.error
import urllib.request
import uuid

BASE_URL = "http://127.0.0.1:8000"


def http_request(method: str, path: str, data: dict = None, headers: dict = None):
    url = f"{BASE_URL}{path}"
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed


def run_verification():
    print("=" * 60)
    print("STARTING LIVE HTTP AUTHENTICATION VERIFICATION")
    print(f"Target: {BASE_URL}")
    print("=" * 60)

    passed = 0
    total = 0

    def assert_test(condition: bool, test_name: str, detail: str = ""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"  [PASS] {test_name}")
        else:
            print(f"  [FAIL] {test_name}: {detail}")
            sys.exit(1)

    # 1. Health Endpoints
    print("\n--- Phase 1: Service Health Checks ---")
    status, body = http_request("GET", "/health")
    assert_test(status == 200 and body.get("status") == "healthy", "GET /health is 200 healthy")

    status, body = http_request("GET", "/api/v1/health")
    assert_test(status == 200 and body.get("service") == "convoMind-api", "GET /api/v1/health is 200")

    # 2. Registration Flow
    print("\n--- Phase 2: User Registration Flow ---")
    unique_id = uuid.uuid4().hex[:8]
    email = f"live_test_{unique_id}@convomind.ai"
    password = "LivePassword123!"
    full_name = "Live Test User"

    status, body = http_request("POST", "/api/v1/auth/register", {
        "name": full_name,
        "email": email,
        "password": password,
    })
    assert_test(status == 201, f"POST /register creates user with 201 (got {status})", str(body))
    assert_test(body.get("email") == email.lower(), "Registration returns correct email")
    assert_test(body.get("full_name") == full_name, "Registration returns correct full name")
    assert_test(body.get("is_active") is True, "Registration user is_active == True")
    assert_test("id" in body, "Registration user returns uuid id")
    assert_test("password" not in body and "hashed_password" not in body, "Passwords excluded from response")
    user_id = body.get("id")

    # Duplicate registration
    status, body = http_request("POST", "/api/v1/auth/register", {
        "name": full_name,
        "email": email,
        "password": password,
    })
    assert_test(status in (400, 409), f"Duplicate registration returns 400/409 (got {status})")

    # Invalid email validation
    status, body = http_request("POST", "/api/v1/auth/register", {
        "name": "Invalid",
        "email": "not-a-valid-email",
        "password": password,
    })
    assert_test(status == 422, f"Invalid email format returns 422 (got {status})")

    # Weak password validation
    status, body = http_request("POST", "/api/v1/auth/register", {
        "name": "Weak",
        "email": f"weak_{unique_id}@convomind.ai",
        "password": "weak",
    })
    assert_test(status == 422, f"Weak password returns 422 (got {status})")

    # 3. Authentication / Login Flow
    print("\n--- Phase 3: Login & Token Issuance Flow ---")
    status, body = http_request("POST", "/api/v1/auth/login", {
        "email": email,
        "password": password,
    })
    assert_test(status == 200, f"POST /login with valid credentials returns 200 (got {status})")
    access_token = body.get("access_token")
    refresh_token = body.get("refresh_token")
    token_type = body.get("token_type")
    expires_in = body.get("expires_in")
    assert_test(bool(access_token), "Access token present in login response")
    assert_test(bool(refresh_token), "Refresh token present in login response")
    assert_test(token_type == "bearer", f"Token type is bearer (got {token_type})")
    assert_test(expires_in == 1800, f"Expires in is 1800s (got {expires_in})")

    # Login with wrong password
    status, body = http_request("POST", "/api/v1/auth/login", {
        "email": email,
        "password": "WrongPassword999!",
    })
    assert_test(status == 401, f"Login with wrong password returns 401 (got {status})")

    # Login with nonexistent email
    status, body = http_request("POST", "/api/v1/auth/login", {
        "email": "nonexistent_404@convomind.ai",
        "password": password,
    })
    assert_test(status == 401, f"Login with nonexistent email returns 401 (got {status})")

    # 4. Protected Route Flow (/api/v1/auth/me)
    print("\n--- Phase 4: Protected Profile Access (/me) ---")
    status, body = http_request("GET", "/api/v1/auth/me", headers={
        "Authorization": f"Bearer {access_token}"
    })
    assert_test(status == 200, f"GET /me with Bearer token returns 200 (got {status})")
    assert_test(body.get("email") == email.lower(), "/me returns current user email")
    assert_test(body.get("id") == user_id, "/me returns current user ID")
    assert_test("hashed_password" not in body, "/me does not leak hashed password")

    # Access without header
    status, body = http_request("GET", "/api/v1/auth/me")
    assert_test(status == 401, f"GET /me without authorization header returns 401 (got {status})")

    # Access with bogus token
    status, body = http_request("GET", "/api/v1/auth/me", headers={
        "Authorization": "Bearer not.a.valid.jwt.token"
    })
    assert_test(status == 401, f"GET /me with bogus token returns 401 (got {status})")

    # 5. Token Refresh Flow
    print("\n--- Phase 5: Token Refresh Flow ---")
    # Reject access token on refresh endpoint
    status, body = http_request("POST", "/api/v1/auth/refresh", {
        "refresh_token": access_token
    })
    assert_test(status == 401, f"POST /refresh with access token rejected with 401 (got {status})")

    # Valid refresh token
    status, body = http_request("POST", "/api/v1/auth/refresh", {
        "refresh_token": refresh_token
    })
    assert_test(status == 200, f"POST /refresh with valid refresh token returns 200 (got {status})")
    new_access_token = body.get("access_token")
    assert_test(bool(new_access_token), "New access token received from refresh")
    assert_test(new_access_token != access_token, "New access token is distinct from old one")

    # Verify new access token works on /me
    status, body = http_request("GET", "/api/v1/auth/me", headers={
        "Authorization": f"Bearer {new_access_token}"
    })
    assert_test(status == 200, f"GET /me with new access token succeeds with 200 (got {status})")

    # 6. Logout & Revocation Flow
    print("\n--- Phase 6: Logout & Revocation Flow ---")
    status, body = http_request("POST", "/api/v1/auth/logout", {
        "refresh_token": refresh_token
    })
    assert_test(status == 200, f"POST /logout returns 200 (got {status})")
    assert_test("logged out" in body.get("message", "").lower(), "Logout returns success confirmation")

    # Attempt to refresh with revoked refresh token
    status, body = http_request("POST", "/api/v1/auth/refresh", {
        "refresh_token": refresh_token
    })
    assert_test(status == 401, f"POST /refresh with revoked token returns 401 (got {status})")
    assert_test("revoked" in body.get("detail", "").lower(), f"Detail confirms token revoked: {body.get('detail')}")

    print("\n" + "=" * 60)
    print(f"ALL {passed}/{total} LIVE HTTP VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_verification()
