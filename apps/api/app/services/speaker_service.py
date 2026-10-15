"""Speaker domain service handling meeting speaker CRUD and workspace user association."""

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkspaceRole
from app.models.meeting import Meeting, Speaker
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.transcript import SpeakerCreate, SpeakerUpdate

logger = logging.getLogger(__name__)


class SpeakerService:
    """Service handling meeting speaker CRUD, RBAC, and user associations."""

    @staticmethod
    async def _verify_meeting_access(
        db: AsyncSession,
        meeting_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Tuple[Meeting, WorkspaceMember]:
        """Verify user is a member of the workspace owning the meeting."""
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

    @classmethod
    async def list_speakers(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
    ) -> List[Speaker]:
        """List all identified speakers for a meeting."""
        meeting, _ = await cls._verify_meeting_access(db, meeting_id, current_user.id)

        stmt = (
            select(Speaker)
            .where(Speaker.meeting_id == meeting.id)
            .order_by(Speaker.created_at.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_speaker(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        speaker_id: uuid.UUID,
        current_user: User,
    ) -> Speaker:
        """Get a single speaker by ID."""
        meeting, _ = await cls._verify_meeting_access(db, meeting_id, current_user.id)

        stmt = select(Speaker).where(
            Speaker.id == speaker_id,
            Speaker.meeting_id == meeting.id,
        )
        res = await db.execute(stmt)
        speaker = res.scalar_one_or_none()
        if not speaker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Speaker not found.",
            )
        return speaker

    @classmethod
    async def create_speaker(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        data: SpeakerCreate,
    ) -> Speaker:
        """Create a new speaker entry for a meeting."""
        meeting, member = await cls._verify_meeting_access(db, meeting_id, current_user.id)

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests cannot add speakers.",
            )

        if data.user_id:
            # Verify user is member of this meeting's workspace
            ws_user_stmt = select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == meeting.workspace_id,
                WorkspaceMember.user_id == data.user_id,
            )
            ws_user = (await db.execute(ws_user_stmt)).scalar_one_or_none()
            if not ws_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Specified user does not belong to this workspace.",
                )

        speaker = Speaker(
            meeting_id=meeting.id,
            label=data.label,
            name=data.name,
            user_id=data.user_id,
        )
        db.add(speaker)
        await db.commit()
        await db.refresh(speaker)
        return speaker

    @classmethod
    async def update_speaker(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        speaker_id: uuid.UUID,
        current_user: User,
        data: SpeakerUpdate,
    ) -> Speaker:
        """Update a speaker's name, label, or user association."""
        meeting, member = await cls._verify_meeting_access(db, meeting_id, current_user.id)

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests cannot update speakers.",
            )

        speaker = await cls.get_speaker(db, meeting_id, speaker_id, current_user)

        if data.user_id is not None and data.user_id != speaker.user_id:
            ws_user_stmt = select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == meeting.workspace_id,
                WorkspaceMember.user_id == data.user_id,
            )
            ws_user = (await db.execute(ws_user_stmt)).scalar_one_or_none()
            if not ws_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Specified user does not belong to this workspace.",
                )
            speaker.user_id = data.user_id

        if data.label is not None:
            speaker.label = data.label
        if data.name is not None:
            speaker.name = data.name

        await db.commit()
        await db.refresh(speaker)
        return speaker

    @classmethod
    async def delete_speaker(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        speaker_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """Delete a speaker from a meeting (unlinking any associated segments)."""
        meeting, member = await cls._verify_meeting_access(db, meeting_id, current_user.id)

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests cannot delete speakers.",
            )

        speaker = await cls.get_speaker(db, meeting_id, speaker_id, current_user)
        await db.delete(speaker)
        await db.commit()

    @classmethod
    async def trigger_diarization(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
    ) -> Dict[str, Any]:
        """Trigger asynchronous speaker diarization for a meeting recording."""
        meeting, member = await cls._verify_meeting_access(db, meeting_id, current_user.id)

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests cannot trigger speaker diarization.",
            )

        # Check for meeting recording
        from app.models.recording import MeetingRecording
        rec_stmt = (
            select(MeetingRecording)
            .where(MeetingRecording.meeting_id == meeting.id)
            .order_by(MeetingRecording.created_at.desc())
        )
        recording = (await db.execute(rec_stmt)).scalars().first()

        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No recording found for this meeting.",
            )

        # Queue Celery diarization task
        from app.workers.tasks.diarization_tasks import process_speaker_diarization
        task_res = process_speaker_diarization.delay(str(recording.id))

        return {
            "message": "Speaker diarization process queued successfully.",
            "meeting_id": str(meeting.id),
            "recording_id": str(recording.id),
            "task_id": task_res.id,
        }

