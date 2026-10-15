"""Comprehensive Automated Regression Test Suite for Meeting Data Isolation.

Fixtures:
Meeting A:
  Title: "Marketing Planning"
  Transcript: "Marketing Meeting. Arjun will prepare the marketing campaign by October 19. Sara will review the advertising design by October 20."

Meeting B:
  Title: "Clinic Appointment Planning"
  Transcript: "Clinic Planning Meeting. Priya will configure appointment booking by October 22. Daniel will test receptionist availability by October 23."

Verifies all 14 Phase 9 requirements.
"""

import asyncio
import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select, delete

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.chat import ChatConversation
from app.models.embedding import TranscriptEmbedding
from app.models.enums import (
    ActionItemStatus,
    IntelligenceStatus,
    MeetingPlatform,
    MeetingStatus,
    PriorityLevel,
    TranscriptStatus,
    WorkspaceRole,
)
from app.models.intelligence import ActionItem, Decision, MeetingIntelligenceJob, MeetingSummary
from app.models.meeting import Meeting, Speaker
from app.models.notification import NotificationPreference
from app.models.transcript import Transcript, TranscriptSegment
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.rag.rag_service import RAGService
from app.workers.tasks.embedding_tasks import _async_process_transcript_embeddings
from app.workers.tasks.intelligence_tasks import _async_process_meeting_intelligence


MEETING_A_TRANSCRIPT = (
    "Marketing Meeting. Arjun will prepare the marketing campaign by October 19. "
    "Sara will review the advertising design by October 20."
)

MEETING_B_TRANSCRIPT = (
    "Clinic Planning Meeting. Priya will configure appointment booking by October 22. "
    "Daniel will test receptionist availability by October 23."
)


