"""Unit tests for SQLAlchemy models instantiation and defaults."""

import uuid
from app.models import (
    ActionItem,
    ActionItemStatus,
    Decision,
    Meeting,
    MeetingParticipant,
    MeetingPlatform,
    MeetingQuestion,
    MeetingStatus,
    MeetingSummary,
    PriorityLevel,
    Speaker,
    Transcript,
    TranscriptSegment,
    TranscriptStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)


def test_user_instantiation():
    user = User(
        email="test@convomind.ai",
        full_name="Jane Doe",
        is_active=True,
        is_superuser=False,
    )
    assert user.email == "test@convomind.ai"
    assert user.full_name == "Jane Doe"
    assert user.is_active is True
    assert user.is_superuser is False
    assert "test@convomind.ai" in repr(user)


def test_workspace_and_membership():
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(
        id=ws_id,
        name="Acme Corp",
        slug="acme-corp",
        description="A test workspace",
    )
    member = WorkspaceMember(
        workspace_id=ws_id,
        user_id=user_id,
        role=WorkspaceRole.OWNER,
    )
    assert ws.slug == "acme-corp"
    assert ws.description == "A test workspace"
    assert member.role == WorkspaceRole.OWNER
    assert str(ws_id) in repr(ws)
    assert repr(member).startswith("<WorkspaceMember")


def test_meeting_and_participants():
    ws_id = uuid.uuid4()
    meeting = Meeting(
        workspace_id=ws_id,
        title="Weekly Sync",
        status=MeetingStatus.SCHEDULED,
        platform=MeetingPlatform.ZOOM,
    )
    participant = MeetingParticipant(
        meeting_id=meeting.id or uuid.uuid4(),
        name="Alice",
        email="alice@example.com",
    )
    speaker = Speaker(
        meeting_id=meeting.id or uuid.uuid4(),
        label="Speaker 1",
        name="Alice",
    )
    assert meeting.title == "Weekly Sync"
    assert meeting.status == MeetingStatus.SCHEDULED
    assert meeting.platform == MeetingPlatform.ZOOM
    assert participant.name == "Alice"
    assert speaker.label == "Speaker 1"


def test_transcript_and_segment():
    meeting_id = uuid.uuid4()
    transcript = Transcript(
        meeting_id=meeting_id,
        status=TranscriptStatus.COMPLETED,
        full_text="Hello world",
        word_count=2,
    )
    segment = TranscriptSegment(
        transcript_id=transcript.id or uuid.uuid4(),
        sequence_order=1,
        start_time=0.0,
        end_time=1.5,
        text="Hello world",
    )
    assert transcript.status == TranscriptStatus.COMPLETED
    assert transcript.word_count == 2
    assert segment.sequence_order == 1
    assert segment.text == "Hello world"


def test_meeting_intelligence_entities():
    meeting_id = uuid.uuid4()
    summary = MeetingSummary(
        meeting_id=meeting_id,
        overview="Product sync overview",
        key_points=[{"point": "Key milestone reached"}],
    )
    action_item = ActionItem(
        meeting_id=meeting_id,
        title="Prepare release notes",
        status=ActionItemStatus.OPEN,
        priority=PriorityLevel.HIGH,
    )
    decision = Decision(
        meeting_id=meeting_id,
        title="Approved Q3 roadmap",
    )
    question = MeetingQuestion(
        meeting_id=meeting_id,
        question="When is code freeze?",
        answer="Next Friday",
        is_resolved=True,
    )

    assert summary.overview == "Product sync overview"
    assert action_item.status == ActionItemStatus.OPEN
    assert action_item.priority == PriorityLevel.HIGH
    assert decision.title == "Approved Q3 roadmap"
    assert question.is_resolved is True
