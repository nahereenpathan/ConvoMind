"""Automated test suite for ConvoMind Native Meeting Platform Foundation (Phase 1)."""

import uuid
from typing import Dict, Tuple
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    """Async test client instance."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def create_user_and_token(
    client: AsyncClient, name: str = "Test Native User"
) -> Tuple[Dict, str]:
    """Register and login a user, returning user payload and JWT token."""
    email = f"native_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "Password123!"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert reg.status_code == 201
    user_data = reg.json()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return user_data, token


async def create_workspace_helper(client: AsyncClient, token: str) -> Dict:
    """Create a workspace for testing."""
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.post(
        "/api/v1/workspaces",
        json={"name": f"Native WS {uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_native_meeting_lifecycle_and_security(client: AsyncClient) -> None:
    """Test full Phase 1 Native Meeting lifecycle, token generation, and RBAC security."""
    # 1. Setup Host & Workspace
    host, host_token = await create_user_and_token(client, "Host User")
    host_headers = {"Authorization": f"Bearer {host_token}"}
    workspace = await create_workspace_helper(client, host_token)
    ws_id = workspace["id"]

    # 2. Setup Regular Member & Stranger
    member, member_token = await create_user_and_token(client, "Member User")
    member_headers = {"Authorization": f"Bearer {member_token}"}
    
    # Add member to workspace
    add_mem = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member["email"], "role": "MEMBER"},
        headers=host_headers,
    )
    assert add_mem.status_code == 201

    stranger, stranger_token = await create_user_and_token(client, "Stranger User")
    stranger_headers = {"Authorization": f"Bearer {stranger_token}"}

    # 3. Host creates a Meeting
    create_mtg = await client.post(
        "/api/v1/meetings",
        json={"workspace_id": ws_id, "title": "Native Sprint Standup"},
        headers=host_headers,
    )
    assert create_mtg.status_code == 201
    meeting = create_mtg.json()
    meeting_id = meeting["id"]

    # 4. Host initializes Native Room
    init_room = await client.post(
        f"/api/v1/meetings/{meeting_id}/native-room",
        headers=host_headers,
    )
    assert init_room.status_code == 200
    room_init_data = init_room.json()
    assert room_init_data["is_native"] is True
    assert room_init_data["room_id"].startswith("cm_room_")
    assert room_init_data["room_status"] == "IDLE"

    # 5. Stranger attempts to join native room -> Rejected (404/403)
    stranger_join = await client.post(
        f"/api/v1/meetings/{meeting_id}/join",
        headers=stranger_headers,
    )
    assert stranger_join.status_code in (404, 403)

    # 6. Host joins Native Room -> Generates signed token & sets room_status="ACTIVE"
    host_join = await client.post(
        f"/api/v1/meetings/{meeting_id}/join",
        headers=host_headers,
    )
    assert host_join.status_code == 200
    host_join_data = host_join.json()
    assert host_join_data["is_host"] is True
    assert host_join_data["token"].startswith("mock_lk_token_") or len(host_join_data["token"]) > 20
    assert host_join_data["room_status"] == "ACTIVE"

    # 7. Workspace Member joins Native Room -> Generates member token
    member_join = await client.post(
        f"/api/v1/meetings/{meeting_id}/join",
        headers=member_headers,
    )
    assert member_join.status_code == 200
    member_join_data = member_join.json()
    assert member_join_data["is_host"] is False
    assert member_join_data["token"] != ""

    # 8. Check Room Presence & Status Endpoint
    get_room = await client.get(
        f"/api/v1/meetings/{meeting_id}/room",
        headers=member_headers,
    )
    assert get_room.status_code == 200
    room_status_data = get_room.json()
    assert room_status_data["room_status"] == "ACTIVE"
    assert room_status_data["active_participants_count"] == 2

    # 9. Regular Member attempts to END meeting -> Rejected (403 Forbidden)
    member_end = await client.post(
        f"/api/v1/meetings/{meeting_id}/end",
        headers=member_headers,
    )
    assert member_end.status_code == 403

    # 10. Host ENDS meeting for all -> Status changes to COMPLETED / CLOSED
    host_end = await client.post(
        f"/api/v1/meetings/{meeting_id}/end",
        headers=host_headers,
    )
    assert host_end.status_code == 200
    ended_data = host_end.json()
    assert ended_data["status"] == "COMPLETED"
    assert ended_data["room_status"] == "CLOSED"

    # 11. Member attempts to rejoin ENDED meeting -> Rejected (400 Bad Request)
    rejoin_ended = await client.post(
        f"/api/v1/meetings/{meeting_id}/join",
        headers=member_headers,
    )
    assert rejoin_ended.status_code == 400
