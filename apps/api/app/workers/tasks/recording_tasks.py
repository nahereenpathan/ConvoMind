"""Celery tasks for meeting recording asynchronous transcription and audio processing."""

import asyncio
import logging
import os
import tempfile
import uuid
from typing import Any, Dict, Optional

from celery.exceptions import MaxRetriesExceededError
import redis
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.enums import MeetingStatus, RecordingStatus, TranscriptStatus
from app.models.meeting import Meeting
from app.models.recording import MeetingRecording
from app.models.transcript import Transcript, TranscriptSegment
from app.services.ffmpeg_service import get_ffmpeg_service
from app.services.storage_service import get_storage_service
from app.services.transcription import (
    TranscriptionPermanentError,
    TranscriptionTransientError,
    get_transcription_provider,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _sanitize_error_message(exc: Exception) -> str:
    """Format safe error message suitable for storage without leaking credentials."""
    msg = str(exc)
    # Strip any potential API key or bearer tokens
    for token in ("sk-", "Bearer", "password", "secret"):
        if token.lower() in msg.lower():
            return f"{type(exc).__name__}: An error occurred while communicating with provider."
    return f"{type(exc).__name__}: {msg[:250]}"


async def _async_process_recording(recording_id_str: str, force: bool = False) -> Dict[str, Any]:
    """Execute asynchronous audio extraction, transcription, and database persistence pipeline."""
    try:
        recording_id = uuid.UUID(recording_id_str)
    except (ValueError, TypeError) as exc:
        logger.error(f"Invalid recording UUID passed to worker: {recording_id_str} ({exc})")
        return {"status": "invalid_id", "recording_id": recording_id_str}

    storage_service = get_storage_service()
    ffmpeg_service = get_ffmpeg_service()

    # Distributed locking via Redis to prevent concurrent worker runs
    redis_client = None
    lock_acquired = False
    lock_key = f"lock:transcription:{recording_id_str}"

    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        lock_acquired = bool(redis_client.set(lock_key, "locked", nx=True, ex=600))
        if not lock_acquired and not force:
            logger.warning(
                f"Transcription for recording {recording_id_str} is already running on another worker."
            )
            return {"status": "already_running", "recording_id": recording_id_str}
    except Exception as lock_err:
        logger.warning(f"Could not check Redis lock: {lock_err}. Proceeding with pipeline.")

    temp_wav_path: Optional[str] = None

    try:
        async with AsyncSessionLocal() as session:
            # 1. Fetch recording
            result = await session.execute(
                select(MeetingRecording).where(MeetingRecording.id == recording_id)
            )
            recording = result.scalar_one_or_none()

            if not recording:
                logger.warning(f"Recording {recording_id} not found in database.")
                return {"status": "not_found", "recording_id": str(recording_id)}

            # 2. Check existing transcript and idempotency
            t_stmt = select(Transcript).where(Transcript.recording_id == recording.id)
            t_res = await session.execute(t_stmt)
            transcript = t_res.scalar_one_or_none()

            if (
                not force
                and recording.status == RecordingStatus.COMPLETED
                and transcript
                and transcript.status == TranscriptStatus.COMPLETED
            ):
                logger.info(f"Recording {recording_id} and its transcript are already COMPLETED.")
                return {
                    "status": "already_completed",
                    "recording_id": str(recording_id),
                    "transcript_id": str(transcript.id),
                    "duration_seconds": recording.duration_seconds,
                }

            # 3. Transition status to PROCESSING
            recording.status = RecordingStatus.PROCESSING
            recording.error_message = None

            if transcript is None:
                transcript = Transcript(
                    id=uuid.uuid4(),
                    meeting_id=recording.meeting_id,
                    recording_id=recording.id,
                    workspace_id=recording.workspace_id,
                    status=TranscriptStatus.PROCESSING,
                )
                session.add(transcript)
            else:
                transcript.status = TranscriptStatus.PROCESSING
                transcript.error_message = None

            await session.commit()
            await session.refresh(recording)
            await session.refresh(transcript)

            logger.info(
                f"[transcription started] recording_id={recording.id} meeting_id={recording.meeting_id}"
            )

            # 4. Storage file existence check
            file_path = storage_service.get_file_path(recording.storage_key)
            if not storage_service.file_exists(recording.storage_key):
                raise TranscriptionPermanentError(
                    f"Recording file missing from storage key: {recording.storage_key}"
                )

            # 5. Probe media metadata via FFprobe
            media_info = ffmpeg_service.probe_media(file_path)
            duration = media_info.get("duration_seconds")
            if duration is not None:
                recording.duration_seconds = duration

            # 6. Extract normalized audio to temporary WAV file (16kHz mono PCM)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            logger.info(f"[ffmpeg started] extracting STT audio to {temp_wav_path}")
            conversion_ok = ffmpeg_service.extract_audio_for_stt(
                input_path=file_path,
                output_path=temp_wav_path,
                sample_rate=16000,
                channels=1,
            )
            if not conversion_ok:
                if file_path.lower().endswith(".wav") and os.path.exists(file_path):
                    logger.info(f"Copying uploaded WAV file directly for STT: {file_path}")
                    import shutil
                    shutil.copyfile(file_path, temp_wav_path)
                elif os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    logger.info(f"Using uploaded media file directly for STT: {file_path}")
                    temp_wav_path = file_path
                else:
                    raise TranscriptionPermanentError(
                        f"FFmpeg audio extraction failed on '{file_path}' and media format could not be converted."
                    )

            logger.info("[ffmpeg completed] normalized WAV file created successfully.")


            # 7. Run Transcription Provider
            provider = get_transcription_provider()
            logger.info(f"[provider started] running provider={type(provider).__name__}")
            transcription_result = await provider.transcribe(temp_wav_path)
            logger.info(
                f"[provider completed] received {len(transcription_result.segments)} segments, "
                f"word_count={transcription_result.word_count}"
            )

            # 8. Clean up existing segments if re-processing to maintain idempotency
            await session.execute(
                delete(TranscriptSegment).where(TranscriptSegment.transcript_id == transcript.id)
            )

            # 9. Update Transcript record
            transcript.full_text = transcription_result.full_text
            transcript.word_count = transcription_result.word_count
            transcript.confidence_score = transcription_result.confidence_score
            transcript.language = transcription_result.language
            transcript.duration = transcription_result.duration or (float(duration) if duration else None)
            transcript.provider = transcription_result.provider
            transcript.processing_metadata = transcription_result.metadata
            transcript.status = TranscriptStatus.COMPLETED
            transcript.error_message = None

            # 10. Persist TranscriptSegment records with strict sequence ordering
            for seg_data in transcription_result.segments:
                segment = TranscriptSegment(
                    id=uuid.uuid4(),
                    transcript_id=transcript.id,
                    speaker_id=None,
                    sequence_order=seg_data.sequence_order,
                    start_time=seg_data.start_time,
                    end_time=seg_data.end_time,
                    text=seg_data.text,
                    confidence=seg_data.confidence,
                )
                session.add(segment)

            # 11. Complete recording and update meeting
            recording.status = RecordingStatus.COMPLETED
            recording.error_message = None

            meeting_res = await session.execute(
                select(Meeting).where(Meeting.id == recording.meeting_id)
            )
            meeting = meeting_res.scalar_one_or_none()
            if meeting:
                if duration and (meeting.duration_seconds is None or meeting.duration_seconds == 0):
                    meeting.duration_seconds = duration
                if meeting.status in (MeetingStatus.RECORDING, MeetingStatus.PROCESSING, MeetingStatus.IN_PROGRESS, MeetingStatus.SCHEDULED, MeetingStatus.FAILED):
                    meeting.status = MeetingStatus.COMPLETED

            await session.commit()
            logger.info(
                f"[transcription completed] recording_id={recording.id} transcript_id={transcript.id}"
            )

            # Enqueue recording_ready email
            try:
                from app.models.user import User
                from app.services.email.dispatch import EmailDispatchService
                if meeting and meeting.creator_id:
                    creator_res = await session.execute(select(User).where(User.id == meeting.creator_id))
                    creator_user = creator_res.scalar_one_or_none()
                    if creator_user and creator_user.email:
                        dur_str = f"{int(recording.duration_seconds // 60)}m {int(recording.duration_seconds % 60)}s" if recording.duration_seconds else "Completed"
                        await EmailDispatchService.enqueue_email(
                            db=session,
                            recipient_email=creator_user.email,
                            recipient_name=creator_user.full_name,
                            event_type="recording_ready",
                            template_data={
                                "meeting_id": str(meeting.id),
                                "meeting_title": meeting.title,
                                "duration": dur_str,
                            },
                            user_id=creator_user.id,
                            workspace_id=meeting.workspace_id,
                            meeting_id=meeting.id,
                            idempotency_key=f"recording_ready:{recording.id}:{creator_user.id}",
                            check_preference=True,
                        )
            except Exception as rec_email_err:
                logger.warning(f"Failed to enqueue recording ready email: {rec_email_err}")

            out_recording_id = str(recording.id)
            out_transcript_id = str(transcript.id)
            out_meeting_id = str(meeting.id)
            out_duration = transcript.duration
            out_segments_count = len(transcription_result.segments)

        # Trigger downstream vector embedding generation outside the active DB session
        try:
            from app.workers.celery_app import celery_app
            from app.workers.tasks.embedding_tasks import process_transcript_embeddings, _async_process_transcript_embeddings
            celery_active = False
            try:
                inspector = celery_app.control.inspect(timeout=0.2)
                ping_res = inspector.ping() if inspector else None
                celery_active = bool(ping_res and len(ping_res) > 0)
            except Exception:
                celery_active = False

            if celery_active:
                process_transcript_embeddings.delay(out_transcript_id)
                logger.info(f"Queued embedding task for transcript_id={out_transcript_id}")
            else:
                await _async_process_transcript_embeddings(out_transcript_id)
                logger.info(f"Triggered in-process embedding task for transcript_id={out_transcript_id}")
        except Exception as emb_queue_err:
            logger.warning(f"Failed to process embedding task for transcript {out_transcript_id}: {emb_queue_err}.")

        # Auto-trigger AI meeting intelligence processing outside the active DB session
        try:
            from app.workers.celery_app import celery_app
            from app.workers.tasks.intelligence_tasks import process_meeting_intelligence, _async_process_meeting_intelligence
            celery_active = False
            try:
                inspector = celery_app.control.inspect(timeout=0.2)
                ping_res = inspector.ping() if inspector else None
                celery_active = bool(ping_res and len(ping_res) > 0)
            except Exception:
                celery_active = False

            if celery_active:
                process_meeting_intelligence.delay(out_meeting_id)
                logger.info(f"Queued AI meeting intelligence task for meeting_id={out_meeting_id}")
            else:
                await _async_process_meeting_intelligence(out_meeting_id)
                logger.info(f"Triggered in-process AI meeting intelligence for meeting_id={out_meeting_id}")
        except Exception as intel_queue_err:
            logger.warning(f"Failed to auto-trigger AI intelligence for meeting {out_meeting_id}: {intel_queue_err}.")

        return {
            "status": "completed",
            "recording_id": out_recording_id,
            "transcript_id": out_transcript_id,
            "duration_seconds": out_duration,
            "segments_count": out_segments_count,
        }

    except (TranscriptionTransientError, Exception) as exc:
        safe_reason = _sanitize_error_message(exc)
        logger.exception(f"[transcription failed] recording_id={recording_id_str}: {safe_reason}")

        # Mark FAILED in database if permanent error or unexpected exception
        is_transient = isinstance(exc, TranscriptionTransientError)

        try:
            async with AsyncSessionLocal() as failure_session:
                rec_res = await failure_session.execute(
                    select(MeetingRecording).where(MeetingRecording.id == recording_id)
                )
                rec = rec_res.scalar_one_or_none()
                if rec and not is_transient:
                    rec.status = RecordingStatus.FAILED
                    rec.error_message = safe_reason

                    m_res = await failure_session.execute(
                        select(Meeting).where(Meeting.id == rec.meeting_id)
                    )
                    meeting = m_res.scalar_one_or_none()
                    if meeting:
                        meeting.status = MeetingStatus.FAILED

                t_res = await failure_session.execute(
                    select(Transcript).where(Transcript.recording_id == recording_id)
                )
                tr = t_res.scalar_one_or_none()
                if tr and not is_transient:
                    tr.status = TranscriptStatus.FAILED
                    tr.error_message = safe_reason
                    tr.full_text = None
                    tr.word_count = 0
                    await failure_session.execute(
                        delete(TranscriptSegment).where(TranscriptSegment.transcript_id == tr.id)
                    )

                await failure_session.commit()
        except Exception as db_err:
            logger.error(f"Failed to record failure state in database: {db_err}")

        # Re-raise so Celery task wrapper can manage retries
        raise exc

    finally:
        # Guaranteed temporary file cleanup
        if temp_wav_path and temp_wav_path != file_path and os.path.exists(temp_wav_path):
            try:
                os.remove(temp_wav_path)
            except OSError as cleanup_err:
                logger.warning(f"Failed to delete temp WAV file {temp_wav_path}: {cleanup_err}")

        # Release distributed lock
        if lock_acquired and redis_client:
            try:
                redis_client.delete(lock_key)
            except Exception:
                pass

        import sys
        if "pytest" not in sys.modules and not os.getenv("TESTING") and os.getenv("CELERY_WORKER"):
            try:
                await engine.dispose()
            except Exception:
                pass


@celery_app.task(
    bind=True,
    name="app.workers.tasks.recording_tasks.process_meeting_recording",
    max_retries=3,
)
def process_meeting_recording(self, recording_id: str) -> Dict[str, Any]:
    """Celery task to validate, extract audio, transcribe, and persist meeting recording."""
    logger.info(
        f"Starting Celery task for recording {recording_id} (attempt {self.request.retries + 1})"
    )
    try:
        return asyncio.run(_async_process_recording(recording_id))
    except TranscriptionTransientError as trans_exc:
        # Calculate exponential backoff: 5s, 10s, 20s
        countdown = 5 * (2 ** self.request.retries)
        logger.warning(
            f"Transient failure for recording {recording_id}: {trans_exc}. "
            f"Retrying in {countdown}s (retry {self.request.retries + 1}/{self.max_retries})..."
        )
        try:
            self.retry(exc=trans_exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for recording {recording_id}.")
            _record_final_failure(recording_id, f"Max retries exceeded: {trans_exc}")
            raise
    except Exception as exc:
        logger.error(f"Permanent or unhandled failure for recording {recording_id}: {exc}")
        _record_final_failure(recording_id, _sanitize_error_message(exc))
        raise


def _record_final_failure(recording_id_str: str, message: str) -> None:
    """Synchronous helper to mark final FAILED status in PostgreSQL."""
    try:
        rec_uuid = uuid.UUID(recording_id_str)
    except Exception:
        return

    async def _async_mark():
        async with AsyncSessionLocal() as session:
            rec = (
                await session.execute(
                    select(MeetingRecording).where(MeetingRecording.id == rec_uuid)
                )
            ).scalar_one_or_none()
            if rec:
                rec.status = RecordingStatus.FAILED
                rec.error_message = message[:500]

                m_res = await session.execute(
                    select(Meeting).where(Meeting.id == rec.meeting_id)
                )
                meeting = m_res.scalar_one_or_none()
                if meeting:
                    meeting.status = MeetingStatus.FAILED

            tr = (
                await session.execute(
                    select(Transcript).where(Transcript.recording_id == rec_uuid)
                )
            ).scalar_one_or_none()
            if tr:
                tr.status = TranscriptStatus.FAILED
                tr.error_message = message[:500]
                tr.full_text = None
                tr.word_count = 0
                await session.execute(
                    delete(TranscriptSegment).where(TranscriptSegment.transcript_id == tr.id)
                )

            try:
                await session.commit()
            finally:
                import sys
                if "pytest" not in sys.modules and not os.getenv("TESTING") and os.getenv("CELERY_WORKER"):
                    try:
                        await engine.dispose()
                    except Exception:
                        pass

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, _async_mark()).result()
        else:
            asyncio.run(_async_mark())
    except Exception as exc:
        logger.error(f"Failed to record final failure: {exc}")