@pytest.fixture
async def isolation_environment():
    """Create two fully independent meetings (Meeting A: Marketing, Meeting B: Clinic)
    in the same workspace, plus an isolated second workspace and user."""
    async with AsyncSessionLocal() as session:
        # User & Workspace 1 (Primary)
        user_1 = User(
            id=uuid.uuid4(),
            email=f"primary_user_{uuid.uuid4().hex[:6]}@convomind.ai",
            full_name="Primary User",
            hashed_password="hashed_pw_sample",
            is_active=True,
        )
        session.add(user_1)
        session.add(NotificationPreference(user_id=user_1.id))
        await session.flush()

        ws_1 = Workspace(
            id=uuid.uuid4(),
            name="Primary Workspace",
            slug=f"ws-prim-{uuid.uuid4().hex[:6]}",
            created_by_id=user_1.id,
        )
        session.add(ws_1)
        await session.flush()

        wm_1 = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_1.id,
            user_id=user_1.id,
            role=WorkspaceRole.OWNER,
        )
        session.add(wm_1)

        # User & Workspace 2 (For multi-tenant isolation testing)
        user_2 = User(
            id=uuid.uuid4(),
            email=f"isolated_user_{uuid.uuid4().hex[:6]}@convomind.ai",
            full_name="Isolated User",
            hashed_password="hashed_pw_sample",
            is_active=True,
        )
        session.add(user_2)
        session.add(NotificationPreference(user_id=user_2.id))
        await session.flush()

        ws_2 = Workspace(
            id=uuid.uuid4(),
            name="Isolated Workspace",
            slug=f"ws-iso-{uuid.uuid4().hex[:6]}",
            created_by_id=user_2.id,
        )
        session.add(ws_2)
        await session.flush()

        wm_2 = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_2.id,
            user_id=user_2.id,
            role=WorkspaceRole.OWNER,
        )
        session.add(wm_2)

        # ---------------- Meeting A: Marketing ----------------
        meeting_a = Meeting(
            id=uuid.uuid4(),
            workspace_id=ws_1.id,
            creator_id=user_1.id,
            title="Marketing Planning",
            status=MeetingStatus.COMPLETED,
            platform=MeetingPlatform.UPLOAD,
        )
        session.add(meeting_a)
        await session.flush()

        speaker_a = Speaker(
            id=uuid.uuid4(),
            meeting_id=meeting_a.id,
            name="Marketing Lead",
            label="SPEAKER_00",
        )
        session.add(speaker_a)
        await session.flush()

        transcript_a = Transcript(
            id=uuid.uuid4(),
            meeting_id=meeting_a.id,
            workspace_id=ws_1.id,
            status=TranscriptStatus.COMPLETED,
            full_text=MEETING_A_TRANSCRIPT,
            word_count=len(MEETING_A_TRANSCRIPT.split()),
            language="en",
        )
        session.add(transcript_a)
        await session.flush()

        seg_a_data = [
            ("Marketing Meeting.", 0.0, 4.0),
            ("Arjun will prepare the marketing campaign by October 19.", 4.0, 11.0),
            ("Sara will review the advertising design by October 20.", 11.0, 18.0),
        ]
        for idx, (txt, st, et) in enumerate(seg_a_data):
            session.add(
                TranscriptSegment(
                    id=uuid.uuid4(),
                    transcript_id=transcript_a.id,
                    speaker_id=speaker_a.id,
                    sequence_order=idx,
                    start_time=st,
                    end_time=et,
                    text=txt,
                    confidence=0.99,
                )
            )

        # ---------------- Meeting B: Clinic ----------------
        meeting_b = Meeting(
            id=uuid.uuid4(),
            workspace_id=ws_1.id,
            creator_id=user_1.id,
            title="Clinic Appointment Planning",
            status=MeetingStatus.COMPLETED,
            platform=MeetingPlatform.UPLOAD,
        )
        session.add(meeting_b)
        await session.flush()

        speaker_b = Speaker(
            id=uuid.uuid4(),
            meeting_id=meeting_b.id,
            name="Clinic Manager",
            label="SPEAKER_00",
        )
        session.add(speaker_b)
        await session.flush()

        transcript_b = Transcript(
            id=uuid.uuid4(),
            meeting_id=meeting_b.id,
            workspace_id=ws_1.id,
            status=TranscriptStatus.COMPLETED,
            full_text=MEETING_B_TRANSCRIPT,
            word_count=len(MEETING_B_TRANSCRIPT.split()),
            language="en",
        )
        session.add(transcript_b)
        await session.flush()

        seg_b_data = [
            ("Clinic Planning Meeting.", 0.0, 4.0),
            ("Priya will configure appointment booking by October 22.", 4.0, 11.0),
            ("Daniel will test receptionist availability by October 23.", 11.0, 18.0),
        ]
        for idx, (txt, st, et) in enumerate(seg_b_data):
            session.add(
                TranscriptSegment(
                    id=uuid.uuid4(),
                    transcript_id=transcript_b.id,
                    speaker_id=speaker_b.id,
                    sequence_order=idx,
                    start_time=st,
                    end_time=et,
                    text=txt,
                    confidence=0.99,
                )
            )

        await session.commit()

        token_1 = create_access_token(user_1.id)
        token_2 = create_access_token(user_2.id)

        return {
            "user_1": user_1,
            "ws_1": ws_1,
            "token_1": token_1,
            "meeting_a": meeting_a,
            "transcript_a": transcript_a,
            "meeting_b": meeting_b,
            "transcript_b": transcript_b,
            "user_2": user_2,
            "ws_2": ws_2,
            "token_2": token_2,
        }


# -------------------------------------------------------------------------
# Test 1: Meeting A summary contains marketing-related information only.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_01_meeting_a_summary_contains_marketing_only(isolation_environment):
    env = isolation_environment
    meeting_a = env["meeting_a"]

    res = await _async_process_meeting_intelligence(str(meeting_a.id))
    assert res["status"] == "completed"

    async with AsyncSessionLocal() as session:
        stmt = select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_a.id)
        summary = (await session.execute(stmt)).scalar_one_or_none()
        assert summary is not None

        content = (summary.overview + " " + (summary.detailed_summary or "")).lower()
        # Must contain marketing info
        assert "marketing" in content or "campaign" in content
        # Must NOT contain Meeting B's clinic content
        assert "clinic" not in content
        assert "appointment" not in content
        assert "receptionist" not in content
        assert "priya" not in content


# -------------------------------------------------------------------------
# Test 2: Meeting B summary contains clinic-planning information only.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_02_meeting_b_summary_contains_clinic_only(isolation_environment):
    env = isolation_environment
    meeting_b = env["meeting_b"]

    res = await _async_process_meeting_intelligence(str(meeting_b.id))
    assert res["status"] == "completed"

    async with AsyncSessionLocal() as session:
        stmt = select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_b.id)
        summary = (await session.execute(stmt)).scalar_one_or_none()
        assert summary is not None

        content = (summary.overview + " " + (summary.detailed_summary or "")).lower()
        # Must contain clinic info
        assert "clinic" in content or "appointment" in content
        # Must NOT contain Meeting A's marketing content
        assert "advertising" not in content
        assert "marketing campaign" not in content
        assert "sara" not in content
        assert "arjun" not in content


