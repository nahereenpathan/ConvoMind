"""Verification script for ConvoMind Soft Delete, Trash, Restore, and Permanent Delete lifecycle."""

import httpx
import uuid

BASE_URL = "http://127.0.0.1:8000"

def run_verification():
    print("=" * 70)
    print("CONVOMIND SOFT DELETE, TRASH, RESTORE & PERMANENT DELETE VERIFICATION")
    print(f"Target Service: {BASE_URL}")
    print("=" * 70)

    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # 1. Register & Login Owner
    unique_suffix = uuid.uuid4().hex[:6]
    owner_email = f"trash_owner_{unique_suffix}@convomind.ai"
    password = "Password123!"

    reg_res = client.post("/api/v1/auth/register", json={
        "name": "Trash Test Owner",
        "email": owner_email,
        "password": password,
    })
    assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"

    login_res = client.post("/api/v1/auth/login", json={
        "email": owner_email,
        "password": password,
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_owner = login_res.json()["access_token"]
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    print("  [PASS 01] Authenticated Owner user successfully")

    # 2. Register & Login Stranger (Cross-workspace isolation check)
    stranger_email = f"trash_stranger_{unique_suffix}@convomind.ai"
    client.post("/api/v1/auth/register", json={
        "name": "Trash Stranger",
        "email": stranger_email,
        "password": password,
    })
    login_stranger_res = client.post("/api/v1/auth/login", json={
        "email": stranger_email,
        "password": password,
    })
    token_stranger = login_stranger_res.json()["access_token"]
    headers_stranger = {"Authorization": f"Bearer {token_stranger}"}
    print("  [PASS 02] Authenticated Stranger user successfully")

    # 3. Create Workspace
    ws_res = client.post("/api/v1/workspaces", json={
        "name": f"Trash Test Workspace {unique_suffix}"
    }, headers=headers_owner)
    assert ws_res.status_code == 201
    workspace_id = ws_res.json()["id"]
    print("  [PASS 03] Workspace created successfully")

    # 4. Create Meeting
    meeting_res = client.post("/api/v1/meetings", json={
        "workspace_id": workspace_id,
        "title": "Client Project Discussion - ConvoMind",
        "description": "Quarterly review and deliverable planning",
    }, headers=headers_owner)
    assert meeting_res.status_code == 201
    meeting = meeting_res.json()
    meeting_id = meeting["id"]
    print("  [PASS 04] Active meeting created successfully")

    # 5. Verify Meeting appears in Active Meetings List
    list_active = client.get(f"/api/v1/meetings?workspace_id={workspace_id}", headers=headers_owner)
    assert list_active.status_code == 200
    active_items = list_active.json()["items"]
    assert any(m["id"] == meeting_id for m in active_items)
    print("  [PASS 05] Meeting verified in active meetings list")

    # 6. Move Meeting to Trash (Soft Delete)
    soft_del_res = client.delete(f"/api/v1/meetings/{meeting_id}", headers=headers_owner)
    assert soft_del_res.status_code == 200
    assert "trash" in soft_del_res.json()["message"].lower()
    print("  [PASS 06] Soft deleted meeting (Moved to Trash)")

    # 7. Verify Meeting is removed from Active Meetings List & GET returns 404
    list_active_after = client.get(f"/api/v1/meetings?workspace_id={workspace_id}", headers=headers_owner)
    assert list_active_after.status_code == 200
    assert not any(m["id"] == meeting_id for m in list_active_after.json()["items"])

    get_res = client.get(f"/api/v1/meetings/{meeting_id}", headers=headers_owner)
    assert get_res.status_code == 404
    print("  [PASS 07] Soft deleted meeting excluded from active list & active GET endpoint")

    # 8. Verify Meeting appears in Trash List GET /api/v1/meetings/trash
    list_trash = client.get(f"/api/v1/meetings/trash?workspace_id={workspace_id}", headers=headers_owner)
    assert list_trash.status_code == 200
    trashed_items = list_trash.json()["items"]
    assert any(m["id"] == meeting_id for m in trashed_items)
    print("  [PASS 08] Meeting verified in Trash list")

    # 9. Verify Stranger cannot access Trash or Restore (Cross-Workspace Isolation)
    stranger_trash = client.get(f"/api/v1/meetings/trash?workspace_id={workspace_id}", headers=headers_stranger)
    assert stranger_trash.status_code == 404

    stranger_restore = client.post(f"/api/v1/meetings/{meeting_id}/restore", headers=headers_stranger)
    assert stranger_restore.status_code == 404
    print("  [PASS 09] Cross-workspace IDOR access rejected with 404 Not Found")

    # 10. Restore Meeting from Trash
    restore_res = client.post(f"/api/v1/meetings/{meeting_id}/restore", headers=headers_owner)
    assert restore_res.status_code == 200
    assert "restored" in restore_res.json()["message"].lower()
    print("  [PASS 10] Restored meeting from Trash successfully")

    # 11. Verify Meeting returns to Active Meetings List
    list_active_restored = client.get(f"/api/v1/meetings?workspace_id={workspace_id}", headers=headers_owner)
    assert list_active_restored.status_code == 200
    assert any(m["id"] == meeting_id for m in list_active_restored.json()["items"])
    print("  [PASS 11] Restored meeting returned to active list")

    # 12. Active Native Room Soft-Delete Block
    native_meeting_res = client.post("/api/v1/meetings", json={
        "workspace_id": workspace_id,
        "title": "Active Native Session",
    }, headers=headers_owner)
    native_id = native_meeting_res.json()["id"]

    client.post(f"/api/v1/meetings/{native_id}/native-room", headers=headers_owner)
    client.post(f"/api/v1/meetings/{native_id}/join", headers=headers_owner)

    # Attempt to trash active meeting -> HTTP 409 Conflict
    active_trash_attempt = client.delete(f"/api/v1/meetings/{native_id}", headers=headers_owner)
    assert active_trash_attempt.status_code == 409
    assert "currently active" in active_trash_attempt.json()["detail"].lower()
    print("  [PASS 12] Active native meeting trash attempt rejected with 409 Conflict")

    # End native meeting
    client.post(f"/api/v1/meetings/{native_id}/end", headers=headers_owner)

    # 13. Move to Trash & Permanent Delete
    soft_del_res2 = client.delete(f"/api/v1/meetings/{meeting_id}", headers=headers_owner)
    assert soft_del_res2.status_code == 200

    perm_del_res = client.delete(f"/api/v1/meetings/{meeting_id}/permanent", headers=headers_owner)
    assert perm_del_res.status_code == 200
    assert "permanently" in perm_del_res.json()["message"].lower()
    print("  [PASS 13] Permanently deleted meeting successfully")

    # 14. Verify Permanent Deletion in Trash List
    list_trash_after = client.get(f"/api/v1/meetings/trash?workspace_id={workspace_id}", headers=headers_owner)
    assert list_trash_after.status_code == 200
    assert not any(m["id"] == meeting_id for m in list_trash_after.json()["items"])
    print("  [PASS 14] Verified meeting permanently purged from Trash list")

    print("=" * 70)
    print("SUCCESS: ALL 14/14 SOFT DELETE, TRASH, RESTORE & PERMANENT DELETE VERIFICATION STEPS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    run_verification()

