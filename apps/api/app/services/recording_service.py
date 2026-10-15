"""Meeting recording business logic, file validation, storage orchestration, and Celery dispatch."""

import logging
import os
import re
import uuid
from typing import List, Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import MeetingStatus, RecordingStatus, WorkspaceRole
from app.models.meeting import Meeting
from app.models.recording import MeetingRecording
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.services.storage_service import FileSizeExceededError, get_storage_service

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".mp4", ".webm", ".mov"}

ALLOWED_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/x-m4a",
    "audio/m4a",
    "audio/mp4",
    "audio/ogg",
    "video/ogg",
    "application/ogg",
    "video/mp4",
    "video/webm",
    "audio/webm",
    "video/quicktime",
    "application/octet-stream",
}


def sanitize_filename(filename: Optional[str]) -> str:
    """Sanitize filename to prevent path traversal and strip illegal characters."""
    if not filename:
        return "recording.bin"
    base = os.path.basename(filename)
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    return safe[:200] if safe else "recording.bin"


def validate_magic_bytes(header: bytes, ext: str) -> bool:
    """Validate file signature (magic bytes) against expected media format container."""
    if not header:
        return False
    ext = ext.lower()
    if ext == ".mp3":
        # ID3 header or sync frame
        if header.startswith(b"ID3"):
            return True
        if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            return True
        return False
    elif ext == ".wav":
        # RIFF....WAVE
        return len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WAVE"
    elif ext in (".mp4", ".m4a", ".mov"):
        # ISO base media format box signatures
        if len(header) >= 8 and (
            header[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"skip")
            or header[:4] in (b"moov", b"mdat", b"wide", b"skip")
        ):
            return True
        return False
    elif ext == ".ogg":
        return header.startswith(b"OggS")
    elif ext == ".webm":
        # EBML header
        return header.startswith(b"\x1a\x45\xdf\xa3")
    return False