# -------------------------------------------------------------------------
# Test 3: Meeting A RAG question: "What is Sara responsible for?"
# Expected: Review the advertising design by October 20.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_03_meeting_a_rag_sara_responsible(isolation_environment):
    env = isolation_environment
    user_1 = env["user_1"]
    ws_1 = env["ws_1"]
    meeting_a = env["meeting_a"]
    transcript_a = env["transcript_a"]

    # Index embeddings for Meeting A
    await _async_process_transcript_embeddings(str(transcript_a.id))

    async with AsyncSessionLocal() as session:
        conv = ChatConversation(
            id=uuid.uuid4(),
            workspace_id=ws_1.id,
            user_id=user_1.id,
            meeting_id=meeting_a.id,
            title="Meeting A Chat",
        )
        session.add(conv)
        await session.commit()
        conv_id = conv.id

    async with AsyncSessionLocal() as session:
        rag_res = await RAGService.answer_question(
            session=session,
            workspace_id=ws_1.id,
            user_id=user_1.id,
            conversation_id=conv_id,
            question_text="What is Sara responsible for?",
            meeting_id_filter=meeting_a.id,
        )

        ans = rag_res.answer.lower()
        assert "sara" in ans
        assert "advertising design" in ans
        assert "october 20" in ans
        # Sources must link strictly to Meeting A
        assert len(rag_res.sources) > 0
        for src in rag_res.sources:
            assert src["meeting_id"] == str(meeting_a.id)


# -------------------------------------------------------------------------
# Test 4: Meeting B RAG question: "What is Priya responsible for?"
# Expected: Configure appointment booking by October 22.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_04_meeting_b_rag_priya_responsible(isolation_environment):
    env = isolation_environment
    user_1 = env["user_1"]
    ws_1 = env["ws_1"]
    meeting_b = env["meeting_b"]
    transcript_b = env["transcript_b"]

    # Index embeddings for Meeting B
    await _async_process_transcript_embeddings(str(transcript_b.id))

    async with AsyncSessionLocal() as session:
        conv = ChatConversation(
            id=uuid.uuid4(),
            workspace_id=ws_1.id,
            user_id=user_1.id,
            meeting_id=meeting_b.id,
            title="Meeting B Chat",
        )
        session.add(conv)
        await session.commit()
        conv_id = conv.id

    async with AsyncSessionLocal() as session:
        rag_res = await RAGService.answer_question(
            session=session,
            workspace_id=ws_1.id,
            user_id=user_1.id,
            conversation_id=conv_id,
            question_text="What is Priya responsible for?",
            meeting_id_filter=meeting_b.id,
        )

        ans = rag_res.answer.lower()
        assert "priya" in ans
        assert "appointment booking" in ans
        assert "october 22" in ans
        # Sources must link strictly to Meeting B
        assert len(rag_res.sources) > 0
        for src in rag_res.sources:
            assert src["meeting_id"] == str(meeting_b.id)


# -------------------------------------------------------------------------
# Test 5: Ask Meeting B about Sara's advertising design task.
# Expected: State that the information is not found in Meeting B's transcript.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_05_ask_meeting_b_about_sara_task_returns_not_found(isolation_environment):
    env = isolation_environment
    user_1 = env["user_1"]
    ws_1 = env["ws_1"]
    meeting_b = env["meeting_b"]
    transcript_b = env["transcript_b"]

    await _async_process_transcript_embeddings(str(transcript_b.id))

    async with AsyncSessionLocal() as session:
        conv = ChatConversation(
            id=uuid.uuid4(),
            workspace_id=ws_1.id,
            user_id=user_1.id,
            meeting_id=meeting_b.id,
            title="Meeting B Cross Query",
        )
        session.add(conv)
        await session.commit()
        conv_id = conv.id

    async with AsyncSessionLocal() as session:
        rag_res = await RAGService.answer_question(
            session=session,
            workspace_id=ws_1.id,
            user_id=user_1.id,
            conversation_id=conv_id,
            question_text="What is Sara's advertising design task?",
            meeting_id_filter=meeting_b.id,
        )

        ans = rag_res.answer.lower()
        assert (
            "couldn't find" in ans
            or "could not find" in ans
            or "not found" in ans
            or "not present" in ans
        )
        # Refusal must NOT present fabricated sources
        assert len(rag_res.sources) == 0


