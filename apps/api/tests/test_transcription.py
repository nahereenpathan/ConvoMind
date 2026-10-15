"""Comprehensive automated tests for Transcription & Audio Processing Pipeline."""

import io
import os
import struct
import tempfile
import uuid
from typing import Dict, Tuple
from unittest.mock import MagicMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.enums import RecordingStatus, TranscriptStatus, WorkspaceRole
from app.models.recording import MeetingRecording
from app.models.transcript import Transcript, TranscriptSegment
from app.services.ffmpeg_service import get_ffmpeg_service
from app.services.storage_service import get_storage_service
from app.services.transcription import (
    MockTranscriptionProvider,
    TranscriptionPermanentError,
    TranscriptionTransientError,
    WhisperProvider,
    get_transcription_provider,
)
from app.workers.tasks.recording_tasks import (
    _async_process_recording,
    process_meeting_recording,
)


def make_valid_pcm_wav(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate authentic, valid PCM WAV audio byte sequence."""
    num_samples = int(duration_s * sample_rate)
    byte_rate = sample_rate * 2
    block_align = 2
    data_size = num_samples * 2
    chunk_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        1,  # Mono
        sample_rate,
        byte_rate,
        block_align,
        16,  # 16-bit
        b"data",
        data_size,
    )
    samples = b"\x00" * data_size
    return header + samples


VALID_TEST_WAV = make_valid_pcm_wav(duration_s=2.0)


async def create_user_and_token(
    client: AsyncClient, name: str = "Transcription User"
) -> Tuple[Dict, str]:
    """Register and login a test user."""
    email = f"trans_{uuid.uuid4().hex[:8]}@convomind.ai"
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
    return {"Authorization": f"Bearer {token}"}


async def setup_transcription_fixture(client: AsyncClient) -> Dict:
    """Setup workspace, members, meeting, and uploaded recording."""
    owner, t_owner = await create_user_and_token(client, "Owner")
    admin, t_admin = await create_user_and_token(client, "Admin")
    member, t_member = await create_user_and_token(client, "Member")
    guest, t_guest = await create_user_and_token(client, "Guest")
    stranger, t_stranger = await create_user_and_token(client, "Stranger")

    # 1. Create workspace
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": f"Transcription WS {uuid.uuid4().hex[:6]}"},
        headers=auth_header(t_owner),
    )
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    # 2. Add members
    for user_obj, token_role, role_val in [
        (admin, t_admin, WorkspaceRole.ADMIN.value),
        (member, t_member, WorkspaceRole.MEMBER.value),
        (guest, t_guest, WorkspaceRole.GUEST.value),
    ]:
        add_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"email": user_obj["email"], "role": role_val},
            headers=auth_header(t_owner),
        )
        assert add_res.status_code == 201

    # 3. Create meeting
    m_res = await client.post(
        "/api/v1/meetings",
        json={"workspace_id": ws_id, "title": "Pipeline Architecture Sync"},
        headers=auth_header(t_owner),
    )
    assert m_res.status_code == 201
    meeting = m_res.json()

    # 4. Upload recording with valid WAV
    files = {"file": ("sync_meeting.wav", io.BytesIO(VALID_TEST_WAV), "audio/wav")}
    with patch("app.workers.tasks.recording_tasks.process_meeting_recording.delay"):
        rec_res = await client.post(
            f"/api/v1/meetings/{meeting['id']}/recordings",
            files=files,
            headers=auth_header(t_owner),
        )
    assert rec_res.status_code == 201
    recording = rec_res.json()

    return {
        "workspace_id": ws_id,
        "meeting_id": meeting["id"],
        "recording_id": recording["id"],
        "recording": recording,
        "meeting": meeting,
        "owner": (owner, t_owner),
        "admin": (admin, t_admin),
        "member": (member, t_member),
        "guest": (guest, t_guest),
        "stranger": (stranger, t_stranger),
    }


# ============================================================================
# 1. FFmpeg Audio Extraction & Audio Processing Tests
# ============================================================================


def test_ffmpeg_extract_audio_for_stt_success():
    """Verify FFmpeg normalizes real audio into 16kHz mono WAV."""
    ffmpeg = get_ffmpeg_service()
    if not ffmpeg.is_available():
        pytest.skip("FFmpeg not available in environment.")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as in_file:
        in_file.write(VALID_TEST_WAV)
        in_path = in_file.name

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out_file:
        out_path = out_file.name

    try:
        success = ffmpeg.extract_audio_for_stt(in_path, out_path, sample_rate=16000, channels=1)
        assert success is True
        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0

        # Probe the converted media
        probe = ffmpeg.probe_media(out_path)
        assert probe["channels"] == 1
        assert probe["sample_rate"] == 16000
    finally:
        for p in (in_path, out_path):
            if os.path.exists(p):
                os.remove(p)


def test_ffmpeg_corrupt_media_fails_safely():
    """Verify FFmpeg handles corrupt media files gracefully without unhandled crashes."""
    ffmpeg = get_ffmpeg_service()
    if not ffmpeg.is_available():
        pytest.skip("FFmpeg not available in environment.")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as corrupt_file:
        corrupt_file.write(b"NOT_A_VALID_MEDIA_FILE_CORRUPT_BYTES_DATA")
        corrupt_path = corrupt_file.name

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out_file:
        out_path = out_file.name

    try:
        success = ffmpeg.extract_audio_for_stt(corrupt_path, out_path)
        assert success is False
    finally:
        for p in (corrupt_path, out_path):
            if os.path.exists(p):
                os.remove(p)


def test_ffmpeg_path_traversal_rejected():
    """Verify FFmpeg service guards against path traversal attempts."""
    ffmpeg = get_ffmpeg_service()
    success = ffmpeg.extract_audio_for_stt("../etc/passwd", "/tmp/out.wav")
    assert success is False


# ============================================================================
# 2. Transcription Provider Abstraction Tests
# ============================================================================


@pytest.mark.asyncio
async def test_transcription_provider_abstraction():
    """Verify MockTranscriptionProvider returns structured text and timestamped segments."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(VALID_TEST_WAV)
        tmp_path = tmp.name

    try:
        provider = MockTranscriptionProvider()
        result = await provider.transcribe(tmp_path)

        assert result.provider == "mock"
        assert result.full_text is not None and len(result.full_text) > 0
        assert len(result.segments) > 0
        assert result.duration is not None and result.duration > 0
        assert result.word_count > 0

        # Verify segment timestamps and ordering
        prev_end = 0.0
        for seg in result.segments:
            assert seg.start_time >= prev_end
            assert seg.end_time > seg.start_time
            assert len(seg.text) > 0
            prev_end = seg.end_time
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.asyncio
async def test_whisper_provider_missing_key_fails_permanently():
    """Verify WhisperProvider raises TranscriptionPermanentError if API key is unset."""
    provider = WhisperProvider(api_key=None)
    with pytest.raises(TranscriptionPermanentError) as exc_info:
        await provider.transcribe("/dummy/path.wav")
    assert "api key is not configured" in str(exc_info.value).lower()


# ============================================================================
# 3. Celery Pipeline End-to-End, Persistence & Idempotency Tests
# ============================================================================


@pytest.mark.asyncio
async def test_transcription_celery_task_end_to_end(client: AsyncClient):
    """Test full asynchronous pipeline: probe -> extract -> transcribe -> persist."""
    fixture = await setup_transcription_fixture(client)
    recording_id = fixture["recording_id"]
    meeting_id = fixture["meeting_id"]

    # Execute async pipeline task
    result = await _async_process_recording(recording_id)
    assert result["status"] == "completed"
    assert result["recording_id"] == recording_id
    assert "transcript_id" in result
    assert result["segments_count"] > 0

    # Verify database state for MeetingRecording and Transcript
    async with AsyncSessionLocal() as session:
        rec = (
            await session.execute(
                select(MeetingRecording).where(MeetingRecording.id == uuid.UUID(recording_id))
            )
        ).scalar_one()
        assert rec.status == RecordingStatus.COMPLETED
        assert rec.error_message is None

        tr = (
            await session.execute(
                select(Transcript).where(Transcript.recording_id == uuid.UUID(recording_id))
            )
        ).scalar_one()
        assert tr.status == TranscriptStatus.COMPLETED
        assert tr.full_text is not None
        assert tr.word_count > 0
        assert tr.provider == "mock"
        assert tr.meeting_id == uuid.UUID(meeting_id)

        # Verify persisted segments
        segs = list(
            (
                await session.execute(
                    select(TranscriptSegment)
                    .where(TranscriptSegment.transcript_id == tr.id)
                    .order_by(TranscriptSegment.sequence_order.asc())
                )
            ).scalars().all()
        )
        assert len(segs) == result["segments_count"]
        for idx, s in enumerate(segs):
            assert s.sequence_order == idx
            assert s.start_time <= s.end_time
            assert s.text is not None


@pytest.mark.asyncio
async def test_transcription_idempotency(client: AsyncClient):
    """Verify executing transcription task multiple times does NOT duplicate transcripts or segments."""
    fixture = await setup_transcription_fixture(client)
    recording_id = fixture["recording_id"]

    # First execution
    res1 = await _async_process_recording(recording_id)
    assert res1["status"] == "completed"

    # Second execution (idempotency check)
    res2 = await _async_process_recording(recording_id)
    assert res2["status"] == "already_completed"

    # Check that database contains exactly 1 transcript and correct segment count
    async with AsyncSessionLocal() as session:
        transcripts = list(
            (
                await session.execute(
                    select(Transcript).where(Transcript.recording_id == uuid.UUID(recording_id))
                )
            ).scalars().all()
        )
        assert len(transcripts) == 1

        segments = list(
            (
                await session.execute(
                    select(TranscriptSegment).where(TranscriptSegment.transcript_id == transcripts[0].id)
                )
            ).scalars().all()
        )
        assert len(segments) == res1["segments_count"]


@pytest.mark.asyncio
async def test_permanent_failure_handling(client: AsyncClient):
    """Verify permanent failure transitions status to FAILED without endless retry."""
    fixture = await setup_transcription_fixture(client)
    recording_id = fixture["recording_id"]

    # Simulate permanent error in provider
    mock_provider = MockTranscriptionProvider(simulate_permanent_error=True)
    with patch("app.workers.tasks.recording_tasks.get_transcription_provider", return_value=mock_provider):
        with pytest.raises(TranscriptionPermanentError):
            await _async_process_recording(recording_id)

    # Check status is FAILED in database
    async with AsyncSessionLocal() as session:
        rec = (
            await session.execute(
                select(MeetingRecording).where(MeetingRecording.id == uuid.UUID(recording_id))
            )
        ).scalar_one()
        assert rec.status == RecordingStatus.FAILED
        assert "simulated permanent" in rec.error_message.lower()

        tr = (
            await session.execute(
                select(Transcript).where(Transcript.recording_id == uuid.UUID(recording_id))
            )
        ).scalar_one()
        assert tr.status == TranscriptStatus.FAILED
        assert "simulated permanent" in tr.error_message.lower()


def test_transient_failure_triggers_retry():
    """Verify Celery task catches TranscriptionTransientError and triggers retry."""
    dummy_id = "00000000-0000-0000-0000-000000000000"

    with patch(
        "app.workers.tasks.recording_tasks.asyncio.run",
        side_effect=TranscriptionTransientError("Simulated 429", provider="mock"),
    ), patch.object(
        process_meeting_recording, "retry", side_effect=Exception("TaskRetried")
    ) as mock_retry:
        with pytest.raises(Exception) as exc_info:
            process_meeting_recording(dummy_id)
        assert "TaskRetried" in str(exc_info.value)
        assert mock_retry.called


@pytest.mark.asyncio
async def test_missing_recording_handled_safely():
    """Verify passing non-existent recording UUID exits safely with not_found."""
    missing_id = str(uuid.uuid4())
    res = await _async_process_recording(missing_id)
    assert res["status"] == "not_found"


# ============================================================================
# 4. API Endpoints, Workspace Isolation & Security Tests
# ============================================================================


@pytest.mark.asyncio
async def test_trigger_transcription_api(client: AsyncClient):
    """POST /meetings/{meeting_id}/recordings/{recording_id}/transcribe queues Celery task."""
    fixture = await setup_transcription_fixture(client)
    _, t_owner = fixture["owner"]
    meeting_id = fixture["meeting_id"]
    recording_id = fixture["recording_id"]

    with patch("app.workers.tasks.recording_tasks.process_meeting_recording.delay") as mock_delay:
        res = await client.post(
            f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}/transcribe",
            headers=auth_header(t_owner),
        )
        assert res.status_code == 202
        data = res.json()
        assert data["status"] == "QUEUED"
        assert data["recording_id"] == recording_id
        assert data["meeting_id"] == meeting_id
        assert mock_delay.called


