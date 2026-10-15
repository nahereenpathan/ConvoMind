"""Automated test suite for Workspace Action Items & Tasks management."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.models.enums import ActionItemStatus, PriorityLevel, WorkspaceRole
from app.models.intelligence import ActionItem
from app.models.meeting import Meeting


async def create_user_and_token(
    client: AsyncClient, name: str = "Test User"
) -> Tuple[Dict, str]:
    """Register and login a user, returning user data and JWT access token."""
    email = f"task_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "Password123!"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert reg.status_code == 201, reg.text

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return reg.json(), token


def auth_header(token: str) -> Dict[str, str]:
    """Helper for Bearer authorization header."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def task_fixture(client: AsyncClient) -> Dict:
    """Fixture creating workspaces, members, and meetings for testing."""
    owner, t_owner = await create_user_and_token(client, "Task Owner")
    member, t_member = await create_user_and_token(client, "Task Member")
    stranger, t_stranger = await create_user_and_token(client, "Task Stranger")

    # Create workspace 1
    ws1_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace One"},
        headers=auth_header(t_owner),
    )
    assert ws1_res.status_code == 201
    ws1 = ws1_res.json()

    # Add member to workspace 1
    add_mem = await client.post(
        f"/api/v1/workspaces/{ws1['id']}/members",
        json={"email": member["email"], "role": "MEMBER"},
        headers=auth_header(t_owner),
    )
    assert add_mem.status_code == 201

    # Create workspace 2 (isolated)
    ws2_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Workspace Two"},
        headers=auth_header(t_stranger),
    )
    assert ws2_res.status_code == 201
    ws2 = ws2_res.json()

    # Create meeting under workspace 1
    m1_res = await client.post(
        "/api/v1/meetings",
        json={"workspace_id": ws1["id"], "title": "Project Sprint Review"},
        headers=auth_header(t_owner),
    )
    assert m1_res.status_code == 201
    m1 = m1_res.json()

    # Create meeting under workspace 2
    m2_res = await client.post(
        "/api/v1/meetings",
        json={"workspace_id": ws2["id"], "title": "Secret Meeting"},
        headers=auth_header(t_stranger),
    )
    assert m2_res.status_code == 201
    m2 = m2_res.json()

    return {
        "owner": owner,
        "t_owner": t_owner,
        "member": member,
        "t_member": t_member,
        "stranger": stranger,
        "t_stranger": t_stranger,
        "ws1": ws1,
        "ws2": ws2,
        "m1": m1,
        "m2": m2,
    }


@pytest.mark.asyncio
async def test_empty_action_items_returns_200(client: AsyncClient, task_fixture: Dict):
    """Verify listing action items for a workspace with zero items returns 200 with empty list structure."""
    res = await client.get(
        f"/api/v1/action-items?workspace_id={task_fixture['ws1']['id']}",
        headers=auth_header(task_fixture["t_owner"]),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_create_and_get_action_item(client: AsyncClient, task_fixture: Dict):
    """Verify creating a task and fetching workspace action items."""
    # Create task
    create_res = await client.post(
        f"/api/v1/action-items?meeting_id={task_fixture['m1']['id']}",
        json={
            "title": "Implement authentication middleware",
            "description": "Ensure JWT tokens are validated on protected routes.",
            "assignee_name": task_fixture["member"]["full_name"],
            "priority": "HIGH",
            "status": "OPEN",
        },
        headers=auth_header(task_fixture["t_owner"]),
    )
    assert create_res.status_code == 201, create_res.text
    created = create_res.json()
    assert created["title"] == "Implement authentication middleware"
    assert created["priority"] == "HIGH"

    # Fetch workspace action items
    get_res = await client.get(
        f"/api/v1/action-items?workspace_id={task_fixture['ws1']['id']}",
        headers=auth_header(task_fixture["t_owner"]),
    )
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == created["id"]
    assert data["items"][0]["meeting_title"] == "Project Sprint Review"


@pytest.mark.asyncio
async def test_workspace_isolation(client: AsyncClient, task_fixture: Dict):
    """Verify strict multi-tenant workspace isolation (Stranger cannot see WS1 items)."""
    # Create task in WS1
    await client.post(
        f"/api/v1/action-items?meeting_id={task_fixture['m1']['id']}",
        json={"title": "WS1 Task"},
        headers=auth_header(task_fixture["t_owner"]),
    )

    # Stranger tries to query WS1 action items -> 403 Forbidden
    res = await client.get(
        f"/api/v1/action-items?workspace_id={task_fixture['ws1']['id']}",
        headers=auth_header(task_fixture["t_stranger"]),
    )
    assert res.status_code in (403, 404)


@pytest.mark.asyncio
async def test_action_item_metrics(client: AsyncClient, task_fixture: Dict):
    """Verify action item metrics endpoint computes correct total, my_tasks, overdue, completed."""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    tomorrow = now + timedelta(days=1)

    # 1. Open task assigned to member
    await client.post(
        f"/api/v1/action-items?meeting_id={task_fixture['m1']['id']}",
        json={
            "title": "Open Task",
            "assignee_name": task_fixture["member"]["full_name"],
            "due_date": tomorrow.isoformat(),
            "status": "OPEN",
        },
        headers=auth_header(task_fixture["t_owner"]),
    )

    # 2. Overdue task
    await client.post(
        f"/api/v1/action-items?meeting_id={task_fixture['m1']['id']}",
        json={
            "title": "Overdue Task",
            "due_date": yesterday.isoformat(),
            "status": "OPEN",
        },
        headers=auth_header(task_fixture["t_owner"]),
    )

    # 3. Completed task
    await client.post(
        f"/api/v1/action-items?meeting_id={task_fixture['m1']['id']}",
        json={
            "title": "Completed Task",
            "status": "COMPLETED",
        },
        headers=auth_header(task_fixture["t_owner"]),
    )

    # Get metrics for member
    res = await client.get(
        f"/api/v1/action-items/metrics?workspace_id={task_fixture['ws1']['id']}",
        headers=auth_header(task_fixture["t_member"]),
    )
    assert res.status_code == 200
    metrics = res.json()
    assert metrics["total"] == 3
    assert metrics["my_tasks"] == 1
    assert metrics["overdue"] == 1
    assert metrics["completed"] == 1


@pytest.mark.asyncio
async def test_update_and_delete_action_item(client: AsyncClient, task_fixture: Dict):
    """Verify updating and deleting action items."""
    create_res = await client.post(
        f"/api/v1/action-items?meeting_id={task_fixture['m1']['id']}",
        json={"title": "Draft API Spec", "status": "OPEN"},
        headers=auth_header(task_fixture["t_owner"]),
    )
    task_id = create_res.json()["id"]

    # Update task
    patch_res = await client.patch(
        f"/api/v1/action-items/{task_id}",
        json={"title": "Updated API Spec", "status": "COMPLETED", "priority": "URGENT"},
        headers=auth_header(task_fixture["t_owner"]),
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["title"] == "Updated API Spec"
    assert updated["status"] == "COMPLETED"
    assert updated["priority"] == "URGENT"
    assert updated["completed_at"] is not None

    # Delete task
    del_res = await client.delete(
        f"/api/v1/action-items/{task_id}",
        headers=auth_header(task_fixture["t_owner"]),
    )
    assert del_res.status_code == 204

    # Verify task is deleted
    list_res = await client.get(
        f"/api/v1/action-items?workspace_id={task_fixture['ws1']['id']}",
        headers=auth_header(task_fixture["t_owner"]),
    )
    assert list_res.json()["total"] == 0