# -------------------------------------------------------------------------
# Test 6: Reprocess Meeting B and verify Meeting A's transcript, summary,
# action items, and indexes remain unchanged.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_06_reprocess_meeting_b_preserves_meeting_a(isolation_environment):
    env = isolation_environment
    meeting_a = env["meeting_a"]
    transcript_a = env["transcript_a"]
    meeting_b = env["meeting_b"]
    transcript_b = env["transcript_b"]

    # 1. Process both meetings initially
    await _async_process_meeting_intelligence(str(meeting_a.id))
    await _async_process_transcript_embeddings(str(transcript_a.id))
    await _async_process_meeting_intelligence(str(meeting_b.id))
    await _async_process_transcript_embeddings(str(transcript_b.id))

    # Capture Meeting A snapshot
    async with AsyncSessionLocal() as session:
        sum_a = (await session.execute(select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_a.id))).scalar_one()
        tasks_a = list((await session.execute(select(ActionItem).where(ActionItem.meeting_id == meeting_a.id))).scalars().all())
        embs_a = list((await session.execute(select(TranscriptEmbedding).where(TranscriptEmbedding.meeting_id == meeting_a.id))).scalars().all())

        sum_a_overview = sum_a.overview
        task_a_ids = {t.id for t in tasks_a}
        emb_a_ids = {e.id for e in embs_a}
        assert len(task_a_ids) == 2
        assert len(emb_a_ids) > 0

    # 2. Trigger Reprocessing on Meeting B only
    reproc_res = await _async_process_meeting_intelligence(str(meeting_b.id))
    assert reproc_res["status"] == "completed"
    await _async_process_transcript_embeddings(str(transcript_b.id))

    # 3. Verify Meeting A is 100% unaltered
    async with AsyncSessionLocal() as session:
        sum_a_after = (await session.execute(select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_a.id))).scalar_one()
        tasks_a_after = list((await session.execute(select(ActionItem).where(ActionItem.meeting_id == meeting_a.id))).scalars().all())
        embs_a_after = list((await session.execute(select(TranscriptEmbedding).where(TranscriptEmbedding.meeting_id == meeting_a.id))).scalars().all())

        assert sum_a_after.overview == sum_a_overview
        assert {t.id for t in tasks_a_after} == task_a_ids
        assert {e.id for e in embs_a_after} == emb_a_ids


# -------------------------------------------------------------------------
# Test 7: Upload two meetings in quick succession and verify independent processing.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_07_quick_succession_independent_processing(isolation_environment):
    env = isolation_environment
    meeting_a = env["meeting_a"]
    meeting_b = env["meeting_b"]

    res_a = await _async_process_meeting_intelligence(str(meeting_a.id))
    res_b = await _async_process_meeting_intelligence(str(meeting_b.id))

    assert res_a["status"] == "completed"
    assert res_b["status"] == "completed"

    async with AsyncSessionLocal() as session:
        tasks_a = list((await session.execute(select(ActionItem).where(ActionItem.meeting_id == meeting_a.id))).scalars().all())
        tasks_b = list((await session.execute(select(ActionItem).where(ActionItem.meeting_id == meeting_b.id))).scalars().all())

        a_assignees = {t.assignee_name for t in tasks_a}
        b_assignees = {t.assignee_name for t in tasks_b}

        assert a_assignees == {"Arjun", "Sara"}
        assert b_assignees == {"Priya", "Daniel"}


# -------------------------------------------------------------------------
# Test 8: Run concurrent processing jobs and verify that results are stored
# under the correct meeting IDs.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_08_concurrent_processing_maintains_meeting_boundary(isolation_environment):
    env = isolation_environment
    meeting_a = env["meeting_a"]
    meeting_b = env["meeting_b"]

    # Concurrently execute both intelligence pipelines
    res_a, res_b = await asyncio.gather(
        _async_process_meeting_intelligence(str(meeting_a.id)),
        _async_process_meeting_intelligence(str(meeting_b.id)),
    )

    assert res_a["status"] == "completed"
    assert res_b["status"] == "completed"

    async with AsyncSessionLocal() as session:
        # Check Meeting A
        stmt_a = select(ActionItem).where(ActionItem.meeting_id == meeting_a.id)
        items_a = list((await session.execute(stmt_a)).scalars().all())
        for it in items_a:
            assert it.meeting_id == meeting_a.id
            assert it.assignee_name in ["Arjun", "Sara"]

        # Check Meeting B
        stmt_b = select(ActionItem).where(ActionItem.meeting_id == meeting_b.id)
        items_b = list((await session.execute(stmt_b)).scalars().all())
        for it in items_b:
            assert it.meeting_id == meeting_b.id
            assert it.assignee_name in ["Priya", "Daniel"]


