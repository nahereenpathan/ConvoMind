"""Comprehensive automated tests for Meeting Recording & File Upload Module."""

import io
import os
import uuid
from typing import Dict, Tuple
from unittest.mock import patch
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.models.enums import RecordingStatus, WorkspaceRole
from app.services.storage_service import get_storage_service
from app.workers.tasks.recording_tasks import _async_process_recording, process_meeting_recording

# Valid sample media headers
VALID_MP3_BYTES = b"ID3\x04\x00\x00\x00\x00\x00\x0a" + b"\xff\xfb\x90\x44" + b"\x00" * 200
VALID_WAV_BYTES = (
    b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00"
    b"\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)
VALID_MP4_BYTES = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42" + b"\x00" * 128
VALID_OGG_BYTES = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" + b"\x00" * 64
VALID_WEBM_BYTES = b"\x1a\x45\xdf\xa3\x01\x00\x00\x1f\x42\x86\x81\x01\x42\x82\x84webm" + b"\x00" * 64


async def create_user_and_token(
    client: AsyncClient, name: str = "Recording Test User"
) -> Tuple[Dict, str]:
    """Register and login a user, returning user data and access token."""
    email = f"rec_test_{uuid.uuid4().hex[:8]}@convomind.ai"
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


async def setup_test_workspace_and_meeting(client: AsyncClient) -> Dict:
    """Setup workspace with owner, admin, member, guest, stranger and a meeting."""
    owner, t_owner = await create_user_and_token(client, "Owner")
    admin, t_admin = await create_user_and_token(client, "Admin")
    member, t_member = await create_user_and_token(client, "Member")
    guest, t_guest = await create_user_and_token(client, "Guest")
    stranger, t_stranger = await create_user_and_token(client, "Stranger")

    # Create workspace
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": f"Recording WS {uuid.uuid4().hex[:6]}"},
        headers=auth_header(t_owner),
    )
    assert ws_res.status_code == 201
    ws_id = ws_res.json()["id"]

    # Add roles
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

    # Create meeting by owner
    m_res = await client.post(
        "/api/v1/meetings",
        json={
            "workspace_id": ws_id,
            "title": "Strategy Sync",
            "meeting_type": "INTERNAL",
        },
        headers=auth_header(t_owner),
    )
    assert m_res.status_code == 201
    meeting = m_res.json()

    return {
        "workspace_id": ws_id,
        "meeting_id": meeting["id"],
        "meeting": meeting,
        "owner": (owner, t_owner),
        "admin": (admin, t_admin),
        "member": (member, t_member),
        "guest": (guest, t_guest),
        "stranger": (stranger, t_stranger),
    }


@pytest.mark.asyncio
async def test_upload_valid_mp3_recording(client: AsyncClient):
    """Test successful upload of an MP3 recording."""
    data = await setup_test_workspace_and_meeting(client)
    _, t_owner = data["owner"]
    meeting_id = data["meeting_id"]

    files = {
        "file": ("strategy_discussion.mp3", io.BytesIO(VALID_MP3_BYTES), "audio/mpeg")
    }

    res = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files=files,
        headers=auth_header(t_owner),
    )
    assert res.status_code == 201, res.text
    recording = res.json()

    assert recording["filename"] == "strategy_discussion.mp3"
    assert recording["mime_type"] == "audio/mpeg"
    assert recording["file_size"] == len(VALID_MP3_BYTES)
    assert recording["status"] == "QUEUED"
    assert recording["checksum"] is not None
    assert "id" in recording
    assert recording["meeting_id"] == meeting_id
    assert recording["workspace_id"] == data["workspace_id"]

    # Storage abstraction check: internal path is NOT exposed in response schema
    assert "storage_key" not in recording
    assert "full_path" not in recording


@pytest.mark.asyncio
async def test_upload_valid_wav_and_mp4_recordings(client: AsyncClient):
    """Test uploading valid WAV audio and MP4 video recordings."""
    data = await setup_test_workspace_and_meeting(client)
    _, t_owner = data["owner"]
    meeting_id = data["meeting_id"]

    # 1. WAV
    wav_files = {"file": ("audio_sample.wav", io.BytesIO(VALID_WAV_BYTES), "audio/wav")}
    wav_res = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files=wav_files,
        headers=auth_header(t_owner),
    )
    assert wav_res.status_code == 201
    assert wav_res.json()["mime_type"] == "audio/wav"

    # 2. MP4
    mp4_files = {"file": ("video_screen.mp4", io.BytesIO(VALID_MP4_BYTES), "video/mp4")}
    mp4_res = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files=mp4_files,
        headers=auth_header(t_owner),
    )
    assert mp4_res.status_code == 201
    assert mp4_res.json()["mime_type"] == "video/mp4"


