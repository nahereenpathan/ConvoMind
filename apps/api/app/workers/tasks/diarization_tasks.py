"""Celery task pipeline for asynchronous speaker diarization."""

import asyncio
import logging
import os
import tempfile
import uuid
from typing import Any, Dict, Optional

from celery.exceptions import MaxRetriesExceededError
import redis
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.recording import MeetingRecording
from app.models.transcript import Transcript
from app.services.diarization import DiarizationPermanentError, DiarizationTransientError
from app.services.diarization_service import DiarizationService
from app.services.ffmpeg_service import get_ffmpeg_service
from app.services.storage_service import get_storage_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _sanitize_error_message(exc: Exception) -> str:
    """Format safe error message for logging."""
    raw = str(exc).strip()
    for secret_key in ("sk-", "Bearer", "token", "password"):
        if secret_key.lower() in raw.lower():
            return f"{type(exc).__name__}: An error occurred during diarization execution."
    return f"{type(exc).__name__}: {raw[:250]}"


async def _async_process_speaker_diarization(recording_id_str: str) -> Dict[str, Any]:
    """Execute asynchronous audio preparation, speaker diarization, and alignment persistence."""
    try:
        recording_id = uuid.UUID(recording_id_str)
    except (ValueError, TypeError) as exc:
        logger.error(f"Invalid recording UUID passed to diarization worker: {recording_id_str} ({exc})")
        return {"status": "invalid_id", "recording_id": recording_id_str}

    storage_service = get_storage_service()
    ffmpeg_service = get_ffmpeg_service()

    redis_client = None
    lock_acquired = False
    lock_key = f"lock:diarization:{recording_id_str}"

    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        lock_acquired = bool(redis_client.set(lock_key, "locked", nx=True, ex=600))
        if not lock_acquired:
            logger.warning(f"Diarization for recording {recording_id_str} is already active on another worker.")
            return {"status": "already_running", "recording_id": recording_id_str}
    except Exception as lock_err:
        logger.warning(f"Could not verify Redis lock: {lock_err}. Proceeding with diarization pipeline.")

    temp_wav_path: Optional[str] = None

    try:
        async with AsyncSessionLocal() as session:
            # 1. Fetch recording
            rec_stmt = select(MeetingRecording).where(MeetingRecording.id == recording_id)
            recording = (await session.execute(rec_stmt)).scalar_one_or_none()

            if not recording:
                logger.warning(f"Recording {recording_id} not found in database.")
                return {"status": "not_found", "recording_id": str(recording_id)}

            # 2. Check media storage availability
            file_path = storage_service.get_file_path(recording.storage_key)
            if not storage_service.file_exists(recording.storage_key):
                raise DiarizationPermanentError(
                    f"Recording audio file missing from storage key: {recording.storage_key}"
                )

            # 3. Extract normalized WAV audio (16kHz mono)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            logger.info(f"[ffmpeg diarization] extracting WAV audio to {temp_wav_path}")
            conversion_ok = ffmpeg_service.extract_audio_for_stt(
                input_path=file_path,
                output_path=temp_wav_path,
                sample_rate=16000,
                channels=1,
            )
            if not conversion_ok:
                raise DiarizationPermanentError("FFmpeg failed to extract WAV audio for diarization.")

            # 4. Execute Diarization Service pipeline
            result_metrics = await DiarizationService.process_diarization(
                db=session,
                meeting_id=recording.meeting_id,
                audio_path=temp_wav_path,
            )

            # 5. Fetch completed transcript and trigger re-embedding task
            tr_stmt = select(Transcript).where(Transcript.recording_id == recording.id)
            transcript = (await session.execute(tr_stmt)).scalar_one_or_none()

            if transcript:
                try:
                    from app.workers.tasks.embedding_tasks import process_transcript_embeddings
                    process_transcript_embeddings.delay(str(transcript.id))
                    logger.info(f"Triggered re-embedding task for transcript {transcript.id} after diarization.")
                except Exception as emb_err:
                    logger.warning(f"Failed to queue re-embedding task for transcript {transcript.id}: {emb_err}")

            return {
                "status": "completed",
                "recording_id": str(recording.id),
                "meeting_id": str(recording.meeting_id),
                "speakers_count": result_metrics.get("speakers_count", 0),
                "segments_aligned": result_metrics.get("segments_aligned", 0),
            }

    except (DiarizationTransientError, Exception) as exc:
        safe_msg = _sanitize_error_message(exc)
        logger.exception(f"[diarization failed] recording_id={recording_id_str}: {safe_msg}")
        raise exc

    finally:
        # Guaranteed temporary file cleanup
        if temp_wav_path and os.path.exists(temp_wav_path):
            try:
                os.remove(temp_wav_path)
            except OSError as cleanup_err:
                logger.warning(f"Failed to remove temp WAV file {temp_wav_path}: {cleanup_err}")

        # Release distributed lock
        if lock_acquired and redis_client:
            try:
                redis_client.delete(lock_key)
            except Exception:
                pass

        try:
            await engine.dispose()
        except Exception:
            pass


@celery_app.task(
    bind=True,
    name="app.workers.tasks.diarization_tasks.process_speaker_diarization",
    max_retries=3,
)
def process_speaker_diarization(self, recording_id: str) -> Dict[str, Any]:
    """Celery task wrapper to process speaker diarization asynchronously."""
    logger.info(
        f"Starting Celery diarization task for recording {recording_id} (attempt {self.request.retries + 1})"
    )
    try:
        return asyncio.run(_async_process_speaker_diarization(recording_id))
    except DiarizationTransientError as trans_exc:
        countdown = 5 * (2 ** self.request.retries)
        logger.warning(
            f"Transient failure for recording {recording_id}: {trans_exc}. "
            f"Retrying in {countdown}s (attempt {self.request.retries + 1}/{self.max_retries})..."
        )
        try:
            self.retry(exc=trans_exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for diarization of recording {recording_id}.")
            raise
    except Exception as exc:
        logger.error(f"Permanent or unhandled failure for diarization of recording {recording_id}: {exc}")
        raise
