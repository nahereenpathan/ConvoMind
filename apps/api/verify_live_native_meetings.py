"""Live HTTP Verification Script for ConvoMind Native Meeting Platform (Phase 1).

Executes real HTTP requests against the running FastAPI application on http://localhost:8000
to verify all Native Meeting foundation capabilities, including lifecycle, token generation,
workspace isolation, and RBAC authorization.
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
    email = f"live_native_{uuid.uuid4().hex[:8]}@convomind.ai"
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
        "name": name,
        "email": email,
        "token": body["access_token"],
        "id": None,
    }


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


def run_live_native_verification():
    print("=" * 70)
    print("CONVOMIND NATIVE MEETING PLATFORM - LIVE HTTP API VERIFICATION")
    print(f"Target Service: {BASE_URL}")
    print("=" * 70)

    passed = 0
    total = 0

    def assert_step(condition: bool, test_name: str, detail: str = ""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"  [PASS {passed:02d}] {test_name}")
        else:
            print(f"  [FAIL] {test_name}: {detail}")
            sys.exit(1)

    # 1. Setup Users
    print("\n--- STEP 1 & 2: User Authentication & Token Retrieval ---")
    host = create_user_and_token("Native Host User")
    member = create_user_and_token("Native Member User")
    stranger = create_user_and_token("Native Stranger User")

    for actor in [host, member, stranger]:
        status, me_body = http_request("GET", "/api/v1/auth/me", headers=auth_header(actor["token"]))
        assert_step(status == 200, f"Authenticated user '{actor['name']}' retrieved profile successfully")
        actor["id"] = me_body["id"]

    # 2. Setup Workspace
    print("\n--- STEP 3: Workspace Creation & Member RBAC Provisioning ---")
    status, ws_body = http_request(
        "POST",
        "/api/v1/workspaces",
        {"name": f"Native Room Workspace {uuid.uuid4().hex[:4]}"},
        headers=auth_header(host["token"]),
    )
    assert_step(status == 201, "Host created workspace successfully")
    ws_id = ws_body["id"]

    status, add_mem_body = http_request(
        "POST",
        f"/api/v1/workspaces/{ws_id}/members",
        {"email": member["email"], "role": "MEMBER"},
        headers=auth_header(host["token"]),
    )
    assert_step(status == 201, "Host added Member to workspace")

    # 3. Create Meeting
    print("\n--- STEP 4: Meeting Creation ---")
    status, meeting_body = http_request(
        "POST",
        "/api/v1/meetings",
        {
            "workspace_id": ws_id,
            "title": "Live Native Engineering Sync",
            "description": "Testing live room initialization and token issuance",
        },
        headers=auth_header(host["token"]),
    )
    assert_step(status == 201, "Host created meeting metadata successfully")
    meeting_id = meeting_body["id"]

    # 4. Initialize Native Room
    print("\n--- STEP 5: Native Room Initialization ---")
    status, init_body = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/native-room",
        headers=auth_header(host["token"]),
    )
    assert_step(status == 200, "Host initialized native meeting room")
    assert_step(init_body["is_native"] is True, "Meeting flag 'is_native' is True")
    assert_step(init_body["room_id"].startswith("cm_room_"), f"Secure Room ID generated: {init_body['room_id']}")
    assert_step(init_body["room_status"] == "IDLE", "Initial room status is IDLE")
    room_id = init_body["room_id"]

    # 5. Join Native Room as Host
    print("\n--- STEP 6: Host Join & Media Token Generation ---")
    status, host_join = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/join",
        headers=auth_header(host["token"]),
    )
    assert_step(status == 200, "Host joined native room successfully")
    assert_step(host_join["is_host"] is True, "Host join payload indicates is_host=True")
    assert_step(host_join["room_status"] == "ACTIVE", "Room status updated to ACTIVE upon join")
    assert_step(len(host_join["token"]) > 10, "Secure media access token generated")
    assert_step("ws_url" in host_join, f"Media server WebSocket URL returned: {host_join['ws_url']}")

    # 6. Join Native Room as Workspace Member
    print("\n--- STEP 6b: Member Join Native Room ---")
    status, member_join = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/join",
        headers=auth_header(member["token"]),
    )
    assert_step(status == 200, "Workspace Member joined native room successfully")
    assert_step(member_join["is_host"] is False, "Member join payload indicates is_host=False")
    assert_step(len(member_join["token"]) > 10, "Secure media access token issued to Member")

    # 7. Retrieve Room Information & Participants
    print("\n--- STEP 7 & 8: Retrieve Room Information & Active Participants ---")
    status, room_info = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/room",
        headers=auth_header(member["token"]),
    )
    assert_step(status == 200, "Retrieved native room status and presence")
    assert_step(room_info["room_id"] == room_id, "Room ID matches expected slug")
    assert_step(room_info["room_status"] == "ACTIVE", "Room status is ACTIVE")
    assert_step(room_info["active_participants_count"] == 2, "Presence tracks 2 active participants")
    assert_step(len(room_info["participants"]) == 2, "Participants list contains 2 records")

    # 8. Member Leaves Native Room
    print("\n--- STEP 9: Participant Leave Meeting ---")
    status, leave_body = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/leave",
        headers=auth_header(member["token"]),
    )
    assert_step(status == 200, "Member left native room successfully")

    # Verify active participant count updated
    status, room_info_after_leave = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/room",
        headers=auth_header(host["token"]),
    )
    assert_step(room_info_after_leave["active_participants_count"] == 1, "Active participant count reduced to 1")

    # 8b. In-Meeting Chat Verification (Phase 3)
    print("\n--- Phase 3: Live In-Meeting Chat & Persistence Verification ---")
    status, chat_send = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/messages",
        {"message": "Phase 3 live chat verification message"},
        headers=auth_header(host["token"]),
    )
    assert_step(status == 201, "Host sent in-meeting chat message successfully")
    assert_step(chat_send["message"] == "Phase 3 live chat verification message", "Chat message body saved correctly")

    status, chat_list = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/messages",
        headers=auth_header(member["token"]),
    )
    assert_step(status == 200, "Workspace member retrieved meeting chat history")
    assert_step(len(chat_list) >= 1, "Chat history contains published messages")

    # Stranger chat access rejection
    status, stranger_chat = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/messages",
        headers=auth_header(stranger["token"]),
    )
    assert_step(status == 404, "Stranger chat history access rejected with 404 Not Found")


    # 8c. Phase 4 Native Recording Verification
    print("\n--- Phase 4: Live Native Meeting Recording Verification ---")
    # Member attempts start recording -> 403 Forbidden
    status, member_rec_start = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/recording/start",
        headers=auth_header(member["token"]),
    )
    assert_step(status == 403, "Non-host member attempt to start recording rejected with 403 Forbidden")

    # Host starts recording -> 200 OK
    status, host_rec_start = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/recording/start",
        headers=auth_header(host["token"]),
    )
    assert_step(status == 200, "Host started native room recording successfully")
    assert_step(host_rec_start["status"] == "RECORDING", "Native recording status is RECORDING")
    assert_step("recording_id" in host_rec_start, "Returned active recording ID")

    # Duplicate start -> 400 Bad Request
    status, dup_start = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/recording/start",
        headers=auth_header(host["token"]),
    )
    assert_step(status == 400, "Duplicate active recording start attempt rejected with 400 Bad Request")

    # Member attempts stop recording -> 403 Forbidden
    status, member_rec_stop = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/recording/stop",
        headers=auth_header(member["token"]),
    )
    assert_step(status == 403, "Non-host member attempt to stop recording rejected with 403 Forbidden")

    # Host stops recording -> 200 OK
    status, host_rec_stop = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/recording/stop",
        headers=auth_header(host["token"]),
    )
    assert_step(status == 200, "Host stopped native room recording and queued task successfully")
    assert_step(host_rec_stop["status"] == "QUEUED", "Native recording status updated to QUEUED for background processing")
    assert_step(host_rec_stop["file_size"] > 0, "Native recording file artifact generated and saved")

    # Verify recording listed in meeting recordings
    status, rec_list = http_request(
        "GET",
        f"/api/v1/meetings/{meeting_id}/recordings",
        headers=auth_header(host["token"]),
    )
    assert_step(status == 200, "Host retrieved meeting recordings list")
    assert_step(len(rec_list.get("items", [])) >= 1, "Recordings list contains native recording artifact")

    # 9. Authorization Checks (RBAC & Security)
    print("\n--- STEP 11, 12 & 15: Security & Authorization Verification ---")
    # Unauthorized request (no token)
    status, unauth_body = http_request("POST", f"/api/v1/meetings/{meeting_id}/join")
    assert_step(status == 401, "Unauthenticated join attempt rejected with 401 Unauthorized")

    # Stranger (cross-workspace member) join attempt
    status, stranger_join = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/join",
        headers=auth_header(stranger["token"]),
    )
    assert_step(status == 404, "Stranger cross-workspace join attempt rejected with 404 Not Found")

    # STEP 13: Non-host attempts to end meeting
    status, member_end = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/end",
        headers=auth_header(member["token"]),
    )
    assert_step(status == 403, "Non-host member attempt to end room rejected with 403 Forbidden")

    # 10. Host Ends Meeting
    print("\n--- STEP 10: Host End Meeting ---")
    status, end_body = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/end",
        headers=auth_header(host["token"]),
    )
    assert_step(status == 200, "Host ended native meeting room successfully")
    assert_step(end_body["status"] == "COMPLETED", "Meeting status updated to COMPLETED")
    assert_step(end_body["room_status"] == "CLOSED", "Room status updated to CLOSED")

    # STEP 14: Rejoin ended meeting rejected
    print("\n--- STEP 14: Reject Join on Ended Meeting ---")
    status, rejoin_body = http_request(
        "POST",
        f"/api/v1/meetings/{meeting_id}/join",
        headers=auth_header(host["token"]),
    )
    assert_step(status == 400, "Join attempt on ended meeting rejected with 400 Bad Request")

    print("\n" + "=" * 70)
    print(f"SUCCESS: ALL {passed}/{total} LIVE NATIVE MEETING VERIFICATION STEPS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    run_live_native_verification()