class RecordingService:
    """Service handling meeting recording uploads, validation, storage, and retrieval."""

    @staticmethod
    async def _get_meeting_and_member(
        db: AsyncSession,
        meeting_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Tuple[Meeting, WorkspaceMember]:
        """Fetch meeting and workspace member record, raising 404 if not found or unauthorized."""
        stmt = (
            select(Meeting, WorkspaceMember)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Meeting.workspace_id)
            .where(
                Meeting.id == meeting_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found.",
            )
        return row[0], row[1]

    @staticmethod
    async def upload_recording(
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        file: UploadFile,
        dispatch_worker: bool = True,
    ) -> MeetingRecording:
        """Validate, store, record in database, and enqueue asynchronous media processing."""
        # 1. Authorization: meeting must exist in a workspace user has access to
        meeting, member = await RecordingService._get_meeting_and_member(
            db, meeting_id, current_user.id
        )

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests are not permitted to upload recordings to this meeting.",
            )

        # 2. Extension validation
        safe_name = sanitize_filename(file.filename)
        _, ext = os.path.splitext(safe_name.lower())
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        # 3. Content-Type MIME validation
        content_type = (file.content_type or "application/octet-stream").lower()
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid MIME content type '{content_type}' for recording upload.",
            )

        # 4. Read initial header chunk for empty file check and magic bytes inspection
        header = await file.read(64)
        if not header or len(header) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        if not validate_magic_bytes(header, ext):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded file content signature does not match expected format {ext}.",
            )

        # Rewind file pointer to beginning for complete streaming write
        await file.seek(0)

        # 5. Save to storage backend with chunked streaming and size enforcement
        storage = get_storage_service()
        file_uuid = uuid.uuid4()
        storage_key = f"recordings/{meeting.workspace_id}/{meeting.id}/{file_uuid}_{safe_name}"
        max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

        try:
            file_size, checksum = await storage.save_file(
                file=file,
                storage_key=storage_key,
                max_size_bytes=max_size_bytes,
            )
        except FileSizeExceededError:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed upload size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
            )
        except ValueError as val_err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(val_err),
            )

        # 6. Create database record
        recording = MeetingRecording(
            id=file_uuid,
            meeting_id=meeting.id,
            workspace_id=meeting.workspace_id,
            uploaded_by_id=current_user.id,
            original_filename=file.filename or safe_name,
            storage_key=storage_key,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            status=RecordingStatus.UPLOADED,
            checksum=checksum,
        )
        db.add(recording)

        # Update meeting metadata if recording key is unset
        if not meeting.recording_key:
            meeting.recording_key = storage_key
        if meeting.status == MeetingStatus.SCHEDULED:
            meeting.status = MeetingStatus.RECORDING

        await db.commit()
        await db.refresh(recording)

        # 7. Transition to QUEUED and dispatch processing task
        recording.status = RecordingStatus.QUEUED
        await db.commit()
        await db.refresh(recording)

        if dispatch_worker:
            if os.getenv("TESTING"):
                try:
                    from app.workers.tasks.recording_tasks import process_meeting_recording
                    process_meeting_recording.delay(str(recording.id))
                except Exception:
                    pass
            else:
                try:
                    from app.workers.celery_app import celery_app
                    celery_active = False
                    try:
                        inspector = celery_app.control.inspect(timeout=0.2)
                        ping_res = inspector.ping() if inspector else None
                        celery_active = bool(ping_res and len(ping_res) > 0)
                    except Exception:
                        celery_active = False

                    if celery_active:
                        from app.workers.tasks.recording_tasks import process_meeting_recording
                        process_meeting_recording.delay(str(recording.id))
                    else:
                        import asyncio
                        from app.workers.tasks.recording_tasks import _async_process_recording
                        asyncio.create_task(_async_process_recording(str(recording.id)))
                except Exception as exc:
                    logger.warning(
                        f"Could not enqueue Celery task for recording {recording.id}: {exc}. Executing in-process fallback."
                    )
                    import asyncio
                    from app.workers.tasks.recording_tasks import _async_process_recording
                    asyncio.create_task(_async_process_recording(str(recording.id)))

        return recording


    @staticmethod
    async def list_recordings(
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
    ) -> List[MeetingRecording]:
        """List all recordings for a meeting in an authorized workspace."""
        meeting, _ = await RecordingService._get_meeting_and_member(
            db, meeting_id, current_user.id
        )

        stmt = (
            select(MeetingRecording)
            .where(MeetingRecording.meeting_id == meeting.id)
            .order_by(MeetingRecording.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_recording(
        db: AsyncSession,
        meeting_id: uuid.UUID,
        recording_id: uuid.UUID,
        current_user: User,
    ) -> MeetingRecording:
        """Retrieve a specific recording if meeting belongs to authorized workspace."""
        meeting, _ = await RecordingService._get_meeting_and_member(
            db, meeting_id, current_user.id
        )

        stmt = select(MeetingRecording).where(
            MeetingRecording.id == recording_id,
            MeetingRecording.meeting_id == meeting.id,
        )
        result = await db.execute(stmt)
        recording = result.scalar_one_or_none()

        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found.",
            )
        return recording

    @staticmethod
    async def delete_recording(
        db: AsyncSession,
        meeting_id: uuid.UUID,
        recording_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """Delete a recording from storage and database, validating delete permissions."""
        meeting, member = await RecordingService._get_meeting_and_member(
            db, meeting_id, current_user.id
        )

        stmt = select(MeetingRecording).where(
            MeetingRecording.id == recording_id,
            MeetingRecording.meeting_id == meeting.id,
        )
        result = await db.execute(stmt)
        recording = result.scalar_one_or_none()

        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found.",
            )

        # Deletion permission: Owner, Admin, or the original uploader
        is_owner_or_admin = member.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
        is_uploader = recording.uploaded_by_id == current_user.id

        if not (is_owner_or_admin or is_uploader):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this recording.",
            )

        # Delete physical file from storage
        storage = get_storage_service()
        await storage.delete_file(recording.storage_key)

        # Clear meeting recording_key if this was the primary recording
        if meeting.recording_key == recording.storage_key:
            meeting.recording_key = None

        # Delete database record
        await db.delete(recording)
        await db.commit()