@pytest.mark.asyncio
async def test_get_meeting_transcript_and_status_api(client: AsyncClient):
    """GET /meetings/{meeting_id}/transcript and /status return complete transcript with segments."""
    fixture = await setup_transcription_fixture(client)
    _, t_owner = fixture["owner"]
    meeting_id = fixture["meeting_id"]
    recording_id = fixture["recording_id"]

    # Process recording first
    await _async_process_recording(recording_id)

    # 1. Test /meetings/{meeting_id}/transcript
    t_res = await client.get(
        f"/api/v1/meetings/{meeting_id}/transcript",
        headers=auth_header(t_owner),
    )
    assert t_res.status_code == 200
    t_data = t_res.json()
    assert t_data["meeting_id"] == meeting_id
    assert t_data["recording_id"] == recording_id
    assert t_data["status"] == "COMPLETED"
    assert t_data["full_text"] is not None
    assert len(t_data["segments"]) > 0
    assert t_data["total_segments"] > 0

    # 2. Test pagination
    t_pag = await client.get(
        f"/api/v1/meetings/{meeting_id}/transcript?page=1&page_size=2",
        headers=auth_header(t_owner),
    )
    assert t_pag.status_code == 200
    assert len(t_pag.json()["segments"]) == 2
    assert t_pag.json()["page"] == 1
    assert t_pag.json()["page_size"] == 2

    # 3. Test /meetings/{meeting_id}/transcript/status
    s_res = await client.get(
        f"/api/v1/meetings/{meeting_id}/transcript/status",
        headers=auth_header(t_owner),
    )
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert s_data["status"] == "COMPLETED"
    assert s_data["meeting_id"] == meeting_id

    # 4. Test /meetings/{meeting_id}/recordings/{recording_id}/transcription
    rec_t_res = await client.get(
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}/transcription",
        headers=auth_header(t_owner),
    )
    assert rec_t_res.status_code == 200
    assert rec_t_res.json()["recording_id"] == recording_id


