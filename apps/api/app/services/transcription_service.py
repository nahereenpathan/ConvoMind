"""Transcription domain service handling queries, RBAC validation, pagination, segment edits, speaker assignment, and search."""

import logging
import os
import uuid
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import RecordingStatus, TranscriptStatus, WorkspaceRole
from app.models.meeting import Meeting, Speaker
from app.models.recording import MeetingRecording
from app.models.transcript import Transcript, TranscriptSegment
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.transcript import (
    TranscriptSearchResponse,
    TranscriptSearchResultItem,
    TranscriptSearchSegmentResult,
    TranscriptSegmentBatchSpeaker,
    TranscriptSegmentCreate,
    TranscriptSegmentUpdate,
    TranscriptUpdate,
)

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service handling meeting transcription retrieval, validation, segment management, search, and queuing."""

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
    async def _recalculate_transcript_aggregates(
        cls,
        db: AsyncSession,
        transcript_id: uuid.UUID,
    ) -> None:
        """Recalculate full_text, word_count, and duration for a transcript from its segments."""
        stmt = (
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript_id)
            .order_by(TranscriptSegment.sequence_order.asc())
        )
        res = await db.execute(stmt)
        segments = list(res.scalars().all())

        full_text = " ".join(s.text.strip() for s in segments if s.text and s.text.strip())
        word_count = len(full_text.split()) if full_text else 0
        duration = max((s.end_time for s in segments), default=0.0)

        tr_stmt = select(Transcript).where(Transcript.id == transcript_id)
        tr_res = await db.execute(tr_stmt)
        transcript = tr_res.scalar_one_or_none()
        if transcript:
            transcript.full_text = full_text
            transcript.word_count = word_count
            if duration > 0:
                transcript.duration = duration

    @classmethod
    async def get_transcript_for_meeting(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        page: int = 1,
        page_size: int = 100,
    ) -> Tuple[Meeting, Transcript, List[TranscriptSegment], int]:
        """Fetch meeting, primary transcript, and paginated segments with speakers."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        stmt = (
            select(Transcript)
            .where(Transcript.meeting_id == meeting.id)
            .order_by(Transcript.updated_at.desc())
        )
        result = await db.execute(stmt)
        transcript = result.scalars().first()

        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No transcript found for this meeting.",
            )

        count_stmt = select(func.count(TranscriptSegment.id)).where(
            TranscriptSegment.transcript_id == transcript.id
        )
        total_segments = (await db.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        seg_stmt = (
            select(TranscriptSegment)
            .options(selectinload(TranscriptSegment.speaker))
            .where(TranscriptSegment.transcript_id == transcript.id)
            .order_by(TranscriptSegment.sequence_order.asc())
            .offset(offset)
            .limit(page_size)
        )
        seg_res = await db.execute(seg_stmt)
        segments = list(seg_res.scalars().all())

        return meeting, transcript, segments, total_segments

    @classmethod
    async def get_all_segments_for_export(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
    ) -> Tuple[Meeting, Transcript, List[TranscriptSegment]]:
        """Fetch meeting, transcript, and all segments ordered for export."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        stmt = (
            select(Transcript)
            .where(Transcript.meeting_id == meeting.id)
            .order_by(Transcript.updated_at.desc())
        )
        result = await db.execute(stmt)
        transcript = result.scalars().first()

        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No transcript found for this meeting.",
            )

        seg_stmt = (
            select(TranscriptSegment)
            .options(selectinload(TranscriptSegment.speaker))
            .where(TranscriptSegment.transcript_id == transcript.id)
            .order_by(TranscriptSegment.sequence_order.asc())
        )
        seg_res = await db.execute(seg_stmt)
        segments = list(seg_res.scalars().all())

        return meeting, transcript, segments

    @classmethod
    async def update_transcript(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        data: TranscriptUpdate,
    ) -> Transcript:
        """Update transcript metadata (e.g. language). Only non-GUEST workspace members."""
        meeting, member = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests cannot update transcripts.",
            )

        stmt = (
            select(Transcript)
            .where(Transcript.meeting_id == meeting.id)
            .order_by(Transcript.updated_at.desc())
        )
        result = await db.execute(stmt)
        transcript = result.scalars().first()

        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No transcript found for this meeting.",
            )

        if data.language is not None:
            transcript.language = data.language

        await db.commit()
        await db.refresh(transcript)
        return transcript

    @classmethod
    async def list_segments(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        page: int = 1,
        page_size: int = 50,
        query: Optional[str] = None,
    ) -> Tuple[Transcript, List[TranscriptSegment], int]:
        """List segments with optional text filtering."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        stmt = (
            select(Transcript)
            .where(Transcript.meeting_id == meeting.id)
            .order_by(Transcript.updated_at.desc())
        )
        result = await db.execute(stmt)
        transcript = result.scalars().first()

        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No transcript found for this meeting.",
            )

        count_query = select(func.count(TranscriptSegment.id)).where(
            TranscriptSegment.transcript_id == transcript.id
        )
        data_query = (
            select(TranscriptSegment)
            .options(selectinload(TranscriptSegment.speaker))
            .where(TranscriptSegment.transcript_id == transcript.id)
        )

        if query and query.strip():
            filter_clause = TranscriptSegment.text.ilike(f"%{query.strip()}%")
            count_query = count_query.where(filter_clause)
            data_query = data_query.where(filter_clause)

        total = (await db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        data_query = (
            data_query.order_by(TranscriptSegment.sequence_order.asc())
            .offset(offset)
            .limit(page_size)
        )

        res = await db.execute(data_query)
        segments = list(res.scalars().all())

        return transcript, segments, total

    @classmethod
    async def get_segment(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        segment_id: uuid.UUID,
        current_user: User,
    ) -> TranscriptSegment:
        """Fetch a single segment by ID."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        stmt = (
            select(TranscriptSegment)
            .options(selectinload(TranscriptSegment.speaker))
            .join(Transcript, Transcript.id == TranscriptSegment.transcript_id)
            .where(
                TranscriptSegment.id == segment_id,
                Transcript.meeting_id == meeting.id,
            )
        )
        res = await db.execute(stmt)
        segment = res.scalar_one_or_none()

        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcript segment not found.",
            )

        return segment

    @classmethod
    async def create_segment(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        data: TranscriptSegmentCreate,
    ) -> TranscriptSegment:
        """Insert a new segment into the transcript with sequence ordering."""
        meeting, member = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests cannot add transcript segments.",
            )

        stmt = (
            select(Transcript)
            .where(Transcript.meeting_id == meeting.id)
            .order_by(Transcript.updated_at.desc())
        )
        result = await db.execute(stmt)
        transcript = result.scalar_one_or_none()

        if not transcript:
            transcript = Transcript(
                meeting_id=meeting.id,
                workspace_id=meeting.workspace_id,
                status=TranscriptStatus.COMPLETED,
                full_text="",
                word_count=0,
                provider="manual",
            )
            db.add(transcript)
            await db.flush()

        # Validate speaker if provided
        if data.speaker_id:
            spk_stmt = select(Speaker).where(
                Speaker.id == data.speaker_id,
                Speaker.meeting_id == meeting.id,
            )
            speaker = (await db.execute(spk_stmt)).scalar_one_or_none()
            if not speaker:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Speaker does not exist for this meeting.",
                )

        count_stmt = select(func.count(TranscriptSegment.id)).where(
            TranscriptSegment.transcript_id == transcript.id
        )
        current_count = (await db.execute(count_stmt)).scalar() or 0

        target_order = data.sequence_order
        if target_order is None or target_order >= current_count:
            target_order = current_count
        else:
            # Shift existing segments starting at target_order using safe two-step offset
            shift_up_offset = 1_000_000
            await db.execute(
                update(TranscriptSegment)
                .where(
                    TranscriptSegment.transcript_id == transcript.id,
                    TranscriptSegment.sequence_order >= target_order,
                )
                .values(sequence_order=TranscriptSegment.sequence_order + shift_up_offset)
            )
            await db.execute(
                update(TranscriptSegment)
                .where(
                    TranscriptSegment.transcript_id == transcript.id,
                    TranscriptSegment.sequence_order >= target_order + shift_up_offset,
                )
                .values(sequence_order=TranscriptSegment.sequence_order - (shift_up_offset - 1))
            )

        new_segment = TranscriptSegment(
            transcript_id=transcript.id,
            sequence_order=target_order,
            start_time=data.start_time,
            end_time=data.end_time,
            text=data.text.strip(),
            confidence=data.confidence,
            speaker_id=data.speaker_id,
        )
        db.add(new_segment)
        await db.flush()

        await cls._recalculate_transcript_aggregates(db, transcript.id)
        await db.commit()

        # Re-fetch with speaker relationship loaded
        return await cls.get_segment(db, meeting.id, new_segment.id, current_user)

    @classmethod
    async def update_segment(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        segment_id: uuid.UUID,
        current_user: User,
        data: TranscriptSegmentUpdate,
    ) -> TranscriptSegment:
        """Update an existing segment's text, timestamps, or speaker."""
        meeting, member = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests cannot edit transcript segments.",
            )

        segment = await cls.get_segment(db, meeting_id, segment_id, current_user)

        # Validate timestamps if only one is provided
        new_start = data.start_time if data.start_time is not None else segment.start_time
        new_end = data.end_time if data.end_time is not None else segment.end_time
        if new_end < new_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Segment end_time cannot be less than start_time.",
            )

        # Validate speaker if provided
        if data.speaker_id is not None:
            spk_stmt = select(Speaker).where(
                Speaker.id == data.speaker_id,
                Speaker.meeting_id == meeting.id,
            )
            speaker = (await db.execute(spk_stmt)).scalar_one_or_none()
            if not speaker:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Speaker does not exist for this meeting.",
                )
            segment.speaker_id = data.speaker_id

        text_changed = False
        if data.text is not None:
            segment.text = data.text.strip()
            text_changed = True

        if data.start_time is not None:
            segment.start_time = data.start_time
        if data.end_time is not None:
            segment.end_time = data.end_time
        if data.confidence is not None:
            segment.confidence = data.confidence

        await db.flush()

        if text_changed or data.end_time is not None:
            await cls._recalculate_transcript_aggregates(db, segment.transcript_id)

        await db.commit()
        return await cls.get_segment(db, meeting.id, segment.id, current_user)

    @classmethod
    async def delete_segment(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        segment_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """Delete a transcript segment and re-sequence subsequent segments."""
        meeting, member = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests cannot delete transcript segments.",
            )

        segment = await cls.get_segment(db, meeting_id, segment_id, current_user)
        deleted_order = segment.sequence_order
        transcript_id = segment.transcript_id

        await db.delete(segment)
        await db.flush()

        # Re-index remaining segments with safe two-step offset
        shift_up_offset = 1_000_000
        await db.execute(
            update(TranscriptSegment)
            .where(
                TranscriptSegment.transcript_id == transcript_id,
                TranscriptSegment.sequence_order > deleted_order,
            )
            .values(sequence_order=TranscriptSegment.sequence_order + shift_up_offset)
        )
        await db.execute(
            update(TranscriptSegment)
            .where(
                TranscriptSegment.transcript_id == transcript_id,
                TranscriptSegment.sequence_order > deleted_order + shift_up_offset,
            )
            .values(sequence_order=TranscriptSegment.sequence_order - (shift_up_offset + 1))
        )

        await cls._recalculate_transcript_aggregates(db, transcript_id)
        await db.commit()

    @classmethod
    async def batch_assign_speaker(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        data: TranscriptSegmentBatchSpeaker,
    ) -> int:
        """Assign speaker identity to multiple segments in a single operation."""
        meeting, member = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests cannot assign speakers.",
            )

        # Validate speaker if assigning
        if data.speaker_id:
            spk_stmt = select(Speaker).where(
                Speaker.id == data.speaker_id,
                Speaker.meeting_id == meeting.id,
            )
            speaker = (await db.execute(spk_stmt)).scalar_one_or_none()
            if not speaker:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Speaker does not exist for this meeting.",
                )

        stmt = (
            select(Transcript)
            .where(Transcript.meeting_id == meeting.id)
            .order_by(Transcript.updated_at.desc())
        )
        transcript = (await db.execute(stmt)).scalar_one_or_none()
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No transcript found for this meeting.",
            )

        # Update segments matching the transcript and requested IDs
        upd = (
            update(TranscriptSegment)
            .where(
                TranscriptSegment.transcript_id == transcript.id,
                TranscriptSegment.id.in_(data.segment_ids),
            )
            .values(speaker_id=data.speaker_id)
        )
        res = await db.execute(upd)
        await db.commit()
        return res.rowcount

    @classmethod
    async def search_workspace_transcripts(
        cls,
        db: AsyncSession,
        workspace_id: uuid.UUID,
        query: str,
        current_user: User,
        limit: int = 50,
        offset: int = 0,
    ) -> TranscriptSearchResponse:
        """Search across all transcripts within a workspace."""
        # Verify workspace membership
        ws_stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
        member = (await db.execute(ws_stmt)).scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found.",
            )

        if not query or not query.strip():
            return TranscriptSearchResponse(query="", total_matches=0, results=[])

        clean_query = query.strip()
        search_filter = TranscriptSegment.text.ilike(f"%{clean_query}%")

        stmt = (
            select(TranscriptSegment, Transcript, Meeting)
            .options(selectinload(TranscriptSegment.speaker))
            .join(Transcript, Transcript.id == TranscriptSegment.transcript_id)
            .join(Meeting, Meeting.id == Transcript.meeting_id)
            .where(
                Meeting.workspace_id == workspace_id,
                search_filter,
            )
            .order_by(Transcript.updated_at.desc(), TranscriptSegment.sequence_order.asc())
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        rows = res.all()

        # Group matches by transcript
        grouped: dict[uuid.UUID, TranscriptSearchResultItem] = {}
        total_segments_matched = 0

        for segment, transcript, meeting in rows:
            total_segments_matched += 1
            if transcript.id not in grouped:
                grouped[transcript.id] = TranscriptSearchResultItem(
                    transcript_id=transcript.id,
                    meeting_id=meeting.id,
                    meeting_title=meeting.title,
                    workspace_id=meeting.workspace_id,
                    language=transcript.language,
                    matched_segment_count=0,
                    matched_segments=[],
                )

            speaker_name = segment.speaker.name if segment.speaker else None
            speaker_label = segment.speaker.label if segment.speaker else None

            grouped[transcript.id].matched_segments.append(
                TranscriptSearchSegmentResult(
                    segment_id=segment.id,
                    sequence_order=segment.sequence_order,
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    text=segment.text,
                    confidence=segment.confidence,
                    speaker_id=segment.speaker_id,
                    speaker_name=speaker_name,
                    speaker_label=speaker_label,
                )
            )
            grouped[transcript.id].matched_segment_count += 1

        return TranscriptSearchResponse(
            query=clean_query,
            total_matches=total_segments_matched,
            results=list(grouped.values()),
        )

    @classmethod
    async def get_transcript_status(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
    ) -> Transcript:
        """Fetch current transcription status for a meeting."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        stmt = (
            select(Transcript)
            .where(Transcript.meeting_id == meeting.id)
            .order_by(Transcript.updated_at.desc())
        )
        result = await db.execute(stmt)
        transcript = result.scalar_one_or_none()

        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No transcription has been initiated for this meeting.",
            )

        return transcript

    @classmethod
    async def get_transcription_for_recording(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        recording_id: uuid.UUID,
        current_user: User,
    ) -> Transcript:
        """Fetch transcript associated with a specific recording."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        stmt = select(Transcript).where(
            Transcript.recording_id == recording_id,
            Transcript.meeting_id == meeting.id,
        )
        result = await db.execute(stmt)
        transcript = result.scalar_one_or_none()

        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No transcript found for the specified recording.",
            )

        return transcript

    @classmethod
    async def trigger_transcription(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        recording_id: uuid.UUID,
        current_user: User,
    ) -> MeetingRecording:
        """Trigger asynchronous transcription task for a recording."""
        meeting, member = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests are not permitted to trigger transcription.",
            )

        rec_stmt = select(MeetingRecording).where(
            MeetingRecording.id == recording_id,
            MeetingRecording.meeting_id == meeting.id,
        )
        rec_res = await db.execute(rec_stmt)
        recording = rec_res.scalar_one_or_none()

        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found.",
            )

        if recording.status == RecordingStatus.PROCESSING:
            logger.info(
                f"Recording {recording.id} is already PROCESSING. Returning idempotent response."
            )
            return recording

        # Transition to QUEUED
        recording.status = RecordingStatus.QUEUED
        recording.error_message = None
        await db.commit()
        await db.refresh(recording)

        # Dispatch processing task to active Celery worker or in-process asyncio fallback
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

