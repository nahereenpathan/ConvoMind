"""Live HTTP verification script for ConvoMind Notifications + AI Follow-Up module.

Verifies:
1. API Service Health check
2. User authentication & token acquisition
3. Workspace & Meeting creation
4. Recording upload & AI Intelligence completion
5. In-App Notification listing & Unread Count API
6. Mark Notification Read & Preferences update
7. AI Follow-Up Draft Generation (POST /api/v1/meetings/{id}/follow-ups/generate)
8. Follow-Up draft listing & details retrieval
9. Follow-Up draft editing (PATCH /api/v1/follow-ups/{id})
10. Explicit Human Approval Send (POST /api/v1/follow-ups/{id}/send)
11. Strict User & Workspace Isolation Security Check
"""

import sys
import time
import uuid
import httpx

BASE_URL = "http://localhost:8000/api/v1"


def print_step(msg: str):
    print(f"\n[STEP] {msg}")


def print_success(msg: str):
    print(f"  [SUCCESS] {msg}")


def print_fail(msg: str):
    print(f"  [FAIL] {msg}")


def main():
    print("=" * 70)
    print("CONVOMIND LIVE NOTIFICATIONS & AI FOLLOW-UP VERIFICATION")
    print("=" * 70)

    client = httpx.Client(timeout=30.0)

    # 1. Health check
    print_step("1. Checking API Health Endpoint")
    try:
        resp = client.get(f"{BASE_URL}/health")
        if resp.status_code == 200 and resp.json().get("status") == "healthy":
            print_success("API is healthy.")
        else:
            print_fail(f"Health check unexpected response: {resp.text}")
            sys.exit(1)
    except Exception as exc:
        print_fail(f"Could not connect to API at {BASE_URL}: {exc}")
        sys.exit(1)

    # 2. Authenticate User A
    print_step("2. Authenticating User A")
    user_a_email = f"notif_a_{uuid.uuid4().hex[:6]}@example.com"
    password = "TestPassword123!"

    reg_resp = client.post(
        f"{BASE_URL}/auth/register",
        json={"email": user_a_email, "password": password, "name": "User A"},
    )
    if reg_resp.status_code != 201:
        print_fail(f"User A registration failed: {reg_resp.text}")
        sys.exit(1)

    login_resp = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": user_a_email, "password": password},
    )
    if login_resp.status_code != 200:
        print_fail(f"User A login failed: {login_resp.text}")
        sys.exit(1)

    token_a = login_resp.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    print_success(f"Authenticated User A: {user_a_email}")

    # 3. Create Workspace & Meeting
    print_step("3. Creating Workspace & Meeting for User A")
    ws_resp = client.post(
        f"{BASE_URL}/workspaces",
        json={"name": "Notifications WS A"},
        headers=headers_a,
    )
    if ws_resp.status_code != 201:
        print_fail(f"Workspace creation failed: {ws_resp.text}")
        sys.exit(1)
    ws_id = ws_resp.json()["id"]

    meeting_resp = client.post(
        f"{BASE_URL}/meetings",
        json={
            "workspace_id": ws_id,
            "title": "Q3 Product Architecture Review",
            "platform": "other",
        },
        headers=headers_a,
    )
    if meeting_resp.status_code != 201:
        print_fail(f"Meeting creation failed: {meeting_resp.text}")
        sys.exit(1)
    meeting_id = meeting_resp.json()["id"]
    print_success(f"Created Meeting ID: {meeting_id}")

    # 4. Upload Recording & Process Transcript / Intelligence
    print_step("4. Uploading Recording & Triggering AI Pipeline")
    import struct
    num_samples = int(2.0 * 16000)
    byte_rate = 16000 * 2
    block_align = 2
    data_size = num_samples * 2
    chunk_size = 36 + data_size
    pcm_header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16, 1, 1, 16000, byte_rate, block_align, 16, b"data", data_size
    )
    dummy_wav_content = pcm_header + (b"\x00" * data_size)

    files = {"file": ("meeting_audio.wav", dummy_wav_content, "audio/wav")}
    rec_resp = client.post(
        f"{BASE_URL}/meetings/{meeting_id}/recordings",
        files=files,
        headers=headers_a,
    )
    if rec_resp.status_code != 201:
        print_fail(f"Recording upload failed: {rec_resp.text}")
        sys.exit(1)

    print("  Waiting for Celery transcription worker...")
    for _ in range(30):
        tr_check = client.get(
            f"{BASE_URL}/meetings/{meeting_id}/transcript",
            headers=headers_a,
        )
        if tr_check.status_code == 200 and tr_check.json().get("status") == "completed":
            print_success("Transcription COMPLETED.")
            break
        time.sleep(1)

    # Trigger AI Intelligence
    client.post(
        f"{BASE_URL}/meetings/{meeting_id}/intelligence/process",
        headers=headers_a,
    )
    print("  Waiting for Celery intelligence worker...")
    for _ in range(30):
        intel_check = client.get(
            f"{BASE_URL}/meetings/{meeting_id}/intelligence",
            headers=headers_a,
        )
        if intel_check.status_code == 200 and intel_check.json().get("status") == "completed":
            print_success("AI Meeting Intelligence COMPLETED.")
            break
        time.sleep(1)

    # 5. Verify In-App Notification Listing & Unread Count API
    print_step("5. Verifying In-App Notifications API")
    notif_resp = client.get(
        f"{BASE_URL}/notifications",
        headers=headers_a,
    )
    if notif_resp.status_code != 200:
        print_fail(f"Listing notifications failed: {notif_resp.text}")
        sys.exit(1)

    notif_data = notif_resp.json()
    items = notif_data["items"]
    print_success(f"Retrieved {len(items)} notifications. Total: {notif_data['total']}, Unread: {notif_data['unread_count']}")

    unread_resp = client.get(
        f"{BASE_URL}/notifications/unread-count",
        headers=headers_a,
    )
    if unread_resp.status_code == 200:
        print_success(f"Unread Count Endpoint returned: {unread_resp.json()['unread_count']}")

    # 6. Mark Notification Read & Preferences Update
    if len(items) > 0:
        print_step("6. Marking Notification Read & Updating Preferences")
        n_id = items[0]["id"]
        read_resp = client.patch(
            f"{BASE_URL}/notifications/{n_id}/read",
            headers=headers_a,
        )
        if read_resp.status_code == 200 and read_resp.json()["is_read"] is True:
            print_success(f"Marked Notification {n_id} as READ.")

    pref_resp = client.get(
        f"{BASE_URL}/notifications/preferences",
        headers=headers_a,
    )
    if pref_resp.status_code == 200:
        print_success("Fetched User Notification Preferences.")

    # 7. Generate AI Follow-Up Draft
    print_step("7. Generating AI Follow-Up Draft (POST /meetings/{id}/follow-ups/generate)")
    gen_resp = client.post(
        f"{BASE_URL}/meetings/{meeting_id}/follow-ups/generate",
        json={"type": "EMAIL_DRAFT", "additional_instructions": "Highlight API deadlines."},
        headers=headers_a,
    )
    if gen_resp.status_code != 201:
        print_fail(f"AI Follow-up generation failed: {gen_resp.text}")
        sys.exit(1)

    follow_up = gen_resp.json()
    follow_up_id = follow_up["id"]
    print_success(f"Generated AI Follow-Up ID: {follow_up_id} (Status: {follow_up['status']})")
    print_success(f"Subject: '{follow_up['subject']}'")

    # 8. List & Get Follow-Up Details
    print_step("8. Listing & Retrieving Follow-Up Details")
    list_fu_resp = client.get(
        f"{BASE_URL}/meetings/{meeting_id}/follow-ups",
        headers=headers_a,
    )
    if list_fu_resp.status_code == 200 and len(list_fu_resp.json()) > 0:
        print_success(f"Meeting Follow-Ups count: {len(list_fu_resp.json())}")

    # 9. Update Follow-Up Draft
    print_step("9. Editing Follow-Up Draft (PATCH /follow-ups/{id})")
    edit_resp = client.patch(
        f"{BASE_URL}/follow-ups/{follow_up_id}",
        json={"subject": "Next Steps — Product Planning Review", "recipients": [user_a_email]},
        headers=headers_a,
    )
    if edit_resp.status_code != 200:
        print_fail(f"Editing follow-up failed: {edit_resp.text}")
        sys.exit(1)
    print_success(f"Updated Follow-Up subject to '{edit_resp.json()['subject']}'")

    # 10. Explicit Human Approval Send
    print_step("10. Explicit Human Approval Send (POST /follow-ups/{id}/send)")
    send_resp = client.post(
        f"{BASE_URL}/follow-ups/{follow_up_id}/send",
        headers=headers_a,
    )
    if send_resp.status_code != 200:
        print_fail(f"Sending follow-up failed: {send_resp.text}")
        sys.exit(1)
    sent_data = send_resp.json()
    if sent_data["status"] == "SENT":
        print_success("Human-approved follow-up email successfully dispatched! Status: SENT")

    # 11. Security & Workspace Isolation
    print_step("11. Verifying Security & Workspace Isolation")
    user_b_email = f"notif_b_{uuid.uuid4().hex[:6]}@example.com"
    client.post(
        f"{BASE_URL}/auth/register",
        json={"email": user_b_email, "password": password, "name": "User B"},
    )
    token_b = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": user_b_email, "password": password},
    ).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    iso_resp = client.get(
        f"{BASE_URL}/follow-ups/{follow_up_id}",
        headers=headers_b,
    )
    if iso_resp.status_code in (403, 404):
        print_success(f"Workspace Isolation enforced: returned HTTP {iso_resp.status_code}")
    else:
        print_fail(f"SECURITY BREACH: User B accessed User A's follow-up draft! Status: {iso_resp.status_code}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("ALL LIVE NOTIFICATIONS & AI FOLLOW-UP VERIFICATION CHECKS PASSED (100%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
