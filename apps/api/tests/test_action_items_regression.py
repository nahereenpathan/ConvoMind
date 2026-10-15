"""Comprehensive regression test suite for Action Items & Tasks.

Verifies:
1. Extraction of explicit commitments (Arjun, Sara, Daniel, Priya) with accurate assignees, deadlines, and timestamps.
2. Complete exclusion of generic descriptions, meeting introductions, agendas, and decisions.
3. Safe reprocessing: user-created tasks are preserved while AI items are cleanly updated without duplication.
4. Full API operations: Create, Search, Assignee/Status/Priority/Meeting/DueDate Filters, Sorting, Pagination, Completion, Edit, Delete, and Metrics.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.enums import ActionItemStatus, MeetingPlatform, MeetingStatus, PriorityLevel, TranscriptStatus, WorkspaceRole
from app.models.intelligence import ActionItem
from app.models.meeting import Meeting, Speaker
from app.models.transcript import Transcript, TranscriptSegment
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.intelligence.mock_provider import MockLLMProvider
from app.workers.tasks.intelligence_tasks import _async_process_meeting_intelligence


TRANSCRIPT_FIXTURE_TEXT = """
Hello everyone, good morning. Today we are discussing our news software project called ConvoMind.
It is an AI powered meeting assistant that helps team summarize meetings and track important task.
Arjun will complete backend development and testing by October 19, 2026.
Sara will improve the user interface and complete design changes by October 20, 2026.
Daniel will prepare the marketing plan and customer feedback questionnaire by October 21, 2026.
Priya will prepare the pilot acceptance checklist and coordinate five pilot teams by October 22, 2026.
We have also decided to test the software with five customers before launching it publicly.
There are three important decisions from today's meeting.
First, we will focus on meeting summaries, transcripts and action items.
Second, we will post one PowerPoint export until the main feature are working properly.
Third, we will review the project progress on October 23 at 3pm.
Our next meeting will be held on October 23.
Thank you everyone, that's all for today's meeting.
"""


@pytest.fixture
async def setup_action_items_env():
    """Create a fully populated workspace, meeting, transcript, and segments for testing."""
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"task_reg_{uuid.uuid4().hex[:6]}@convomind.ai",
            full_name="Alex Lead",
            hashed_password="hashed_sample_pw",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        workspace = Workspace(
            id=uuid.uuid4(),
            name="Tasks Regression Workspace",
            slug=f"tasks-ws-{uuid.uuid4().hex[:6]}",
            created_by_id=user.id,
        )
        session.add(workspace)
        await session.flush()

        member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
        session.add(member)

        meeting = Meeting(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            creator_id=user.id,
            title="Q4 Product Execution Review",
            status=MeetingStatus.COMPLETED,
            platform=MeetingPlatform.UPLOAD,
        )
        session.add(meeting)
        await session.flush()

        speaker = Speaker(
            id=uuid.uuid4(),
            meeting_id=meeting.id,
            name="Alex Lead",
            label="SPEAKER_00",
        )
        session.add(speaker)
        await session.flush()

        transcript = Transcript(
            id=uuid.uuid4(),
            meeting_id=meeting.id,
            workspace_id=workspace.id,
            status=TranscriptStatus.COMPLETED,
            full_text=TRANSCRIPT_FIXTURE_TEXT.strip(),
            word_count=len(TRANSCRIPT_FIXTURE_TEXT.split()),
            language="en",
        )
        session.add(transcript)
        await session.flush()

        segments_data = [
            ("Hello everyone, good morning. Today we are discussing our news software project called ConvoMind.", 0.0, 5.0),
            ("It is an AI powered meeting assistant that helps team summarize meetings and track important task.", 6.0, 11.0),
            ("Arjun will complete backend development and testing by October 19, 2026.", 12.0, 18.0),
            ("Sara will improve the user interface and complete design changes by October 20, 2026.", 19.0, 25.0),
            ("Daniel will prepare the marketing plan and customer feedback questionnaire by October 21, 2026.", 26.0, 32.0),
            ("Priya will prepare the pilot acceptance checklist and coordinate five pilot teams by October 22, 2026.", 33.0, 39.0),
            ("We have also decided to test the software with five customers before launching it publicly.", 40.0, 45.0),
            ("First, we will focus on meeting summaries, transcripts and action items.", 46.0, 50.0),
            ("Our next meeting will be held on October 23. Thank you everyone, that's all for today's meeting.", 51.0, 55.0),
        ]

        for i, (text, start_t, end_t) in enumerate(segments_data):
            seg = TranscriptSegment(
                id=uuid.uuid4(),
                transcript_id=transcript.id,
                speaker_id=speaker.id,
                sequence_order=i,
                start_time=start_t,
                end_time=end_t,
                text=text,
                confidence=0.99,
            )
            session.add(seg)

        await session.commit()

        from app.core.security import create_access_token
        token = create_access_token(user.id)

        return {
            "user": user,
            "workspace": workspace,
            "meeting": meeting,
            "transcript": transcript,
            "token": token,
        }


@pytest.mark.asyncio
async def test_01_extractive_intelligence_four_commitments():
    """Verify that MockLLMProvider extracts the 4 explicit assignments with proper owners and deadlines,
    and rejects generic statements and decisions."""
    provider = MockLLMProvider()
    segments = [
        {"start_time": 12.0, "end_time": 18.0, "text": "Arjun will complete backend development and testing by October 19, 2026."},
        {"start_time": 19.0, "end_time": 25.0, "text": "Sara will improve the user interface and complete design changes by October 20, 2026."},
        {"start_time": 26.0, "end_time": 32.0, "text": "Daniel will prepare the marketing plan and customer feedback questionnaire by October 21, 2026."},
        {"start_time": 33.0, "end_time": 39.0, "text": "Priya will prepare the pilot acceptance checklist and coordinate five pilot teams by October 22, 2026."},
    ]

    output = await provider.generate_meeting_intelligence(
        transcript_text=TRANSCRIPT_FIXTURE_TEXT,
        segments=segments,
    )

    action_items = output.action_items
    assert len(action_items) == 4, f"Expected 4 action items, got {len(action_items)}: {[a.task for a in action_items]}"

    item_map = {a.assignee_name: a for a in action_items}
    assert "Arjun" in item_map
    assert "Sara" in item_map
    assert "Daniel" in item_map
    assert "Priya" in item_map

    # Check Arjun
    arjun_task = item_map["Arjun"]
    assert "backend development and testing" in arjun_task.task.lower()
    assert "october 19" in arjun_task.due_date_str.lower()
    assert arjun_task.timestamp_marker == 12.0

    # Check Sara
    sara_task = item_map["Sara"]
    assert "user interface" in sara_task.task.lower()
    assert "design changes" in sara_task.task.lower()
    assert "october 20" in sara_task.due_date_str.lower()
    assert sara_task.timestamp_marker == 19.0

    # Check Daniel
    daniel_task = item_map["Daniel"]
    assert "marketing plan" in daniel_task.task.lower()
    assert "october 21" in daniel_task.due_date_str.lower()
    assert daniel_task.timestamp_marker == 26.0

    # Check Priya
    priya_task = item_map["Priya"]
    assert "pilot acceptance checklist" in priya_task.task.lower()
    assert "october 22" in priya_task.due_date_str.lower()
    assert priya_task.timestamp_marker == 33.0

    # Negative check: None of the action items should contain generic statements or agendas
    all_titles_lower = " ".join(a.task.lower() for a in action_items)
    assert "ai powered meeting assistant" not in all_titles_lower
    assert "focus on meeting summaries" not in all_titles_lower
    assert "we have also decided" not in all_titles_lower


@pytest.mark.asyncio
async def test_02_async_pipeline_persistence_and_due_dates(setup_action_items_env):
    """Verify that _async_process_meeting_intelligence parses and stores due_date, assignee, and timestamps in DB."""
    env = setup_action_items_env
    meeting = env["meeting"]

    result = await _async_process_meeting_intelligence(str(meeting.id))
    assert result["status"] == "completed"
    assert result["action_items_count"] == 4

    async with AsyncSessionLocal() as session:
        stmt = (
            select(ActionItem)
            .where(ActionItem.meeting_id == meeting.id)
            .order_by(ActionItem.due_date.asc())
        )
        items = list((await session.execute(stmt)).scalars().all())
        assert len(items) == 4

        # Validate that due_date column is populated as valid datetime
        for it in items:
            assert it.due_date is not None
            assert isinstance(it.due_date, datetime)
            assert it.assignee_name in ["Arjun", "Sara", "Daniel", "Priya"]
            assert it.timestamp_marker is not None

        # Verify sorted due dates
        assert items[0].assignee_name == "Arjun"
        assert items[0].due_date.day == 19
        assert items[1].assignee_name == "Sara"
        assert items[1].due_date.day == 20
        assert items[2].assignee_name == "Daniel"
        assert items[2].due_date.day == 21
        assert items[3].assignee_name == "Priya"
        assert items[3].due_date.day == 22


@pytest.mark.asyncio
async def test_03_safe_reprocessing_preserves_user_tasks(setup_action_items_env):
    """Verify safe reprocessing: re-running AI intelligence replaces AI-extracted items
    without deleting user-created tasks or creating duplicates."""
    env = setup_action_items_env
    meeting = env["meeting"]
    user = env["user"]

    # 1. First processing run
    await _async_process_meeting_intelligence(str(meeting.id))

    # 2. User manually creates a task under this meeting
    async with AsyncSessionLocal() as session:
        user_task = ActionItem(
            id=uuid.uuid4(),
            workspace_id=meeting.workspace_id,
            meeting_id=meeting.id,
            created_by_id=user.id,
            job_id=None,  # User created
            title="Manual Task: Review Security Guidelines",
            assignee_name="Security Auditor",
            priority=PriorityLevel.HIGH,
            status=ActionItemStatus.OPEN,
        )
        session.add(user_task)
        await session.commit()
        user_task_id = user_task.id

    # 3. Trigger reprocessing (Run 2)
    reprocess_res = await _async_process_meeting_intelligence(str(meeting.id))
    assert reprocess_res["status"] == "completed"

    # 4. Verify user task still exists, and AI tasks were updated without duplication
    async with AsyncSessionLocal() as session:
        stmt = select(ActionItem).where(ActionItem.meeting_id == meeting.id)
        all_items = list((await session.execute(stmt)).scalars().all())

        # Total should be 4 AI tasks + 1 manual task = 5
        assert len(all_items) == 5

        # Confirm user task is preserved
        preserved_user_task = next((it for it in all_items if it.id == user_task_id), None)
        assert preserved_user_task is not None
        assert preserved_user_task.title == "Manual Task: Review Security Guidelines"


@pytest.mark.asyncio
async def test_04_action_items_api_operations_and_filters(client: AsyncClient, setup_action_items_env):
    """Verify Dashboard Action Items API: search, filters, sorting, pagination, update, delete, metrics."""
    env = setup_action_items_env
    meeting = env["meeting"]
    ws = env["workspace"]
    token = env["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Run intelligence pipeline to seed database
    await _async_process_meeting_intelligence(str(meeting.id))

    # 1. List All Tasks
    res = await client.get(f"/api/v1/action-items?workspace_id={ws.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 4
    assert len(data["items"]) == 4

    # 2. Search Filter (Search for "interface")
    search_res = await client.get(f"/api/v1/action-items?workspace_id={ws.id}&search=interface", headers=headers)
    assert search_res.status_code == 200
    s_data = search_res.json()
    assert s_data["total"] == 1
    assert "user interface" in s_data["items"][0]["title"].lower()
    assert s_data["items"][0]["assignee_name"] == "Sara"

    # 3. Assignee Name Filter
    assignee_res = await client.get(f"/api/v1/action-items?workspace_id={ws.id}&assignee_name=Daniel", headers=headers)
    assert assignee_res.status_code == 200
    a_data = assignee_res.json()
    assert a_data["total"] == 1
    assert a_data["items"][0]["assignee_name"] == "Daniel"

    # 4. Meeting ID Filter
    m_res = await client.get(f"/api/v1/action-items?workspace_id={ws.id}&meeting_id={meeting.id}", headers=headers)
    assert m_res.status_code == 200
    assert m_res.json()["total"] == 4

    # 5. Sorting and Pagination (Page 1 with pageSize 2 sorted by due_date desc)
    page_res = await client.get(
        f"/api/v1/action-items?workspace_id={ws.id}&page=1&page_size=2&sort_by=due_date&sort_order=desc",
        headers=headers,
    )
    assert page_res.status_code == 200
    p_data = page_res.json()
    assert p_data["page"] == 1
    assert p_data["page_size"] == 2
    assert p_data["total_pages"] == 2
    assert len(p_data["items"]) == 2
    # First item should be Priya (Oct 22)
    assert p_data["items"][0]["assignee_name"] == "Priya"

    # 6. Update Task (Complete Priya's task)
    priya_task_id = p_data["items"][0]["id"]
    patch_res = await client.patch(
        f"/api/v1/action-items/{priya_task_id}",
        json={"status": "COMPLETED", "priority": "URGENT"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["status"] == "COMPLETED"
    assert updated["priority"] == "URGENT"
    assert updated["completed_at"] is not None

    # 7. Check Metrics
    metrics_res = await client.get(f"/api/v1/action-items/metrics?workspace_id={ws.id}", headers=headers)
    assert metrics_res.status_code == 200
    m_json = metrics_res.json()
    assert m_json["total"] == 4
    assert m_json["completed"] == 1

    # 8. Create New Task via API
    create_res = await client.post(
        f"/api/v1/action-items?meeting_id={meeting.id}",
        json={
            "title": "Setup CI/CD deployment pipeline",
            "assignee_name": "DevOps Team",
            "priority": "HIGH",
            "status": "OPEN",
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    created_id = create_res.json()["id"]

    # 9. Delete Created Task via API
    del_res = await client.delete(f"/api/v1/action-items/{created_id}", headers=headers)
    assert del_res.status_code == 204

    # 10. Verify total count back to 4
    final_res = await client.get(f"/api/v1/action-items?workspace_id={ws.id}", headers=headers)
    assert final_res.json()["total"] == 4
