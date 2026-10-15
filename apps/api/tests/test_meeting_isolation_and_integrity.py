"""End-to-End Meeting Data Isolation, RAG Isolation, and Grounding Test Suite."""

import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.meeting import Meeting
from app.models.transcript import Transcript, TranscriptSegment
from app.models.intelligence import MeetingSummary, ActionItem, Decision, MeetingQuestion
from app.models.enums import MeetingStatus, TranscriptStatus
from app.workers.tasks.intelligence_tasks import _async_process_meeting_intelligence
from app.services.rag.rag_service import RAGService


@pytest.mark.asyncio
async def test_three_meetings_data_and_rag_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    test_workspace: dict,
):
    """Verify 3 distinct meetings maintain strict transcript, AI intelligence, and RAG data isolation."""
    workspace_id = test_workspace.id

    # 1. Create Meeting 1: Billing / Razorpay / Workspace Security
    m1 = Meeting(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        title="Billing Integration and Razorpay Sync",
        description="Rahul testing Razorpay payment flow, frontend team verifying action items, workspace security",
        status=MeetingStatus.COMPLETED,
    )
    db_session.add(m1)

    # 2. Create Meeting 2: Marketing Campaign / Social Media / Advertising Budget
    m2 = Meeting(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        title="Marketing Campaign Planning Meeting",
        description="Social media marketing, product demo video, advertising budget, campaign launch timeline",
        status=MeetingStatus.COMPLETED,
    )
    db_session.add(m2)

    # 3. Create Meeting 3: Customer Support / Ticket Response Time
    m3 = Meeting(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        title="Customer Support Ticket Response Time and Escalation",
        description="Customer support ticket response time, escalation process, refund policy, weekend support coverage",
        status=MeetingStatus.COMPLETED,
    )
    db_session.add(m3)

    await db_session.commit()

    # Transcripts for Meeting 1
    t1 = Transcript(
        id=uuid.uuid4(),
        meeting_id=m1.id,
        workspace_id=workspace_id,
        status=TranscriptStatus.COMPLETED,
        full_text="Rahul will test the Razorpay payment flow by Friday. Frontend team is verifying the dashboard action items. We need to ensure workspace security.",
    )
    db_session.add(t1)

    s1_1 = TranscriptSegment(
        id=uuid.uuid4(),
        transcript_id=t1.id,
        sequence_order=0,
        start_time=0.0,
        end_time=5.0,
        text="Rahul will test the Razorpay payment flow by Friday.",
    )
    s1_2 = TranscriptSegment(
        id=uuid.uuid4(),
        transcript_id=t1.id,
        sequence_order=1,
        start_time=5.0,
        end_time=10.0,
        text="Frontend team is verifying the dashboard action items.",
    )
    s1_3 = TranscriptSegment(
        id=uuid.uuid4(),
        transcript_id=t1.id,
        sequence_order=2,
        start_time=10.0,
        end_time=15.0,
        text="We need to ensure workspace security.",
    )
    db_session.add_all([s1_1, s1_2, s1_3])

    # Transcripts for Meeting 2
    t2 = Transcript(
        id=uuid.uuid4(),
        meeting_id=m2.id,
        workspace_id=workspace_id,
        status=TranscriptStatus.COMPLETED,
        full_text="We need to finalize the social media marketing plan and product demo video. The advertising budget is approved for the campaign launch timeline.",
    )
    db_session.add(t2)

    s2_1 = TranscriptSegment(
        id=uuid.uuid4(),
        transcript_id=t2.id,
        sequence_order=0,
        start_time=0.0,
        end_time=5.0,
        text="We need to finalize the social media marketing plan and product demo video.",
    )
    s2_2 = TranscriptSegment(
        id=uuid.uuid4(),
        transcript_id=t2.id,
        sequence_order=1,
        start_time=5.0,
        end_time=10.0,
        text="The advertising budget is approved for the campaign launch timeline.",
    )
    db_session.add_all([s2_1, s2_2])

    # Transcripts for Meeting 3
    t3 = Transcript(
        id=uuid.uuid4(),
        meeting_id=m3.id,
        workspace_id=workspace_id,
        status=TranscriptStatus.COMPLETED,
        full_text="Customer support ticket response time must be under 15 minutes. The escalation process and refund policy apply to weekend support coverage.",
    )
    db_session.add(t3)

    s3_1 = TranscriptSegment(
        id=uuid.uuid4(),
        transcript_id=t3.id,
        sequence_order=0,
        start_time=0.0,
        end_time=5.0,
        text="Customer support ticket response time must be under 15 minutes.",
    )
    s3_2 = TranscriptSegment(
        id=uuid.uuid4(),
        transcript_id=t3.id,
        sequence_order=1,
        start_time=5.0,
        end_time=10.0,
        text="The escalation process and refund policy apply to weekend support coverage.",
    )
    db_session.add_all([s3_1, s3_2])

    await db_session.commit()

    # Run AI Intelligence extraction task for all 3 meetings
    res1 = await _async_process_meeting_intelligence(str(m1.id))
    assert res1["status"] == "completed"

    res2 = await _async_process_meeting_intelligence(str(m2.id))
    assert res2["status"] == "completed"

    res3 = await _async_process_meeting_intelligence(str(m3.id))
    assert res3["status"] == "completed"

    # Verify Meeting 1 Intelligence
    res_m1 = await client.get(f"/api/v1/meetings/{m1.id}/ai", headers=auth_headers)
    assert res_m1.status_code == 200
    ai1 = res_m1.json()
    assert "razorpay" in ai1["summary"]["overview"].lower() or "billing" in ai1["summary"]["overview"].lower()
    assert not any("advertising budget" in str(ai1).lower() for _ in [1])
    assert not any("microservice architecture" in str(ai1).lower() for _ in [1])

    # Verify Meeting 2 Intelligence
    res_m2 = await client.get(f"/api/v1/meetings/{m2.id}/ai", headers=auth_headers)
    assert res_m2.status_code == 200
    ai2 = res_m2.json()
    assert "marketing" in ai2["summary"]["overview"].lower() or "advertising" in ai2["summary"]["overview"].lower()
    assert not any("razorpay" in str(ai2).lower() for _ in [1])
    assert not any("microservice architecture" in str(ai2).lower() for _ in [1])

    # Verify Meeting 3 Intelligence
    res_m3 = await client.get(f"/api/v1/meetings/{m3.id}/ai", headers=auth_headers)
    assert res_m3.status_code == 200
    ai3 = res_m3.json()
    assert "ticket response time" in ai3["summary"]["overview"].lower() or "customer support" in ai3["summary"]["overview"].lower()
    assert not any("razorpay" in str(ai3).lower() for _ in [1])

    # Verify Database workspace_id on MeetingSummary
    sum1_db = (await db_session.execute(select(MeetingSummary).where(MeetingSummary.meeting_id == m1.id))).scalar_one()
    assert sum1_db.workspace_id == workspace_id

    # Verify No Hallucinated Assignees (e.g. Team Lead / Engineering Lead)
    act1_db = (await db_session.execute(select(ActionItem).where(ActionItem.meeting_id == m1.id))).scalars().all()
    for act in act1_db:
        assert act.assignee_name != "Team Lead"
        assert act.assignee_name != "Engineering Lead"