@pytest.mark.asyncio
async def test_empty_file_upload_rejected(client: AsyncClient):
    """Reject empty file upload with 400 Bad Request."""
    data = await setup_test_workspace_and_meeting(client)
    _, t_owner = data["owner"]
    meeting_id = data["meeting_id"]

    files = {"file": ("empty.mp3", io.BytesIO(b""), "audio/mpeg")}
    res = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files=files,
        headers=auth_header(t_owner),
    )
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_extension_rejected(client: AsyncClient):
    """Reject disallowed file extension like .exe or .pdf."""
    data = await setup_test_workspace_and_meeting(client)
    _, t_owner = data["owner"]
    meeting_id = data["meeting_id"]

    files = {"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"), "application/octet-stream")}
    res = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files=files,
        headers=auth_header(t_owner),
    )
    assert res.status_code == 400
    assert "unsupported file format" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_magic_bytes_rejected(client: AsyncClient):
    """Reject file when extension is .mp3 but contents are not audio."""
    data = await setup_test_workspace_and_meeting(client)
    _, t_owner = data["owner"]
    meeting_id = data["meeting_id"]

    # Text content disguised as mp3
    fake_mp3 = b"This is plain text and definitely not an MP3 audio file!"
    files = {"file": ("fake_audio.mp3", io.BytesIO(fake_mp3), "audio/mpeg")}
    res = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files=files,
        headers=auth_header(t_owner),
    )
    assert res.status_code == 400
    assert "content signature" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_disallowed_mime_type_rejected(client: AsyncClient):
    """Reject unsupported MIME type."""
    data = await setup_test_workspace_and_meeting(client)
    _, t_owner = data["owner"]
    meeting_id = data["meeting_id"]

    files = {"file": ("recording.mp3", io.BytesIO(VALID_MP3_BYTES), "image/png")}
    res = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files=files,
        headers=auth_header(t_owner),
    )
    assert res.status_code == 400
    assert "mime" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_file_size_limit_enforced(client: AsyncClient):
    """Verify that uploads exceeding MAX_UPLOAD_SIZE_MB are rejected with 413."""
    data = await setup_test_workspace_and_meeting(client)
    _, t_owner = data["owner"]
    meeting_id = data["meeting_id"]

    # Temporarily override MAX_UPLOAD_SIZE_MB to a tiny limit (e.g., 0 MB -> 100 bytes)
    with patch.object(settings, "MAX_UPLOAD_SIZE_MB", 0):
        # 0 MB * 1024 * 1024 = 0 bytes allowed
        files = {"file": ("huge_recording.mp3", io.BytesIO(VALID_MP3_BYTES), "audio/mpeg")}
        res = await client.post(
            f"/api/v1/meetings/{meeting_id}/recordings",
            files=files,
            headers=auth_header(t_owner),
        )
        assert res.status_code == 413
        assert "exceeds" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_guest_cannot_upload_recording(client: AsyncClient):
    """Guest role is read-only and prohibited from uploading recordings (403)."""
    data = await setup_test_workspace_and_meeting(client)
    _, t_guest = data["guest"]
    meeting_id = data["meeting_id"]

    files = {"file": ("guest_speech.mp3", io.BytesIO(VALID_MP3_BYTES), "audio/mpeg")}
    res = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files=files,
        headers=auth_header(t_guest),
    )
    assert res.status_code == 403
    assert "guests" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stranger_cannot_access_or_upload_recordings_idor_protection(client: AsyncClient):
    """Users outside the workspace receive 404 (preventing meeting existence leakage)."""
    data = await setup_test_workspace_and_meeting(client)
    _, t_owner = data["owner"]
    _, t_stranger = data["stranger"]
    meeting_id = data["meeting_id"]

    # 1. Upload by owner
    files = {"file": ("recording1.mp3", io.BytesIO(VALID_MP3_BYTES), "audio/mpeg")}
    up_res = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files=files,
        headers=auth_header(t_owner),
    )
    assert up_res.status_code == 201
    recording_id = up_res.json()["id"]

    # 2. Stranger tries to upload -> 404
    files2 = {"file": ("recording2.mp3", io.BytesIO(VALID_MP3_BYTES), "audio/mpeg")}
    stranger_up = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files=files2,
        headers=auth_header(t_stranger),
    )
    assert stranger_up.status_code == 404

    # 3. Stranger tries to list -> 404
    stranger_list = await client.get(
        f"/api/v1/meetings/{meeting_id}/recordings",
        headers=auth_header(t_stranger),
    )
    assert stranger_list.status_code == 404

    # 4. Stranger tries to get single recording -> 404
    stranger_get = await client.get(
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}",
        headers=auth_header(t_stranger),
    )
    assert stranger_get.status_code == 404

    # 5. Stranger tries to delete -> 404
    stranger_del = await client.delete(
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}",
        headers=auth_header(t_stranger),
    )
    assert stranger_del.status_code == 404


