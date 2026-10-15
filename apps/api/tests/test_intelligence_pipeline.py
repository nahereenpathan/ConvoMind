import pytest
import uuid
from app.models.enums import IntelligenceStatus, RecordingStatus, TranscriptStatus, WorkspaceRole
from app.services.intelligence_service import IntelligenceService
from fastapi import HTTPException

@pytest.mark.asyncio
async def test_trigger_intelligence_no_recording(db_session, test_user, test_workspace):
    """Scenario 2: Missing recording -> safe HTTP 400 response asking to upload recording."""
    m_id = uuid.uuid4()

    from app.models.meeting import Meeting

    meeting = Meeting(id=m_id, workspace_id=test_workspace.id, creator_id=test_user.id, title="Test No Recording")
    db_session.add(meeting)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await IntelligenceService.trigger_intelligence_processing(
            db=db_session,
            meeting_id=m_id,
            current_user=test_user,
        )
    assert exc_info.value.status_code == 400
    assert "Upload a recording before generating AI intelligence." in exc_info.value.detail

@pytest.mark.asyncio
async def test_trigger_intelligence_transcript_still_processing(db_session, test_user, test_workspace):
    """Scenario 4: Transcript still processing -> safe response asking to wait."""
    m_id = uuid.uuid4()

    from app.models.meeting import Meeting
    from app.models.recording import MeetingRecording
    from app.models.transcript import Transcript

    rec_id = uuid.uuid4()
    meeting = Meeting(id=m_id, workspace_id=test_workspace.id, creator_id=test_user.id, title="Test Processing Transcript")
    rec = MeetingRecording(id=rec_id, meeting_id=m_id, workspace_id=test_workspace.id, uploaded_by_id=test_user.id, original_filename="test.mp3", storage_key=f"key_{uuid.uuid4().hex}", file_size=100, mime_type="audio/mp3", status=RecordingStatus.PROCESSING)
    trans = Transcript(id=uuid.uuid4(), meeting_id=m_id, workspace_id=test_workspace.id, recording_id=rec_id, status=TranscriptStatus.PROCESSING)

    db_session.add_all([meeting, rec, trans])
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await IntelligenceService.trigger_intelligence_processing(
            db=db_session,
            meeting_id=m_id,
            current_user=test_user,
        )
    assert exc_info.value.status_code == 400
    assert "Please wait for transcription to complete" in exc_info.value.detail

@pytest.mark.asyncio
async def test_trigger_intelligence_empty_speech(db_session, test_user, test_workspace):
    """Scenario 3: Empty transcript text -> safe response."""
    m_id = uuid.uuid4()

    from app.models.meeting import Meeting
    from app.models.recording import MeetingRecording
    from app.models.transcript import Transcript

    rec_id = uuid.uuid4()
    meeting = Meeting(id=m_id, workspace_id=test_workspace.id, creator_id=test_user.id, title="Test Empty Speech")
    rec = MeetingRecording(id=rec_id, meeting_id=m_id, workspace_id=test_workspace.id, uploaded_by_id=test_user.id, original_filename="test.mp3", storage_key=f"key_{uuid.uuid4().hex}", file_size=100, mime_type="audio/mp3", status=RecordingStatus.COMPLETED)
    trans = Transcript(id=uuid.uuid4(), meeting_id=m_id, workspace_id=test_workspace.id, recording_id=rec_id, status=TranscriptStatus.COMPLETED, full_text="   ")

    db_session.add_all([meeting, rec, trans])
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await IntelligenceService.trigger_intelligence_processing(
            db=db_session,
            meeting_id=m_id,
            current_user=test_user,
        )
    assert exc_info.value.status_code == 400
    assert "No usable speech was detected in this recording." in exc_info.value.detail

@pytest.mark.asyncio
async def test_trigger_intelligence_guest_unauthorized(db_session, test_user, test_workspace):
    """Scenario 13: Guest user cannot trigger AI processing -> 403 Forbidden."""
    m_id = uuid.uuid4()

    from app.models.user import User
    from app.models.meeting import Meeting
    from app.models.workspace import WorkspaceMember
    from app.core.security import hash_password

    guest_user = User(
        id=uuid.uuid4(),
        email=f"guest_{uuid.uuid4().hex[:6]}@convomind.ai",
        full_name="Guest User",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    db_session.add(guest_user)
    await db_session.commit()

    guest_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=test_workspace.id, user_id=guest_user.id, role=WorkspaceRole.GUEST)
    meeting = Meeting(id=m_id, workspace_id=test_workspace.id, creator_id=test_user.id, title="Guest Test")

    db_session.add_all([guest_member, meeting])
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await IntelligenceService.trigger_intelligence_processing(
            db=db_session,
            meeting_id=m_id,
            current_user=guest_user,
        )
    assert exc_info.value.status_code == 403
