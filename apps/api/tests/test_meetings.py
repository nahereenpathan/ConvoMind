"""Comprehensive automated tests for Meeting Management module."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import MeetingStatus, WorkspaceRole


async def create_user_and_token(
    client: AsyncClient, name: str = "Meeting Test User"
) -> Tuple[Dict, str]:
    """Register and login a user, returning user dict and access token."""
    email = f"meeting_test_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "Password123!"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert reg_res.status_code == 201, reg_res.text
    user_data = reg_res.json()

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    return user_data, token


def auth_header(token: str) -> Dict[str, str]:
    """Return Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}


async def setup_workspace_with_roles(
    client: AsyncClient,
) -> Dict:
    """Set up an owner, admin, member, and stranger across workspaces."""
    owner, token_owner = await create_user_and_token(client, "WS Owner")
    admin, token_admin = await create_user_and_token(client, "WS Admin")
    member, token_member = await create_user_and_token(client, "WS Member")
    guest, token_guest = await create_user_and_token(client, "WS Guest")
    stranger, token_stranger = await create_user_and_token(client, "WS Stranger")

    # Create workspace
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": f"Meeting Test Workspace {uuid.uuid4().hex[:4]}"},
        headers=auth_header(token_owner),
    )
    assert ws_res.status_code == 201
    workspace = ws_res.json()
    ws_id = workspace["id"]

    # Add Admin
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": admin["email"], "role": "ADMIN"},
        headers=auth_header(token_owner),
    )

    # Add Member
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member["email"], "role": "MEMBER"},
        headers=auth_header(token_owner),
    )

    # Add Guest
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": guest["email"], "role": "GUEST"},
        headers=auth_header(token_owner),
    )

    return {
        "workspace": workspace,
        "owner": owner,
        "token_owner": token_owner,
        "admin": admin,
        "token_admin": token_admin,
        "member": member,
        "token_member": token_member,
        "guest": guest,
        "token_guest": token_guest,
        "stranger": stranger,
        "token_stranger": token_stranger,
    }


# ==========================================
# 1. Meeting CRUD
# ==========================================


@pytest.mark.asyncio
async def test_create_meeting_success():
    """Verify authenticated workspace member can create a meeting."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]
        sched = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        payload = {
            "workspace_id": ws_id,
            "title": "Product Strategy Sync",
            "description": "Discuss Q4 deliverables and roadmap",
            "meeting_type": "planning",
            "status": "scheduled",
            "scheduled_at": sched,
            "source_type": "zoom",
        }
        res = await client.post(
            "/api/v1/meetings",
            json=payload,
            headers=auth_header(env["token_member"]),
        )
        assert res.status_code == 201
        data = res.json()
        assert data["title"] == "Product Strategy Sync"
        assert data["workspace_id"] == ws_id
        assert data["created_by"] == env["member"]["id"]
        assert data["status"] == "SCHEDULED"
        assert data["meeting_type"] == "planning"
        assert "id" in data


@pytest.mark.asyncio
async def test_list_meetings_with_pagination():
    """Verify listing meetings returns pagination metadata and items."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        # Create 3 meetings
        for i in range(3):
            await client.post(
                "/api/v1/meetings",
                json={"workspace_id": ws_id, "title": f"Meeting {i}"},
                headers=auth_header(env["token_owner"]),
            )

        res = await client.get(
            f"/api/v1/meetings?workspace_id={ws_id}&page=1&page_size=2",
            headers=auth_header(env["token_owner"]),
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 2


@pytest.mark.asyncio
async def test_get_meeting_details():
    """Verify retrieving meeting details by ID."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        create_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Detailed Discussion"},
            headers=auth_header(env["token_owner"]),
        )
        meeting_id = create_res.json()["id"]

        res = await client.get(
            f"/api/v1/meetings/{meeting_id}",
            headers=auth_header(env["token_member"]),
        )
        assert res.status_code == 200
        assert res.json()["id"] == meeting_id
        assert res.json()["title"] == "Detailed Discussion"


@pytest.mark.asyncio
async def test_update_meeting_by_creator():
    """Verify meeting creator can update meeting."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        create_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Old Title"},
            headers=auth_header(env["token_member"]),
        )
        meeting_id = create_res.json()["id"]

        res = await client.patch(
            f"/api/v1/meetings/{meeting_id}",
            json={"title": "Updated Title", "description": "Updated Desc"},
            headers=auth_header(env["token_member"]),
        )
        assert res.status_code == 200
        assert res.json()["title"] == "Updated Title"
        assert res.json()["description"] == "Updated Desc"