@pytest.mark.asyncio
async def test_workspace_isolation_and_idor_protection(client: AsyncClient):
    """Verify unauthorized stranger cannot access or trigger another workspace's transcript."""
    fixture = await setup_transcription_fixture(client)
    _, t_stranger = fixture["stranger"]
    meeting_id = fixture["meeting_id"]
    recording_id = fixture["recording_id"]

    # Process recording
    await _async_process_recording(recording_id)

    # 1. Stranger tries to get transcript -> 404
    res1 = await client.get(
        f"/api/v1/meetings/{meeting_id}/transcript",
        headers=auth_header(t_stranger),
    )
    assert res1.status_code == 404

    # 2. Stranger tries to trigger transcription -> 404
    res2 = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}/transcribe",
        headers=auth_header(t_stranger),
    )
    assert res2.status_code == 404

    # 3. Stranger tries to get status -> 404
    res3 = await client.get(
        f"/api/v1/meetings/{meeting_id}/transcript/status",
        headers=auth_header(t_stranger),
    )
    assert res3.status_code == 404


@pytest.mark.asyncio
async def test_guest_cannot_trigger_transcription(client: AsyncClient):
    """Verify workspace Guest is forbidden from triggering transcription (403 Forbidden)."""
    fixture = await setup_transcription_fixture(client)
    _, t_guest = fixture["guest"]
    meeting_id = fixture["meeting_id"]
    recording_id = fixture["recording_id"]

    res = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}/transcribe",
        headers=auth_header(t_guest),
    )
    assert res.status_code == 403
    assert "guest" in res.json()["detail"].lower()
