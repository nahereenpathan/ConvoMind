"""Live HTTP verification script testing ConvoMind Permanent Delete Meeting flow."""

import httpx
import uuid

BASE_URL = "http://127.0.0.1:8000"

def run_verification():
    print("=" * 70)
    print("CONVOMIND PERMANENT DELETE MEETING VERIFICATION")
    print(f"Target Service: {BASE_URL}")
    print("=" * 70)

    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # 1. Register & Login Owner
    unique_suffix = uuid.uuid4().hex[:6]
    owner_email = f"perm_owner_{unique_suffix}@convomind.ai"
    password = "Password123!"

    reg_res = client.post("/api/v1/auth/register", json={
        "name": "Permanent Delete Owner",
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

    # 2. Create Workspace
    ws_res = client.post("/api/v1/workspaces", json={
        "name": f"Perm Delete Workspace {unique_suffix}"
    }, headers=headers_owner)
    assert ws_res.status_code == 201
    workspace_id = ws_res.json()["id"]
    print("  [PASS 02] Workspace created successfully")

    # 3. Create 2 Meetings (Meeting A for deletion, Meeting B to verify non-deletion)
    m1_res = client.post("/api/v1/meetings", json={
        "workspace_id": workspace_id,
        "title": "ConvoMind Product Development Discussion",
        "description": "ToDelete Target Meeting",
    }, headers=headers_owner)
    assert m1_res.status_code == 201
    m1_id = m1_res.json()["id"]

    m2_res = client.post("/api/v1/meetings", json={
        "workspace_id": workspace_id,
        "title": "Intact Active Meeting",
        "description": "Should remain untouched",
    }, headers=headers_owner)
    assert m2_res.status_code == 201
    m2_id = m2_res.json()["id"]
    print("  [PASS 03] Created test meetings A (delete target) and B (control)")

    # 4. Attempt Permanent Delete on Active Meeting -> 404 (because not in Trash)
    attempt_active = client.delete(f"/api/v1/meetings/{m1_id}/permanent", headers=headers_owner)
    assert attempt_active.status_code == 404
    print("  [PASS 04] Reject permanent delete on active meeting (Must be in Trash first)")

    # 5. Move Meeting A to Trash (Soft Delete)
    trash_res = client.delete(f"/api/v1/meetings/{m1_id}", headers=headers_owner)
    assert trash_res.status_code == 200
    print("  [PASS 05] Moved Meeting A to Trash (Soft Delete)")

    # 6. Verify Meeting A appears in Trash endpoint & Meeting B in Active list
    list_trash = client.get(f"/api/v1/meetings/trash?workspace_id={workspace_id}", headers=headers_owner)
    assert list_trash.status_code == 200
    assert any(m["id"] == m1_id for m in list_trash.json()["items"])

    list_active = client.get(f"/api/v1/meetings?workspace_id={workspace_id}", headers=headers_owner)
    assert list_active.status_code == 200
    assert any(m["id"] == m2_id for m in list_active.json()["items"])
    assert not any(m["id"] == m1_id for m in list_active.json()["items"])
    print("  [PASS 06] Verified Meeting A in Trash and Meeting B in Active list")

    # 7. Execute Permanent Delete on Meeting A from Trash
    perm_del_res = client.delete(f"/api/v1/meetings/{m1_id}/permanent", headers=headers_owner)
    assert perm_del_res.status_code == 200
    assert "permanently" in perm_del_res.json()["message"].lower()
    print("  [PASS 07] Executed Permanent Delete API request successfully")

    # 8. Verify Meeting A is completely purged from Trash & DB
    trash_after = client.get(f"/api/v1/meetings/trash?workspace_id={workspace_id}", headers=headers_owner)
    assert trash_after.status_code == 200
    assert not any(m["id"] == m1_id for m in trash_after.json()["items"])

    # 9. Verify Control Meeting B remains intact
    active_after = client.get(f"/api/v1/meetings?workspace_id={workspace_id}", headers=headers_owner)
    assert active_after.status_code == 200
    assert any(m["id"] == m2_id for m in active_after.json()["items"])
    print("  [PASS 08] Verified Meeting A purged completely; Meeting B intact")

    print("=" * 70)
    print("SUCCESS: ALL 8/8 PERMANENT DELETE VERIFICATION STEPS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    run_verification()