@pytest.mark.asyncio
async def test_delete_meeting_by_creator():
    """Verify meeting creator can move meeting to Trash, list it, restore it, and permanently delete it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        create_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "To Delete"},
            headers=auth_header(env["token_member"]),
        )
        meeting_id = create_res.json()["id"]

        # 1. Soft delete (move to Trash)
        del_res = await client.delete(
            f"/api/v1/meetings/{meeting_id}",
            headers=auth_header(env["token_member"]),
        )
        assert del_res.status_code == 200
        assert "trash" in del_res.json()["message"].lower() or "deleted" in del_res.json()["message"].lower()

        # 2. Verify active GET returns 404
        get_res = await client.get(
            f"/api/v1/meetings/{meeting_id}",
            headers=auth_header(env["token_member"]),
        )
        assert get_res.status_code == 404

        # 3. Verify it appears in Trash list
        trash_res = await client.get(
            f"/api/v1/meetings/trash?workspace_id={ws_id}",
            headers=auth_header(env["token_member"]),
        )
        assert trash_res.status_code == 200
        trashed_items = trash_res.json()["items"]
        assert any(m["id"] == meeting_id for m in trashed_items)

        # 4. Restore meeting from Trash
        restore_res = await client.post(
            f"/api/v1/meetings/{meeting_id}/restore",
            headers=auth_header(env["token_member"]),
        )
        assert restore_res.status_code == 200
        assert "restored" in restore_res.json()["message"].lower()

        # 5. Verify it is active again
        get_active_res = await client.get(
            f"/api/v1/meetings/{meeting_id}",
            headers=auth_header(env["token_member"]),
        )
        assert get_active_res.status_code == 200
        assert get_active_res.json()["id"] == meeting_id

        # 6. Move to trash again and permanently delete
        await client.delete(
            f"/api/v1/meetings/{meeting_id}",
            headers=auth_header(env["token_member"]),
        )
        perm_res = await client.delete(
            f"/api/v1/meetings/{meeting_id}/permanent",
            headers=auth_header(env["token_member"]),
        )
        assert perm_res.status_code == 200
        assert "permanently" in perm_res.json()["message"].lower()

        # 7. Verify trash list is empty
        empty_trash_res = await client.get(
            f"/api/v1/meetings/trash?workspace_id={ws_id}",
            headers=auth_header(env["token_member"]),
        )
        assert empty_trash_res.status_code == 200
        assert not any(m["id"] == meeting_id for m in empty_trash_res.json()["items"])


# ==========================================
# 2. Workspace Isolation & IDOR Prevention
# ==========================================


@pytest.mark.asyncio
async def test_non_member_cannot_access_meeting():
    """Verify non-member receives 404 (IDOR prevention)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        create_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Confidential Meeting"},
            headers=auth_header(env["token_owner"]),
        )
        meeting_id = create_res.json()["id"]

        # Stranger attempts GET
        res_get = await client.get(
            f"/api/v1/meetings/{meeting_id}",
            headers=auth_header(env["token_stranger"]),
        )
        assert res_get.status_code == 404
        assert res_get.json()["detail"] == "Meeting not found."

        # Stranger attempts PATCH
        res_patch = await client.patch(
            f"/api/v1/meetings/{meeting_id}",
            json={"title": "Hacked"},
            headers=auth_header(env["token_stranger"]),
        )
        assert res_patch.status_code == 404

        # Stranger attempts DELETE
        res_del = await client.delete(
            f"/api/v1/meetings/{meeting_id}",
            headers=auth_header(env["token_stranger"]),
        )
        assert res_del.status_code == 404


@pytest.mark.asyncio
async def test_cross_workspace_access_rejected():
    """Verify user cannot query meetings from a workspace they do not belong to."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        res = await client.get(
            f"/api/v1/meetings?workspace_id={ws_id}",
            headers=auth_header(env["token_stranger"]),
        )
        assert res.status_code == 404
        assert "workspace not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected():
    """Verify unauthenticated requests return 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fake_id = uuid.uuid4()
        res = await client.get(f"/api/v1/meetings/{fake_id}")
        assert res.status_code == 401

        res_post = await client.post("/api/v1/meetings", json={"title": "No Auth"})
        assert res_post.status_code == 401


# ==========================================
# 3. RBAC & Permissions
# ==========================================


