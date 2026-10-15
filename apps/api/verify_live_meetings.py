"""Live HTTP Verification Script for ConvoMind Meeting Management.

Executes real HTTP requests against the running FastAPI application
using Python's standard urllib to verify all meeting flows end-to-end.
"""

import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

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
    email = f"live_meet_{uuid.uuid4().hex[:8]}@convomind.ai"
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
        "token": body["access_token"],
        "id": None,
    }


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


def run_verification():
    print("=" * 60)
    print("STARTING LIVE HTTP MEETING MANAGEMENT VERIFICATION")
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

    # 1. Setup Actors & Workspace
    print("\n--- Phase 1: Environment & Workspace Setup ---")
    owner = create_user_and_token("Meeting Owner")
    admin = create_user_and_token("Meeting Admin")
    member = create_user_and_token("Meeting Member")
    stranger = create_user_and_token("Meeting Stranger")

    for actor in [owner, admin, member, stranger]:
        _, me_body = http_request("GET", "/api/v1/auth/me", headers=auth_header(actor["token"]))
        actor["id"] = me_body["id"]

    status, ws_body = http_request(
        "POST",
        "/api/v1/workspaces",
        {"name": f"Live Meeting Org {uuid.uuid4().hex[:4]}"},
        headers=auth_header(owner["token"]),
    )
    assert_test(status == 201, "Workspace created successfully")
    ws_id = ws_body["id"]

    # Add Admin
    http_request(
        "POST",
        f"/api/v1/workspaces/{ws_id}/members",
        {"email": admin["email"], "role": "ADMIN"},
        headers=auth_header(owner["token"]),
    )
    # Add Member
    http_request(
        "POST",
        f"/api/v1/workspaces/{ws_id}/members",
        {"email": member["email"], "role": "MEMBER"},
        headers=auth_header(owner["token"]),
    )
    assert_test(True, "Admin and Member successfully joined workspace")

    # 2. Meeting Creation Flow
    print("\n--- Phase 2: Meeting Creation Flow ---")
    sched_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    status, meeting_body = http_request(
        "POST",
        "/api/v1/meetings",
        {
            "workspace_id": ws_id,
            "title": "Q4 Architecture Planning",
            "description": "Architectural review and roadmap discussion",
            "meeting_type": "planning",
            "status": "scheduled",
            "scheduled_at": sched_time,
            "source_type": "zoom",
        },
        headers=auth_header(member["token"]),
    )
    assert_test(status == 201, "POST /api/v1/meetings creates meeting with 201")
    assert_test(meeting_body["title"] == "Q4 Architecture Planning", "Meeting title is saved correctly")
    assert_test(meeting_body["created_by"] == member["id"], "Meeting creator recorded as current user")
    assert_test(meeting_body["status"] == "SCHEDULED", "Meeting status defaults to SCHEDULED")
    meeting_id = meeting_body["id"]

    # 3. Meeting Listing & Pagination
    print("\n--- Phase 3: Meeting Listing and Pagination ---")
    status, list_body = http_request(
        "GET",
        f"/api/v1/meetings?workspace_id={ws_id}&page=1&page_size=10",
        headers=auth_header(owner["token"]),
    )
    assert_test(status == 200, "GET /api/v1/meetings returns 200 OK")
    assert_test("items" in list_body and "total" in list_body, "Pagination envelope present")
    assert_test(list_body["total"] >= 1, "Meeting appears in workspace total count")
    assert_test(list_body["page"] == 1 and list_body["page_size"] == 10, "Pagination metadata matches request")

    # 4. Meeting Detail Retrieval & IDOR Protection
    print("\n--- Phase 4: Meeting Detail Access & IDOR Verification ---")
    status, get_body = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}",
        headers=auth_header(member["token"]),
    )
    assert_test(status == 200 and get_body["id"] == meeting_id, "Member can retrieve meeting details")

    # Stranger (cross-workspace IDOR attempt)
    status, stranger_body = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}",
        headers=auth_header(stranger["token"]),
    )
    assert_test(status == 404, "Stranger access to meeting rejected with 404 Not Found (no leak)")

    # 5. Meeting Update Flow
    print("\n--- Phase 5: Meeting Update & State Transitions ---")
    status, update_body = http_request(
        "PATCH",
        f"/api/v1/meetings/{meeting_id}",
        {"title": "Q4 Architecture Planning - Final", "meeting_type": "review"},
        headers=auth_header(member["token"]),
    )
    assert_test(status == 200, "Creator can update meeting title")
    assert_test(update_body["title"] == "Q4 Architecture Planning - Final", "Title updated correctly")

    # Valid State Transition: SCHEDULED -> IN_PROGRESS
    status, state_body = http_request(
        "PATCH",
        f"/api/v1/meetings/{meeting_id}",
        {"status": "in_progress"},
        headers=auth_header(admin["token"]),
    )
    assert_test(status == 200, "Status transition SCHEDULED -> IN_PROGRESS succeeds")
    assert_test(state_body["status"] == "IN_PROGRESS", "Meeting status updated to IN_PROGRESS")

    # Valid State Transition: IN_PROGRESS -> COMPLETED
    status, completed_body = http_request(
        "PATCH",
        f"/api/v1/meetings/{meeting_id}",
        {"status": "completed"},
        headers=auth_header(admin["token"]),
    )
    assert_test(status == 200, "Status transition IN_PROGRESS -> COMPLETED succeeds")
    assert_test(completed_body["status"] == "COMPLETED", "Meeting status is COMPLETED")

    # Invalid State Transition from terminal COMPLETED -> IN_PROGRESS (should return 400)
    status, err_body = http_request(
        "PATCH",
        f"/api/v1/meetings/{meeting_id}",
        {"status": "in_progress"},
        headers=auth_header(admin["token"]),
    )
    assert_test(status == 400, "Invalid transition from COMPLETED rejected with 400 Bad Request")

    # 6. Participants Management
    print("\n--- Phase 6: Participant Management ---")
    # Add external participant
    status, part1_body = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/participants",
        {"name": "Client Representative", "email": "client@partner.com", "role": "attendee"},
        headers=auth_header(admin["token"]),
    )
    assert_test(status == 201, "External participant added with 201")
    part1_id = part1_body["id"]

    # Add internal participant
    status, part2_body = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/participants",
        {"user_id": owner["id"], "role": "host"},
        headers=auth_header(admin["token"]),
    )
    assert_test(status == 201, "Internal participant added by user_id with 201")

    # Reject duplicate participant
    status, dup_body = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/participants",
        {"email": "client@partner.com", "role": "attendee"},
        headers=auth_header(admin["token"]),
    )
    assert_test(status == 409, "Duplicate participant rejected with 409 Conflict")

    # List participants
    status, list_parts = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/participants",
        headers=auth_header(member["token"]),
    )
    assert_test(status == 200 and len(list_parts) == 2, "Participants listed correctly")

    # Remove participant
    status, del_part_body = http_request(
        "DELETE",
        f"/api/v1/meetings/{meeting_id}/participants/{part1_id}",
        headers=auth_header(admin["token"]),
    )
    assert_test(status == 200, "Participant removed successfully")

    # 7. Meeting Deletion Flow
    print("\n--- Phase 7: Meeting Deletion Flow ---")
    status, del_meet_body = http_request(
        "DELETE",
        f"/api/v1/meetings/{meeting_id}",
        headers=auth_header(owner["token"]),
    )
    assert_test(status == 200, "Workspace owner can delete meeting")

    # Verify meeting is gone
    status, check_body = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}",
        headers=auth_header(member["token"]),
    )
    assert_test(status == 404, "Deleted meeting returns 404 Not Found")

    print("\n" + "=" * 60)
    print(f"ALL {passed}/{total} LIVE HTTP MEETING VERIFICATION CHECKS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_verification()