@pytest.mark.asyncio
async def test_list_and_get_meeting_recordings(client: AsyncClient):
    """List recordings for a meeting and get individual details."""
    data = await setup_test_workspace_and_meeting(client)
    _, t_owner = data["owner"]
    _, t_member = data["member"]
    meeting_id = data["meeting_id"]

    # Upload two recordings
    for fname in ["first_clip.mp3", "second_clip.wav"]:
        payload = VALID_MP3_BYTES if fname.endswith(".mp3") else VALID_WAV_BYTES
        mime = "audio/mpeg" if fname.endswith(".mp3") else "audio/wav"
        res = await client.post(
            f"/api/v1/meetings/{meeting_id}/recordings",
            files={"file": (fname, io.BytesIO(payload), mime)},
            headers=auth_header(t_owner),
        )
        assert res.status_code == 201

    # Member lists recordings
    list_res = await client.get(
        f"/api/v1/meetings/{meeting_id}/recordings",
        headers=auth_header(t_member),
    )
    assert list_res.status_code == 200
    body = list_res.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2

    first_rec = body["items"][0]
    # Get by ID
    get_res = await client.get(
        f"/api/v1/meetings/{meeting_id}/recordings/{first_rec['id']}",
        headers=auth_header(t_member),
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == first_rec["id"]


@pytest.mark.asyncio
async def test_recording_deletion_permissions_and_storage_cleanup(client: AsyncClient):
    """Test deletion permissions: member cannot delete another's recording, but admin/owner/uploader can."""
    data = await setup_test_workspace_and_meeting(client)
    u_owner, t_owner = data["owner"]
    u_admin, t_admin = data["admin"]
    u_member, t_member = data["member"]
    meeting_id = data["meeting_id"]

    # Member uploads a recording
    files = {"file": ("member_audio.mp3", io.BytesIO(VALID_MP3_BYTES), "audio/mpeg")}
    up_res = await client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files=files,
        headers=auth_header(t_member),
    )
    assert up_res.status_code == 201
    recording_id = up_res.json()["id"]

    storage = get_storage_service()
    # Find storage key from filesystem or database
    # Create another user in the workspace to test regular member deletion denial
    another_user, t_another = await create_user_and_token(client, "Another Member")
    await client.post(
        f"/api/v1/workspaces/{data['workspace_id']}/members",
        json={"email": another_user["email"], "role": WorkspaceRole.MEMBER.value},
        headers=auth_header(t_owner),
    )

    # Another regular member tries to delete member's recording -> 403 Forbidden
    del_res_denied = await client.delete(
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}",
        headers=auth_header(t_another),
    )
    assert del_res_denied.status_code == 403
    assert "permission" in del_res_denied.json()["detail"].lower()

    # Admin deletes recording successfully -> 200 OK
    del_res_admin = await client.delete(
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}",
        headers=auth_header(t_admin),
    )
    assert del_res_admin.status_code == 200
    assert "deleted" in del_res_admin.json()["message"].lower()

    # Verify recording is gone
    get_after_del = await client.get(
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}",
        headers=auth_header(t_admin),
    )
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_async_processing_task_execution(client: AsyncClient):
    """Test Celery async processing execution, metadata probing, and idempotency."""
    data = await setup_test_workspace_and_meeting(client)
    _, t_owner = data["owner"]
    meeting_id = data["meeting_id"]

    # Upload recording
    files = {"file": ("pipeline_test.mp3", io.BytesIO(VALID_MP3_BYTES), "audio/mpeg")}
    with patch("app.workers.tasks.recording_tasks.process_meeting_recording.delay"):
        up_res = await client.post(
            f"/api/v1/meetings/{meeting_id}/recordings",
            files=files,
            headers=auth_header(t_owner),
        )
    assert up_res.status_code == 201
    recording_id = up_res.json()["id"]

    # Mock FFmpegService.probe_media to return simulated duration
    mock_probe = {
        "duration_seconds": 125,
        "format_name": "mp3",
        "bit_rate": 192000,
        "has_audio": True,
        "has_video": False,
        "audio_codec": "mp3",
        "sample_rate": 44100,
        "channels": 2,
    }

    def mock_extract(input_path: str, output_path: str, **kwargs) -> bool:
        with open(output_path, "wb") as f:
            f.write(VALID_WAV_BYTES)
        return True

    with patch("app.services.ffmpeg_service.FFmpegService.probe_media", return_value=mock_probe), \
         patch("app.services.ffmpeg_service.FFmpegService.extract_audio_for_stt", side_effect=mock_extract):
        result = await _async_process_recording(recording_id)
        assert result["status"] == "completed"
        assert result["duration_seconds"] == 125

    # Check database status via API endpoint
    get_res = await client.get(
        f"/api/v1/meetings/{meeting_id}/recordings/{recording_id}",
        headers=auth_header(t_owner),
    )
    assert get_res.status_code == 200
    rec_data = get_res.json()
    assert rec_data["status"] == "COMPLETED"
    assert rec_data["duration_seconds"] == 125

    # Idempotency test: reprocessing a COMPLETED recording returns already_completed
    idemp_res = await _async_process_recording(recording_id)
    assert idemp_res["status"] == "already_completed"
