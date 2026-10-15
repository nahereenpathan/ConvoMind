"""Live HTTP verification script for ConvoMind Notification Management (Delete, Clear All, Read/Unread, and IDOR isolation)."""

import asyncio
import httpx
import uuid

BASE_URL = "http://127.0.0.1:8000"

def run_verification():
    print("=" * 70)
    print("CONVOMIND NOTIFICATION MANAGEMENT VERIFICATION")
    print(f"Target Service: {BASE_URL}")
    print("=" * 70)

    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # 1. Register & Login Owner
    unique_suffix = uuid.uuid4().hex[:6]
    owner_email = f"notif_owner_{unique_suffix}@convomind.ai"
    password = "Password123!"

    reg_res = client.post("/api/v1/auth/register", json={
        "name": "Notification Owner",
        "email": owner_email,
        "password": password,
    })
    assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
    owner_user = reg_res.json()
    owner_user_id = uuid.UUID(owner_user["id"])

    login_res = client.post("/api/v1/auth/login", json={
        "email": owner_email,
        "password": password,
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_owner = login_res.json()["access_token"]
    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    print("  [PASS 01] Authenticated Owner user successfully")

    # 2. Register & Login Stranger
    stranger_email = f"notif_stranger_{unique_suffix}@convomind.ai"
    reg_stranger = client.post("/api/v1/auth/register", json={
        "name": "Notification Stranger",
        "email": stranger_email,
        "password": password,
    })
    assert reg_stranger.status_code == 201
    stranger_user_id = uuid.UUID(reg_stranger.json()["id"])

    login_stranger_res = client.post("/api/v1/auth/login", json={
        "email": stranger_email,
        "password": password,
    })
    token_stranger = login_stranger_res.json()["access_token"]
    headers_stranger = {"Authorization": f"Bearer {token_stranger}"}
    print("  [PASS 02] Authenticated Stranger user successfully")

    # 3. Create Workspace for Owner
    ws_res = client.post("/api/v1/workspaces", json={
        "name": f"Notif Workspace {unique_suffix}"
    }, headers=headers_owner)
    assert ws_res.status_code == 201
    workspace_id = uuid.UUID(ws_res.json()["id"])
    print("  [PASS 03] Workspace created successfully")

    # 4. Dispatch Notifications using NotificationService directly inside Python runner
    from app.core.database import AsyncSessionLocal
    from app.models.enums import NotificationType
    from app.services.notifications.notification_service import NotificationService

    async def seed_test_notifications():
        async with AsyncSessionLocal() as session:
            n1 = await NotificationService.create_and_dispatch_notification(
                db=session,
                user_id=owner_user_id,
                workspace_id=workspace_id,
                type=NotificationType.AI_ANALYSIS_COMPLETED,
                title="AI Analysis Complete",
                message="Your meeting AI intelligence report is ready.",
            )
            n2 = await NotificationService.create_and_dispatch_notification(
                db=session,
                user_id=owner_user_id,
                workspace_id=workspace_id,
                type=NotificationType.ACTION_ITEM_ASSIGNED,
                title="New Action Item Assigned",
                message="Review Q3 strategy presentation.",
            )
            # Seed 1 notification for Stranger to verify isolation
            n_stranger = await NotificationService.create_and_dispatch_notification(
                db=session,
                user_id=stranger_user_id,
                workspace_id=workspace_id,
                type=NotificationType.TRANSCRIPT_COMPLETED,
                title="Stranger Transcript Ready",
                message="Private transcript ready.",
            )
            return n1, n2, n_stranger

    n1, n2, n_stranger = asyncio.run(seed_test_notifications())
    print("  [PASS 04] Created test notifications for Owner & Stranger")

    # 5. Verify Notification Listing & Unread Count for Owner
    list_res = client.get("/api/v1/notifications", headers=headers_owner)
    assert list_res.status_code == 200
    notifications_data = list_res.json()
    items = notifications_data["items"]
    assert len(items) == 2
    assert notifications_data["unread_count"] == 2
    notif_id = str(n1.id)
    print("  [PASS 05] Listed notifications and verified unread count = 2")

    # 6. Mark Notification as Read
    read_res = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers_owner)
    assert read_res.status_code == 200
    assert read_res.json()["is_read"] is True
    print("  [PASS 06] Marked notification as read successfully")

    # 7. Mark Notification as Unread
    unread_res = client.patch(f"/api/v1/notifications/{notif_id}/unread", headers=headers_owner)
    assert unread_res.status_code == 200
    assert unread_res.json()["is_read"] is False
    print("  [PASS 07] Marked notification as unread successfully")

    # 8. Test Stranger IDOR Prevention
    stranger_read = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers_stranger)
    assert stranger_read.status_code == 404

    stranger_unread = client.patch(f"/api/v1/notifications/{notif_id}/unread", headers=headers_stranger)
    assert stranger_unread.status_code == 404

    stranger_delete = client.delete(f"/api/v1/notifications/{notif_id}", headers=headers_stranger)
    assert stranger_delete.status_code == 404
    print("  [PASS 08] Verified IDOR security checks (Stranger receives 404 for all operations)")

    # 9. Mark All as Read
    mark_all_res = client.patch("/api/v1/notifications/read-all", headers=headers_owner)
    assert mark_all_res.status_code == 200

    unread_count_res = client.get("/api/v1/notifications/unread-count", headers=headers_owner)
    assert unread_count_res.status_code == 200
    assert unread_count_res.json()["unread_count"] == 0
    print("  [PASS 09] Marked all notifications as read & verified unread count is 0")

    # 10. Delete Individual Notification
    del_res = client.delete(f"/api/v1/notifications/{notif_id}", headers=headers_owner)
    assert del_res.status_code == 200

    list_after_del = client.get("/api/v1/notifications", headers=headers_owner)
    assert list_after_del.json()["total"] == 1
    print("  [PASS 10] Deleted single notification successfully")

    # 11. Clear All Notifications for Owner
    clear_res = client.delete("/api/v1/notifications", headers=headers_owner)
    assert clear_res.status_code == 200
    assert "cleared" in clear_res.json()["message"].lower()

    # 12. Verify Empty State for Owner & Verify Stranger's Notification Intact
    empty_list_res = client.get("/api/v1/notifications", headers=headers_owner)
    assert empty_list_res.status_code == 200
    assert empty_list_res.json()["total"] == 0

    stranger_list_res = client.get("/api/v1/notifications", headers=headers_stranger)
    assert stranger_list_res.status_code == 200
    assert stranger_list_res.json()["total"] == 1
    assert stranger_list_res.json()["items"][0]["id"] == str(n_stranger.id)
    print("  [PASS 11] Cleared all notifications for Owner; verified Stranger notification intact")

    print("=" * 70)
    print("SUCCESS: ALL 11/11 NOTIFICATION MANAGEMENT VERIFICATION STEPS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    run_verification()
