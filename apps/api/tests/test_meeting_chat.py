"""Automated test suite for ConvoMind Phase 3 In-Meeting Chat APIs and RBAC Security."""

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
    client: AsyncClient, name: str = "Test Chat User"
) -> Tuple[Dict, str]:
    """Register and login a user, returning user payload and JWT token."""
    email = f"chat_{uuid.uuid4().hex[:8]}@convomind.ai"
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
        json={"name": f"Chat WS {uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()


@pytest.mark.asyncio
async def test_meeting_chat_lifecycle_and_rbac(client: AsyncClient) -> None:
    """Test full Phase 3 Meeting Chat flow, message validation, and RBAC authorization."""
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

    # 3. Create Meeting & Init Native Room
    create_mtg = await client.post(
        "/api/v1/meetings",
        json={"workspace_id": ws_id, "title": "Phase 3 Chat & Screen Share Sync"},
        headers=host_headers,
    )
    assert create_mtg.status_code == 201
    meeting_id = create_mtg.json()["id"]

    # 4. Empty Chat List Initially
    get_msgs_1 = await client.get(
        f"/api/v1/meetings/{meeting_id}/messages",
        headers=host_headers,
    )
    assert get_msgs_1.status_code == 200
    assert len(get_msgs_1.json()) == 0

    # 5. Host sends chat message
    send_1 = await client.post(
        f"/api/v1/meetings/{meeting_id}/messages",
        json={"message": "Welcome to the Phase 3 sync!"},
        headers=host_headers,
    )
    assert send_1.status_code == 201
    msg1_data = send_1.json()
    assert msg1_data["message"] == "Welcome to the Phase 3 sync!"
    assert msg1_data["sender_name"] == "Host User"

    # 6. Member sends chat message
    send_2 = await client.post(
        f"/api/v1/meetings/{meeting_id}/messages",
        json={"message": "Thanks! Ready to present screen."},
        headers=member_headers,
    )
    assert send_2.status_code == 201
    msg2_data = send_2.json()
    assert msg2_data["sender_name"] == "Member User"

    # 7. Reject empty message (422/400 validation)
    send_empty = await client.post(
        f"/api/v1/meetings/{meeting_id}/messages",
        json={"message": "   "},
        headers=member_headers,
    )
    assert send_empty.status_code in (400, 422)

    # 8. Stranger attempts to read messages -> Rejected (404 Not Found)
    stranger_get = await client.get(
        f"/api/v1/meetings/{meeting_id}/messages",
        headers=stranger_headers,
    )
    assert stranger_get.status_code == 404

    # 9. Stranger attempts to send message -> Rejected (404 Not Found)
    stranger_send = await client.post(
        f"/api/v1/meetings/{meeting_id}/messages",
        json={"message": "Unauthorized intrusion"},
        headers=stranger_headers,
    )
    assert stranger_send.status_code == 404

    # 10. Fetch chat history for authorized member
    get_msgs_final = await client.get(
        f"/api/v1/meetings/{meeting_id}/messages",
        headers=member_headers,
    )
    assert get_msgs_final.status_code == 200
    msgs_list = get_msgs_final.json()
    assert len(msgs_list) == 2
    assert msgs_list[0]["message"] == "Welcome to the Phase 3 sync!"
    assert msgs_list[1]["message"] == "Thanks! Ready to present screen."