@pytest.mark.asyncio
async def test_regular_member_cannot_update_others_meeting():
    """Verify regular member cannot update a meeting created by someone else (returns 403)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        create_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Owner Meeting"},
            headers=auth_header(env["token_owner"]),
        )
        meeting_id = create_res.json()["id"]

        res = await client.patch(
            f"/api/v1/meetings/{meeting_id}",
            json={"title": "Member Attempted Update"},
            headers=auth_header(env["token_member"]),
        )
        assert res.status_code == 403
        assert "insufficient permissions" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_regular_member_cannot_delete_others_meeting():
    """Verify regular member cannot delete a meeting created by someone else (returns 403)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        create_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Owner Meeting"},
            headers=auth_header(env["token_owner"]),
        )
        meeting_id = create_res.json()["id"]

        res = await client.delete(
            f"/api/v1/meetings/{meeting_id}",
            headers=auth_header(env["token_member"]),
        )
        assert res.status_code == 403
        assert "insufficient permissions" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_can_update_and_delete_any_meeting():
    """Verify workspace admin can update and delete any meeting in the workspace."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        create_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Member Meeting"},
            headers=auth_header(env["token_member"]),
        )
        meeting_id = create_res.json()["id"]

        # Admin updates
        patch_res = await client.patch(
            f"/api/v1/meetings/{meeting_id}",
            json={"title": "Admin Modified Title"},
            headers=auth_header(env["token_admin"]),
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["title"] == "Admin Modified Title"

        # Admin deletes
        del_res = await client.delete(
            f"/api/v1/meetings/{meeting_id}",
            headers=auth_header(env["token_admin"]),
        )
        assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_guest_cannot_create_meeting():
    """Verify workspace guests cannot create meetings (returns 403)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Guest Meeting Attempt"},
            headers=auth_header(env["token_guest"]),
        )
        assert res.status_code == 403
        assert "guests are not permitted" in res.json()["detail"].lower()


# ==========================================
# 4. Participants Management
# ==========================================


@pytest.mark.asyncio
async def test_add_and_list_participants():
    """Verify adding external and internal participants and listing them."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        create_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Sprint Review"},
            headers=auth_header(env["token_owner"]),
        )
        meeting_id = create_res.json()["id"]

        # Add external participant by email
        ext_res = await client.post(
            f"/api/v1/meetings/{meeting_id}/participants",
            json={"name": "External Client", "email": "client@external.com", "role": "attendee"},
            headers=auth_header(env["token_owner"]),
        )
        assert ext_res.status_code == 201
        assert ext_res.json()["email"] == "client@external.com"
        assert ext_res.json()["name"] == "External Client"

        # Add internal participant by user_id
        int_res = await client.post(
            f"/api/v1/meetings/{meeting_id}/participants",
            json={"user_id": env["member"]["id"], "role": "engineer"},
            headers=auth_header(env["token_owner"]),
        )
        assert int_res.status_code == 201
        assert int_res.json()["user_id"] == env["member"]["id"]
        assert int_res.json()["email"] == env["member"]["email"]

        # List participants
        list_res = await client.get(
            f"/api/v1/meetings/{meeting_id}/participants",
            headers=auth_header(env["token_member"]),
        )
        assert list_res.status_code == 200
        participants = list_res.json()
        assert len(participants) == 2


@pytest.mark.asyncio
async def test_duplicate_participant_rejected():
    """Verify duplicate participants in the same meeting return 409 Conflict."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        create_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Dup Test"},
            headers=auth_header(env["token_owner"]),
        )
        meeting_id = create_res.json()["id"]

        await client.post(
            f"/api/v1/meetings/{meeting_id}/participants",
            json={"email": "same@example.com", "name": "Person"},
            headers=auth_header(env["token_owner"]),
        )

        res = await client.post(
            f"/api/v1/meetings/{meeting_id}/participants",
            json={"email": "same@example.com", "name": "Person"},
            headers=auth_header(env["token_owner"]),
        )
        assert res.status_code == 409
        assert "already exists" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_participant_self_removal():
    """Verify a participant can remove themselves from a meeting."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        create_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Opt-out Meeting"},
            headers=auth_header(env["token_owner"]),
        )
        meeting_id = create_res.json()["id"]

        part_res = await client.post(
            f"/api/v1/meetings/{meeting_id}/participants",
            json={"user_id": env["member"]["id"]},
            headers=auth_header(env["token_owner"]),
        )
        part_id = part_res.json()["id"]

        # Member removes themselves
        del_res = await client.delete(
            f"/api/v1/meetings/{meeting_id}/participants/{part_id}",
            headers=auth_header(env["token_member"]),
        )
        assert del_res.status_code == 200


# ==========================================
# 5. Validation & State Transitions
# ==========================================


@pytest.mark.asyncio
async def test_meeting_validation_errors():
    """Verify empty title and invalid dates trigger validation errors."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        # Empty title
        res1 = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "   "},
            headers=auth_header(env["token_owner"]),
        )
        assert res1.status_code == 422

        # ended_at earlier than started_at
        now = datetime.now(timezone.utc)
        res2 = await client.post(
            "/api/v1/meetings",
            json={
                "workspace_id": ws_id,
                "title": "Invalid Dates",
                "started_at": now.isoformat(),
                "ended_at": (now - timedelta(hours=1)).isoformat(),
            },
            headers=auth_header(env["token_owner"]),
        )
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_invalid_status_transition_rejected():
    """Verify moving from terminal states returns 400 Bad Request."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        # Create meeting
        create_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Transition Test", "status": "scheduled"},
            headers=auth_header(env["token_owner"]),
        )
        meeting_id = create_res.json()["id"]

        # SCHEDULED -> CANCELLED (valid)
        res1 = await client.patch(
            f"/api/v1/meetings/{meeting_id}",
            json={"status": "cancelled"},
            headers=auth_header(env["token_owner"]),
        )
        assert res1.status_code == 200
        assert res1.json()["status"] == "CANCELLED"

        # CANCELLED -> IN_PROGRESS (invalid)
        res2 = await client.patch(
            f"/api/v1/meetings/{meeting_id}",
            json={"status": "in_progress"},
            headers=auth_header(env["token_owner"]),
        )
        assert res2.status_code == 400
        assert "invalid status transition" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_uuid_rejected():
    """Verify malformed UUID returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)

        res = await client.get(
            "/api/v1/meetings/not-a-valid-uuid",
            headers=auth_header(env["token_owner"]),
        )
        assert res.status_code == 422


