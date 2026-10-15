"""Live HTTP Verification Script for ConvoMind Workspace Management.

Executes real HTTP requests against the running FastAPI application
using Python's standard urllib to verify all workspace flows end-to-end.
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


def create_user_and_token(name: str):
    email = f"live_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "StrongPassword123!"
    status, body = http_request(
        "POST",
        "/api/v1/auth/register",
        {"name": name, "email": email, "password": password},
    )
    if status != 201:
        raise RuntimeError(f"Failed to register {email}: {body}")

    status, body = http_request(
        "POST",
        "/api/v1/auth/login",
        {"email": email, "password": password},
    )
    if status != 200:
        raise RuntimeError(f"Failed to login {email}: {body}")

    return {
        "email": email,
        "password": password,
        "token": body["access_token"],
        "id": None,
    }


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


def run_verification():
    print("=" * 60)
    print("STARTING LIVE HTTP WORKSPACE MANAGEMENT VERIFICATION")
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

    # 1. Setup Users
    print("\n--- Phase 1: Setting up Test Actors ---")
    owner = create_user_and_token("Workspace Owner")
    admin = create_user_and_token("Workspace Admin")
    member = create_user_and_token("Workspace Member")
    stranger = create_user_and_token("Workspace Stranger")

    # Fetch user IDs from /me
    for actor in [owner, admin, member, stranger]:
        _, me_body = http_request("GET", "/api/v1/auth/me", headers=auth_header(actor["token"]))
        actor["id"] = me_body["id"]

    assert_test(bool(owner["id"]), "Actors initialized with valid JWTs")

    # 2. Workspace Creation
    print("\n--- Phase 2: Workspace Creation Flow ---")
    ws_name = f"Live Workspace {uuid.uuid4().hex[:4]}"
    status, body = http_request(
        "POST",
        "/api/v1/workspaces",
        {"name": ws_name, "description": "Production verification workspace"},
        headers=auth_header(owner["token"]),
    )
    assert_test(status == 201, "POST /api/v1/workspaces returns 201 Created")
    assert_test(body["name"] == ws_name, "Workspace name matches input")
    assert_test(body["description"] == "Production verification workspace", "Workspace description saved")
    assert_test("slug" in body and body["slug"].startswith("live-workspace"), "URL slug generated properly")
    ws_id = body["id"]

    # 3. Workspace Listing & Retrieval
    print("\n--- Phase 3: Workspace Listing & Detail Access ---")
    status, body = http_request("GET", "/api/v1/workspaces", headers=auth_header(owner["token"]))
    assert_test(status == 200, "GET /api/v1/workspaces returns 200 OK")
    owner_ws_ids = [w["id"] for w in body]
    assert_test(ws_id in owner_ws_ids, "Created workspace appears in owner list")
    matching = next(w for w in body if w["id"] == ws_id)
    assert_test(matching["role"] == "OWNER", "Creator automatically assigned OWNER role")

    # Stranger listing should NOT show this workspace
    status, body = http_request("GET", "/api/v1/workspaces", headers=auth_header(stranger["token"]))
    stranger_ws_ids = [w["id"] for w in body]
    assert_test(ws_id not in stranger_ws_ids, "Unrelated user does not see private workspace")

    # Detail access
    status, body = http_request("GET", f"/api/v1/workspaces/{ws_id}", headers=auth_header(owner["token"]))
    assert_test(status == 200 and body["id"] == ws_id, "GET /api/v1/workspaces/{id} returns workspace details")

    # 4. IDOR Prevention Check
    print("\n--- Phase 4: Broken Object-Level Authorization (IDOR) Checks ---")
    status, body = http_request("GET", f"/api/v1/workspaces/{ws_id}", headers=auth_header(stranger["token"]))
    assert_test(status == 404, "Stranger access to workspace returns 404 Not Found (no leakage)")

    # 5. Workspace Update
    print("\n--- Phase 5: Workspace Updates ---")
    updated_name = f"{ws_name} Updated"
    status, body = http_request(
        "PATCH",
        f"/api/v1/workspaces/{ws_id}",
        {"name": updated_name, "description": "Updated description"},
        headers=auth_header(owner["token"]),
    )
    assert_test(status == 200 and body["name"] == updated_name, "Owner can update workspace details")

    # 6. Member Invitations & Management
    print("\n--- Phase 6: Member Invitation & Lifecycle ---")
    # Owner invites Admin
    status, body = http_request(
        "POST",
        f"/api/v1/workspaces/{ws_id}/members",
        {"email": admin["email"], "role": "ADMIN"},
        headers=auth_header(owner["token"]),
    )
    assert_test(status == 201, "Owner can invite user as ADMIN")
    assert_test(body["role"] == "ADMIN", "Role is correctly saved as ADMIN")

    # Admin invites Member
    status, body = http_request(
        "POST",
        f"/api/v1/workspaces/{ws_id}/members",
        {"email": member["email"], "role": "MEMBER"},
        headers=auth_header(admin["token"]),
    )
    assert_test(status == 201, "Admin can invite user as MEMBER")

    # Reject duplicate membership
    status, body = http_request(
        "POST",
        f"/api/v1/workspaces/{ws_id}/members",
        {"email": member["email"], "role": "MEMBER"},
        headers=auth_header(admin["token"]),
    )
    assert_test(status == 409, "Duplicate membership returns 409 Conflict")

    # Reject non-existent user
    status, body = http_request(
        "POST",
        f"/api/v1/workspaces/{ws_id}/members",
        {"email": f"ghost_{uuid.uuid4().hex[:6]}@convomind.ai", "role": "MEMBER"},
        headers=auth_header(admin["token"]),
    )
    assert_test(status == 404, "Inviting unregistered email returns 404 Not Found")

    # List members
    status, body = http_request("GET", f"/api/v1/workspaces/{ws_id}/members", headers=auth_header(member["token"]))
    assert_test(status == 200 and len(body) == 3, "Members list shows all 3 members to member")

    # 7. Authorization & Role Protection Rules
    print("\n--- Phase 7: RBAC Rules & Privilege Protection ---")
    # Member cannot update workspace
    status, body = http_request(
        "PATCH",
        f"/api/v1/workspaces/{ws_id}",
        {"name": "Hacked Name"},
        headers=auth_header(member["token"]),
    )
    assert_test(status == 403, "Regular member cannot update workspace (403 Forbidden)")

    # Admin cannot demote owner
    status, body = http_request(
        "PATCH",
        f"/api/v1/workspaces/{ws_id}/members/{owner['id']}",
        {"role": "MEMBER"},
        headers=auth_header(admin["token"]),
    )
    assert_test(status == 403, "Admin cannot demote OWNER (403 Forbidden)")

    # Admin cannot delete workspace
    status, body = http_request("DELETE", f"/api/v1/workspaces/{ws_id}", headers=auth_header(admin["token"]))
    assert_test(status == 403, "Admin cannot delete workspace (403 Forbidden)")

    # 8. Member Removal & Voluntary Departure
    print("\n--- Phase 8: Member Removal and Self-Departure ---")
    # Member leaves workspace
    status, body = http_request(
        "DELETE",
        f"/api/v1/workspaces/{ws_id}/members/{member['id']}",
        headers=auth_header(member["token"]),
    )
    assert_test(status == 200, "Member can leave workspace (self-departure)")

    # Member no longer has access
    status, body = http_request("GET", f"/api/v1/workspaces/{ws_id}", headers=auth_header(member["token"]))
    assert_test(status == 404, "Departed member cannot access workspace")

    # Owner cannot leave when sole owner
    status, body = http_request(
        "DELETE",
        f"/api/v1/workspaces/{ws_id}/members/{owner['id']}",
        headers=auth_header(owner["token"]),
    )
    assert_test(status == 400, "Sole owner cannot leave without transferring ownership (400 Bad Request)")

    # 9. Workspace Deletion
    print("\n--- Phase 9: Workspace Deletion Flow ---")
    status, body = http_request("DELETE", f"/api/v1/workspaces/{ws_id}", headers=auth_header(owner["token"]))
    assert_test(status == 200, "Owner can delete workspace (200 OK)")

    # Workspace is permanently gone
    status, body = http_request("GET", f"/api/v1/workspaces/{ws_id}", headers=auth_header(owner["token"]))
    assert_test(status == 404, "Deleted workspace returns 404 Not Found")

    print("\n" + "=" * 60)
    print(f"ALL {passed}/{total} LIVE HTTP WORKSPACE VERIFICATION CHECKS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_verification()