# -------------------------------------------------------------------------
# Test 9: Verify workspace isolation for every meeting-specific API.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_09_workspace_isolation_for_meeting_apis(client: AsyncClient, isolation_environment):
    env = isolation_environment
    meeting_a = env["meeting_a"]
    token_2 = env["token_2"]  # Belongs to Workspace 2
    headers_user_2 = {"Authorization": f"Bearer {token_2}"}

    # User 2 attempting to access Meeting A (owned by Workspace 1)
    endpoints = [
        f"/api/v1/meetings/{meeting_a.id}",
        f"/api/v1/meetings/{meeting_a.id}/transcript",
        f"/api/v1/meetings/{meeting_a.id}/ai",
        f"/api/v1/meetings/{meeting_a.id}/ai/action-items",
        f"/api/v1/meetings/{meeting_a.id}/recordings",
    ]

    for ep in endpoints:
        resp = await client.get(ep, headers=headers_user_2)
        assert resp.status_code == 404, f"Endpoint {ep} should return 404 for unauthorized workspace, got {resp.status_code}"

    # Chat shortcut should also return 404
    chat_resp = await client.post(
        f"/api/v1/meetings/{meeting_a.id}/chat",
        headers=headers_user_2,
        json={"question": "What is the marketing budget?"},
    )
    assert chat_resp.status_code == 404


# -------------------------------------------------------------------------
# Test 10: Verify that switching between meetings does not return stale data.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_10_switching_meetings_returns_isolated_data(client: AsyncClient, isolation_environment):
    env = isolation_environment
    meeting_a = env["meeting_a"]
    meeting_b = env["meeting_b"]
    token_1 = env["token_1"]
    headers = {"Authorization": f"Bearer {token_1}"}

    # 1. Fetch Meeting A
    resp_a = await client.get(f"/api/v1/meetings/{meeting_a.id}", headers=headers)
    assert resp_a.status_code == 200
    assert resp_a.json()["id"] == str(meeting_a.id)
    assert resp_a.json()["title"] == "Marketing Planning"

    # 2. Fetch Meeting B immediately
    resp_b = await client.get(f"/api/v1/meetings/{meeting_b.id}", headers=headers)
    assert resp_b.status_code == 200
    assert resp_b.json()["id"] == str(meeting_b.id)
    assert resp_b.json()["title"] == "Clinic Appointment Planning"


