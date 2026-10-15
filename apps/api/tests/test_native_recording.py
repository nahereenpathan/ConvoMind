"""Automated test suite for ConvoMind Phase 4 Native Meeting Recording APIs and Celery Pipeline integration."""

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
    client: AsyncClient, name: str = "Test Rec User"
) -> Tuple[Dict, str]:
    """Register and login a user, returning user payload and JWT token."""
    email = f"rec_{uuid.uuid4().hex[:8]}@convomind.ai"
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
        json={"name": f"Recording WS {uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_native_recording_lifecycle_and_security(client: AsyncClient) -> None:
    """Test Phase 4 native recording start, stop, duplicate prevention, and RBAC authorization."""
    # 1. Setup Host & Workspace
    host, host_token = await create_user_and_token(client, "Host User")
    host_headers = {"Authorization": f"Bearer {host_token}"}
    workspace = await create_workspace_helper(client, host_token)
    ws_id = workspace["id"]

    # 2. Setup Member & Stranger
    member, member_token = await create_user_and_token(client, "Member User")
    member_headers = {"Authorization": f"Bearer {member_token}"}

    add_mem = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member["email"], "role": "MEMBER"},
        headers=host_headers,
    )
    assert add_mem.status_code == 201

    stranger, stranger_token = await create_user_and_token(client, "Stranger User")
    stranger_headers = {"Authorization": f"Bearer {stranger_token}"}

    # 3. Host creates meeting and joins native room
    create_mtg = await client.post(
        "/api/v1/meetings",
        json={"workspace_id": ws_id, "title": "Native Recording Test Meeting"},
        headers=host_headers,
    )
    assert create_mtg.status_code == 201
    meeting_id = create_mtg.json()["id"]

    host_join = await client.post(
        f"/api/v1/meetings/{meeting_id}/join",
        headers=host_headers,
    )
    assert host_join.status_code == 200

    # 4. Member attempts to START recording -> Rejected (403 Forbidden)
    member_start = await client.post(
        f"/api/v1/meetings/{meeting_id}/recording/start",
        headers=member_headers,
    )
    assert member_start.status_code == 403

    # 5. Stranger attempts to START recording -> Rejected (404 Not Found)
    stranger_start = await client.post(
        f"/api/v1/meetings/{meeting_id}/recording/start",
        headers=stranger_headers,
    )
    assert stranger_start.status_code == 404

    # 6. Host STARTS recording -> Succeeds (200 OK)
    host_start = await client.post(
        f"/api/v1/meetings/{meeting_id}/recording/start",
        headers=host_headers,
    )
    assert host_start.status_code == 200
    start_data = host_start.json()
    assert start_data["status"] == "RECORDING"
    assert "recording_id" in start_data

    # 7. Host attempts to START duplicate active recording -> Rejected (400 Bad Request)
    duplicate_start = await client.post(
        f"/api/v1/meetings/{meeting_id}/recording/start",
        headers=host_headers,
    )
    assert duplicate_start.status_code == 400

    # 8. Member attempts to STOP recording -> Rejected (403 Forbidden)
    member_stop = await client.post(
        f"/api/v1/meetings/{meeting_id}/recording/stop",
        headers=member_headers,
    )
    assert member_stop.status_code == 403

    # 9. Host STOPS recording -> Finalizes artifact and enqueues Celery task (200 OK)
    host_stop = await client.post(
        f"/api/v1/meetings/{meeting_id}/recording/stop",
        headers=host_headers,
    )
    assert host_stop.status_code == 200
    stop_data = host_stop.json()
    assert stop_data["status"] == "QUEUED"
    assert stop_data["file_size"] > 0

    # 10. Stop when no active recording exists -> Rejected (400 Bad Request)
    stop_again = await client.post(
        f"/api/v1/meetings/{meeting_id}/recording/stop",
        headers=host_headers,
    )
    assert stop_again.status_code == 400

    # 11. Verify recording appears in meeting recordings list
    get_recs = await client.get(
        f"/api/v1/meetings/{meeting_id}/recordings",
        headers=host_headers,
    )
    assert get_recs.status_code == 200
    recs_list = get_recs.json()["items"]
    assert len(recs_list) >= 1