# ==========================================
# 6. Filtering & Search
# ==========================================


@pytest.mark.asyncio
async def test_filtering_and_search():
    """Verify status, type, search, and date filters work accurately."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        # Meeting 1: Interview
        await client.post(
            "/api/v1/meetings",
            json={
                "workspace_id": ws_id,
                "title": "Engineering Candidate Interview",
                "meeting_type": "interview",
                "status": "scheduled",
            },
            headers=auth_header(env["token_owner"]),
        )

        # Meeting 2: Standup
        await client.post(
            "/api/v1/meetings",
            json={
                "workspace_id": ws_id,
                "title": "Daily Standup Meeting",
                "meeting_type": "standup",
                "status": "in_progress",
            },
            headers=auth_header(env["token_owner"]),
        )

        # Search by title "Candidate"
        search_res = await client.get(
            f"/api/v1/meetings?workspace_id={ws_id}&search=candidate",
            headers=auth_header(env["token_owner"]),
        )
        assert search_res.status_code == 200
        assert len(search_res.json()["items"]) == 1
        assert "Interview" in search_res.json()["items"][0]["title"]

        # Filter by status "IN_PROGRESS"
        status_res = await client.get(
            f"/api/v1/meetings?workspace_id={ws_id}&status=IN_PROGRESS",
            headers=auth_header(env["token_owner"]),
        )
        assert status_res.status_code == 200
        assert len(status_res.json()["items"]) == 1
        assert status_res.json()["items"][0]["meeting_type"] == "standup"

        # Filter by meeting_type "interview"
        type_res = await client.get(
            f"/api/v1/meetings?workspace_id={ws_id}&meeting_type=interview",
            headers=auth_header(env["token_owner"]),
        )
        assert type_res.status_code == 200
        assert len(type_res.json()["items"]) == 1
        assert type_res.json()["items"][0]["title"] == "Engineering Candidate Interview"


@pytest.mark.asyncio
async def test_empty_trash_returns_200():
    """Verify listing trash for user with zero trashed meetings returns 200 OK with empty items list."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        trash_res = await client.get(
            f"/api/v1/meetings/trash?workspace_id={ws_id}",
            headers=auth_header(env["token_owner"]),
        )
        assert trash_res.status_code == 200
        data = trash_res.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1


@pytest.mark.asyncio
async def test_trash_and_restore_lifecycle():
    """Verify trashing a meeting moves it to /trash and restoring returns it to main list."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        env = await setup_workspace_with_roles(client)
        ws_id = env["workspace"]["id"]

        # Create meeting
        m_res = await client.post(
            "/api/v1/meetings",
            json={"workspace_id": ws_id, "title": "Meeting to be trashed"},
            headers=auth_header(env["token_owner"]),
        )
        assert m_res.status_code == 201
        m_id = m_res.json()["id"]

        # Trash meeting (soft delete)
        del_res = await client.delete(
            f"/api/v1/meetings/{m_id}",
            headers=auth_header(env["token_owner"]),
        )
        assert del_res.status_code in (200, 204)

        # Verify meeting appears in /trash
        trash_res = await client.get(
            f"/api/v1/meetings/trash?workspace_id={ws_id}",
            headers=auth_header(env["token_owner"]),
        )
        assert trash_res.status_code == 200
        trash_items = trash_res.json()["items"]
        assert len(trash_items) == 1
        assert trash_items[0]["id"] == m_id

        # Restore meeting
        restore_res = await client.post(
            f"/api/v1/meetings/{m_id}/restore",
            headers=auth_header(env["token_owner"]),
        )
        assert restore_res.status_code == 200

        # Trash should be empty again
        trash_res_2 = await client.get(
            f"/api/v1/meetings/trash?workspace_id={ws_id}",
            headers=auth_header(env["token_owner"]),
        )
        assert trash_res_2.status_code == 200
        assert trash_res_2.json()["items"] == []