# -------------------------------------------------------------------------
# Test 11: Verify that workspace-level task aggregation includes the correct
# tasks and source meeting IDs.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_11_workspace_task_aggregation_retains_source_meeting(client: AsyncClient, isolation_environment):
    env = isolation_environment
    ws_1 = env["ws_1"]
    meeting_a = env["meeting_a"]
    meeting_b = env["meeting_b"]
    token_1 = env["token_1"]
    headers = {"Authorization": f"Bearer {token_1}"}

    await _async_process_meeting_intelligence(str(meeting_a.id))
    await _async_process_meeting_intelligence(str(meeting_b.id))

    # Aggregate all workspace tasks
    resp = await client.get(f"/api/v1/action-items?workspace_id={ws_1.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 4
    items = data["items"]

    # Verify tasks retain their correct source meeting IDs
    for item in items:
        if item["assignee_name"] in ["Arjun", "Sara"]:
            assert item["meeting_id"] == str(meeting_a.id)
            assert item["meeting_title"] == "Marketing Planning"
        elif item["assignee_name"] in ["Priya", "Daniel"]:
            assert item["meeting_id"] == str(meeting_b.id)
            assert item["meeting_title"] == "Clinic Appointment Planning"

    # Verify filtering by meeting_id returns only that meeting's tasks
    resp_filter_a = await client.get(f"/api/v1/action-items?workspace_id={ws_1.id}&meeting_id={meeting_a.id}", headers=headers)
    assert resp_filter_a.status_code == 200
    items_filter_a = resp_filter_a.json()["items"]
    assert len(items_filter_a) == 2
    assert all(it["meeting_id"] == str(meeting_a.id) for it in items_filter_a)


# -------------------------------------------------------------------------
# Test 12: Verify that repeated processing requests do not create duplicate tasks.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_repeated_processing_does_not_duplicate_tasks(isolation_environment):
    env = isolation_environment
    meeting_a = env["meeting_a"]

    # Trigger processing 3 times consecutively
    await _async_process_meeting_intelligence(str(meeting_a.id))
    await _async_process_meeting_intelligence(str(meeting_a.id))
    await _async_process_meeting_intelligence(str(meeting_a.id))

    async with AsyncSessionLocal() as session:
        stmt = select(ActionItem).where(ActionItem.meeting_id == meeting_a.id)
        items = list((await session.execute(stmt)).scalars().all())

        # Must still be exactly 2 tasks
        assert len(items) == 2
        assignees = [it.assignee_name for it in items]
        assert "Arjun" in assignees
        assert "Sara" in assignees


# -------------------------------------------------------------------------
# Test 13: Verify that failed processing cannot overwrite previously valid
# results from another meeting.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_failed_processing_does_not_corrupt_other_meetings(isolation_environment):
    env = isolation_environment
    ws_1 = env["ws_1"]
    user_1 = env["user_1"]
    meeting_a = env["meeting_a"]

    # 1. Ensure Meeting A has valid intelligence
    await _async_process_meeting_intelligence(str(meeting_a.id))

    # 2. Create Meeting C with empty transcript to trigger failure
    async with AsyncSessionLocal() as session:
        meeting_c = Meeting(
            id=uuid.uuid4(),
            workspace_id=ws_1.id,
            creator_id=user_1.id,
            title="Empty Corrupted Meeting",
            status=MeetingStatus.COMPLETED,
            platform=MeetingPlatform.UPLOAD,
        )
        session.add(meeting_c)
        await session.flush()

        transcript_c = Transcript(
            id=uuid.uuid4(),
            meeting_id=meeting_c.id,
            workspace_id=ws_1.id,
            status=TranscriptStatus.FAILED,
            full_text=None,
        )
        session.add(transcript_c)
        await session.commit()
        meeting_c_id = meeting_c.id

    # 3. Run processing on Meeting C -> should fail cleanly
    res_c = await _async_process_meeting_intelligence(str(meeting_c_id))
    assert res_c["status"] == "failed"

    # 4. Verify Meeting A's intelligence is completely untouched
    async with AsyncSessionLocal() as session:
        tasks_a = list((await session.execute(select(ActionItem).where(ActionItem.meeting_id == meeting_a.id))).scalars().all())
        assert len(tasks_a) == 2


# -------------------------------------------------------------------------
# Test 14: Verify that stale background jobs cannot overwrite newer processing
# results for the same meeting.
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_14_stale_background_jobs_cannot_overwrite_newer_results(isolation_environment):
    env = isolation_environment
    meeting_a = env["meeting_a"]
    ws_1 = env["ws_1"]

    # Create Job v1
    async with AsyncSessionLocal() as session:
        job_v1 = MeetingIntelligenceJob(
            id=uuid.uuid4(),
            meeting_id=meeting_a.id,
            workspace_id=ws_1.id,
            status=IntelligenceStatus.PROCESSING,
            version=1,
        )
        session.add(job_v1)
        await session.commit()
        job_v1_id = job_v1.id

    # Create and complete Job v2 (a newer job completed first)
    async with AsyncSessionLocal() as session:
        job_v2 = MeetingIntelligenceJob(
            id=uuid.uuid4(),
            meeting_id=meeting_a.id,
            workspace_id=ws_1.id,
            status=IntelligenceStatus.COMPLETED,
            version=2,
        )
        session.add(job_v2)
        summary_v2 = MeetingSummary(
            id=uuid.uuid4(),
            meeting_id=meeting_a.id,
            workspace_id=ws_1.id,
            overview="NEWER VERSION 2 SUMMARY CONTENT",
            version=2,
            job_id=job_v2.id,
        )
        session.add(summary_v2)
        await session.commit()

    # Now simulate Job v1 (stale worker) running
    stale_res = await _async_process_meeting_intelligence(str(meeting_a.id), job_id_str=str(job_v1_id))
    assert stale_res["status"] == "superseded"
    assert stale_res["superseded_by"] == 2

    # Verify that version 2 summary was NOT overwritten or purged
    async with AsyncSessionLocal() as session:
        latest_summary = (
            await session.execute(select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_a.id))
        ).scalar_one()
        assert latest_summary.overview == "NEWER VERSION 2 SUMMARY CONTENT"
        assert latest_summary.version == 2
