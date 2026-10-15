"""Celery task pipeline for asynchronous AI meeting intelligence extraction."""

import asyncio
import os
from datetime import datetime, timezone, timedelta
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
import redis
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import delete, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.enums import (
    ActionItemStatus,
    IntelligenceStatus,
    NotificationType,
    PriorityLevel,
    QuestionStatus,
    TranscriptStatus,
)
from app.models.intelligence import (
    ActionItem,
    Decision,
    MeetingIntelligenceJob,
    MeetingQuestion,
    MeetingSummary,
)
from app.models.meeting import Meeting, MeetingParticipant, Speaker
from app.models.transcript import Transcript, TranscriptSegment
from app.services.intelligence.base import (
    LLMPermanentError,
    LLMTransientError,
)
from app.services.intelligence.factory import get_llm_provider
from app.services.intelligence.schemas import MeetingIntelligenceOutput
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _sanitize_error_message(exc: Exception) -> str:
    """Format safe error summary for database recording."""
    raw = str(exc).strip()
    return raw[:500] if raw else exc.__class__.__name__


def _find_matching_segment_id(
    timestamp_marker: Optional[float],
    segments: List[TranscriptSegment],
) -> Optional[uuid.UUID]:
    """Find the transcript segment UUID encompassing or closest to timestamp_marker."""
    if timestamp_marker is None or not segments:
        return None

    # First attempt: find segment bounding the timestamp
    for seg in segments:
        if seg.start_time <= timestamp_marker <= (seg.end_time + 1.0):
            return seg.id

    # Fallback: nearest segment by absolute start_time difference within 10s
    nearest = min(segments, key=lambda s: abs(s.start_time - timestamp_marker))
    if abs(nearest.start_time - timestamp_marker) <= 10.0:
        return nearest.id

    return None


def parse_due_date_to_datetime(
    due_date_str: Optional[str],
    base_dt: Optional[datetime] = None,
) -> Optional[datetime]:
    """Parse natural language or ISO date string into a timezone-aware datetime."""
    if not due_date_str or not due_date_str.strip():
        return None
    cleaned = due_date_str.strip()
    now = base_dt or datetime.now(timezone.utc)
    c_lower = cleaned.lower()

    try:
        from dateutil import parser
        default_dt = datetime(now.year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        parsed = parser.parse(cleaned, default=default_dt)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        pass

    if "tomorrow" in c_lower:
        return (now + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)

    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, d in enumerate(days):
        if d in c_lower:
            days_ahead = (i - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (now + timedelta(days=days_ahead)).replace(hour=17, minute=0, second=0, microsecond=0)

    return None


async def _async_process_meeting_intelligence(
    meeting_id_str: str,
    job_id_str: Optional[str] = None,
) -> Dict[str, Any]:
    """Asynchronously execute LLM extraction and persist structured meeting intelligence."""
    try:
        meeting_id = uuid.UUID(meeting_id_str)
        job_id = uuid.UUID(job_id_str) if job_id_str else None
    except (ValueError, TypeError) as exc:
        logger.error(f"Invalid UUID passed to intelligence worker: {meeting_id_str} ({exc})")
        return {"status": "invalid_id", "meeting_id": meeting_id_str}

    # Distributed locking via Redis
    redis_client = None
    lock_acquired = False
    lock_key = f"lock:intelligence:{meeting_id_str}"

    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        if not job_id:
            lock_acquired = bool(redis_client.set(lock_key, "locked", nx=True, ex=30))
            if not lock_acquired:
                logger.warning(
                    f"Intelligence processing for meeting {meeting_id_str} is already active on another worker."
                )
                return {"status": "already_running", "meeting_id": meeting_id_str}
        else:
            redis_client.set(lock_key, "locked", ex=30)
    except Exception as lock_err:
        logger.warning(f"Could not verify Redis lock: {lock_err}. Proceeding with pipeline.")

    start_time = time.time()

    try:
        async with AsyncSessionLocal() as session:
            # 1. Fetch meeting
            m_stmt = (
                select(Meeting)
                .options(
                    selectinload(Meeting.participants),
                    selectinload(Meeting.speakers),
                )
                .where(Meeting.id == meeting_id)
            )
            meeting = (await session.execute(m_stmt)).scalar_one_or_none()
            if not meeting:
                logger.error(f"Meeting {meeting_id} not found in database.")
                return {"status": "not_found", "meeting_id": meeting_id_str}

            # 2. Fetch or create intelligence job
            job = None
            if job_id:
                j_stmt = select(MeetingIntelligenceJob).where(MeetingIntelligenceJob.id == job_id)
                job = (await session.execute(j_stmt)).scalar_one_or_none()

            if not job:
                # Calculate next version
                count_stmt = select(MeetingIntelligenceJob.version).where(
                    MeetingIntelligenceJob.meeting_id == meeting.id
                ).order_by(MeetingIntelligenceJob.version.desc())
                highest_version = (await session.execute(count_stmt)).scalars().first() or 0
                next_version = highest_version + 1

                job = MeetingIntelligenceJob(
                    meeting_id=meeting.id,
                    workspace_id=meeting.workspace_id,
                    status=IntelligenceStatus.QUEUED,
                    provider=settings.LLM_PROVIDER,
                    model=settings.OPENAI_MODEL if settings.LLM_PROVIDER == "openai" else "mock-gpt-4o",
                    prompt_version="v1",
                    version=next_version,
                )
                session.add(job)
                await session.flush()

            # Transition job to PROCESSING
            job.status = IntelligenceStatus.PROCESSING
            job.started_at = job.started_at or datetime.now(timezone.utc)
            await session.commit()

            # 3. Retrieve latest COMPLETED transcript
            t_stmt = (
                select(Transcript)
                .where(
                    Transcript.meeting_id == meeting.id,
                    Transcript.status == TranscriptStatus.COMPLETED,
                )
                .order_by(Transcript.updated_at.desc())
            )
            transcript = (await session.execute(t_stmt)).scalars().first()
            if not transcript:
                t_stmt_any = (
                    select(Transcript)
                    .where(Transcript.meeting_id == meeting.id)
                    .order_by(Transcript.updated_at.desc())
                )
                transcript = (await session.execute(t_stmt_any)).scalars().first()

            if not transcript or transcript.status != TranscriptStatus.COMPLETED or not transcript.full_text or not transcript.full_text.strip():
                err_msg = "Meeting transcript does not exist, is empty, or has not reached COMPLETED status."
                logger.warning(f"Meeting {meeting_id} cannot run AI intelligence: {err_msg}")
                job.status = IntelligenceStatus.FAILED
                job.error_message = err_msg
                await session.commit()
                return {"status": "failed", "error": err_msg}

            # 4. Load transcript segments
            seg_stmt = (
                select(TranscriptSegment)
                .options(selectinload(TranscriptSegment.speaker))
                .where(TranscriptSegment.transcript_id == transcript.id)
                .order_by(TranscriptSegment.sequence_order.asc())
            )
            segments = list((await session.execute(seg_stmt)).scalars().all())

            segment_dicts = [
                {
                    "id": str(s.id),
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "text": s.text,
                    "speaker_name": s.speaker.name if s.speaker else None,
                    "speaker_label": s.speaker.label if s.speaker else None,
                }
                for s in segments
            ]

            full_text = transcript.full_text or " ".join(s.text for s in segments)

            # Safe diagnostic logging (No sensitive transcript logging)
            logger.info(
                f"Executing LLM intelligence extraction for meeting={meeting.id} workspace={meeting.workspace_id} "
                f"transcript={transcript.id} segments={len(segments)} chars={len(full_text)} job={job.id}"
            )

            # 5. Invoke LLM provider with explicit timeout
            provider = get_llm_provider()
            timeout_sec = float(getattr(settings, "LLM_TIMEOUT_SECONDS", 60.0) or 60.0)
            try:
                output: MeetingIntelligenceOutput = await asyncio.wait_for(
                    provider.generate_meeting_intelligence(
                        transcript_text=full_text,
                        segments=segment_dicts,
                    ),
                    timeout=timeout_sec,
                )
            except asyncio.TimeoutError:
                raise LLMTransientError(f"LLM provider request timed out after {timeout_sec}s.")

            # Concurrency & Stale Job Guard: Ensure a newer completed processing run has not superseded this job
            newer_completed_job = (
                await session.execute(
                    select(MeetingIntelligenceJob).where(
                        MeetingIntelligenceJob.meeting_id == meeting.id,
                        MeetingIntelligenceJob.version > job.version,
                        MeetingIntelligenceJob.status == IntelligenceStatus.COMPLETED,
                    )
                )
            ).scalars().first()

            if newer_completed_job:
                logger.warning(
                    f"Job {job.id} (v{job.version}) for meeting {meeting.id} was superseded by completed job "
                    f"{newer_completed_job.id} (v{newer_completed_job.version}). Aborting overwrite."
                )
                job.status = IntelligenceStatus.COMPLETED
                job.error_message = f"Superseded by newer intelligence version {newer_completed_job.version}."
                await session.commit()
                return {
                    "status": "superseded",
                    "meeting_id": str(meeting_id),
                    "version": job.version,
                    "superseded_by": newer_completed_job.version,
                }

            # 6. Purge prior analysis records for this meeting to prevent stale/mock data retention
            # Note: Preserve manually created user tasks (where created_by_id is set and job_id is None)
            await session.execute(delete(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id))
            await session.execute(delete(Decision).where(Decision.meeting_id == meeting.id))
            await session.execute(
                delete(ActionItem).where(
                    ActionItem.meeting_id == meeting.id,
                    or_(ActionItem.job_id.is_not(None), ActionItem.created_by_id.is_(None)),
                )
            )
            await session.execute(delete(MeetingQuestion).where(MeetingQuestion.meeting_id == meeting.id))

            # 7. Persist fresh structured intelligence
            current_version = job.version

            # Meeting Summary
            summary = MeetingSummary(
                meeting_id=meeting.id,
                workspace_id=meeting.workspace_id,
                overview=output.executive_summary,
                detailed_summary=output.detailed_summary,
                key_points=[{"point": p} for p in output.key_points],
                next_steps=[{"step": s} for s in output.follow_up_suggestions],
                risks_and_concerns=[{"risk": r} for r in output.risks_and_concerns],
                requirements_and_notes=[{"note": n} for n in output.requirements_and_notes],
                follow_up_suggestions=[{"suggestion": s} for s in output.follow_up_suggestions],
                model_used=output.model_used or job.model,
                provider=output.provider or job.provider,
                prompt_version=job.prompt_version,
                processing_duration=round(time.time() - start_time, 2),
                token_usage=output.token_usage,
                version=current_version,
                job_id=job.id,
            )
            session.add(summary)

            # Decisions
            for d in output.decisions:
                matched_seg_id = _find_matching_segment_id(d.timestamp_marker, segments)
                decision = Decision(
                    workspace_id=meeting.workspace_id,
                    meeting_id=meeting.id,
                    title=d.decision,
                    context=d.context,
                    impact=d.impact,
                    timestamp_marker=d.timestamp_marker,
                    source_segment_id=matched_seg_id,
                    version=current_version,
                    job_id=job.id,
                )
                session.add(decision)

            # Action Items
            for a in output.action_items:
                matched_seg_id = _find_matching_segment_id(a.timestamp_marker, segments)

                # Attempt to match assignee to meeting participant or speaker
                assignee_id = None
                if a.assignee_name:
                    clean_name = a.assignee_name.lower().strip()
                    for p in meeting.participants:
                        if p.name and clean_name in p.name.lower() and p.user_id:
                            assignee_id = p.user_id
                            break
                    if not assignee_id:
                        for spk in meeting.speakers:
                            if spk.name and clean_name in spk.name.lower() and spk.user_id:
                                assignee_id = spk.user_id
                                break

                # Parse priority
                p_level = PriorityLevel.MEDIUM
                if a.priority and a.priority.upper() in PriorityLevel.__members__:
                    p_level = PriorityLevel[a.priority.upper()]

                parsed_due_date = parse_due_date_to_datetime(a.due_date_str)

                action_item = ActionItem(
                    workspace_id=meeting.workspace_id,
                    meeting_id=meeting.id,
                    assignee_id=assignee_id,
                    assignee_name=a.assignee_name,
                    title=a.task,
                    description=a.description,
                    due_date=parsed_due_date,
                    priority=p_level,
                    timestamp_marker=a.timestamp_marker,
                    source_segment_id=matched_seg_id,
                    version=current_version,
                    job_id=job.id,
                )
                session.add(action_item)

            # Questions
            for q in output.questions:
                matched_seg_id = _find_matching_segment_id(q.timestamp_marker, segments)

                # Attempt to match speaker
                spk_id = None
                if q.asked_by:
                    clean_spk = q.asked_by.lower().strip()
                    for spk in meeting.speakers:
                        if (spk.name and clean_spk in spk.name.lower()) or (clean_spk in spk.label.lower()):
                            spk_id = spk.id
                            break

                q_status = QuestionStatus.ANSWERED if q.is_resolved else QuestionStatus.OPEN
                question_record = MeetingQuestion(
                    workspace_id=meeting.workspace_id,
                    meeting_id=meeting.id,
                    asked_by_speaker_id=spk_id,
                    asked_by_speaker_name=q.asked_by,
                    question=q.question,
                    answer=q.answer,
                    status=q_status,
                    is_resolved=q.is_resolved,
                    timestamp_marker=q.timestamp_marker,
                    source_segment_id=matched_seg_id,
                    version=current_version,
                    job_id=job.id,
                )
                session.add(question_record)

            # Update job to COMPLETED
            duration_s = round(time.time() - start_time, 2)
            job.status = IntelligenceStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.processing_duration = duration_s
            job.token_usage = output.token_usage
            job.provider = output.provider or job.provider
            job.model = output.model_used or job.model
            job.error_message = None

            await session.commit()

            # Trigger notification event for meeting creator
            if meeting.creator_id:
                try:
                    from app.services.notifications.notification_service import NotificationService
                    await NotificationService.create_and_dispatch_notification(
                        db=session,
                        user_id=meeting.creator_id,
                        workspace_id=meeting.workspace_id,
                        type=NotificationType.AI_ANALYSIS_COMPLETED,
                        title="AI Meeting Analysis Complete",
                        message=f"AI Intelligence analysis for '{meeting.title}' has completed successfully.",
                        entity_type="meeting",
                        entity_id=meeting.id,
                    )
                except Exception as notif_err:
                    logger.warning(f"Failed to send notification on AI completion for meeting {meeting.id}: {notif_err}")

            # Enqueue Post-Meeting Summary and Action Item Emails
            try:
                from app.services.email.dispatch import EmailDispatchService
                for p in meeting.participants:
                    if p.email:
                        await EmailDispatchService.enqueue_email(
                            db=session,
                            recipient_email=p.email,
                            recipient_name=p.name or p.email,
                            event_type="post_meeting_summary",
                            template_data={
                                "meeting_id": str(meeting.id),
                                "meeting_title": meeting.title,
                                "summary": output.executive_summary,
                                "decisions": [d.decision for d in output.decisions[:5]],
                            },
                            user_id=p.user_id,
                            workspace_id=meeting.workspace_id,
                            meeting_id=meeting.id,
                            idempotency_key=f"summary:{meeting.id}:{p.email}:{current_version}",
                            check_preference=True,
                        )

                for a in output.action_items:
                    assignee_user_id = None
                    assignee_email = None
                    if a.assignee_name:
                        for p in meeting.participants:
                            if p.name and a.assignee_name.lower() in p.name.lower():
                                assignee_user_id = p.user_id
                                assignee_email = p.email
                                break
                    if assignee_email:
                        await EmailDispatchService.enqueue_email(
                            db=session,
                            recipient_email=assignee_email,
                            recipient_name=a.assignee_name,
                            event_type="action_item_assigned",
                            template_data={
                                "meeting_id": str(meeting.id),
                                "meeting_title": meeting.title,
                                "task_description": a.task,
                                "assignee_name": a.assignee_name,
                                "due_date": getattr(a, "due_date", "") or "",
                            },
                            user_id=assignee_user_id,
                            workspace_id=meeting.workspace_id,
                            meeting_id=meeting.id,
                            idempotency_key=f"action_item:{meeting.id}:{assignee_email}:{a.task[:30]}",
                            check_preference=True,
                        )
            except Exception as email_err:
                logger.warning(f"Failed to enqueue post-meeting summary/action item emails: {email_err}")

            logger.info(
                f"Successfully extracted AI meeting intelligence for meeting {meeting_id} "
                f"(version: {current_version}, duration: {duration_s}s, tokens: {output.token_usage})"
            )

            return {
                "status": "completed",
                "meeting_id": str(meeting_id),
                "job_id": str(job.id),
                "version": current_version,
                "duration_seconds": duration_s,
                "action_items_count": len(output.action_items),
                "decisions_count": len(output.decisions),
                "questions_count": len(output.questions),
            }

    except Exception as exc:
        logger.error(f"Intelligence processing failed for meeting {meeting_id_str}: {exc}")
        # Mark job FAILED
        try:
            async with AsyncSessionLocal() as err_session:
                if job_id:
                    j_err = (
                        await err_session.execute(
                            select(MeetingIntelligenceJob).where(MeetingIntelligenceJob.id == job_id)
                        )
                    ).scalar_one_or_none()
                    if j_err:
                        j_err.status = IntelligenceStatus.FAILED
                        j_err.completed_at = datetime.now(timezone.utc)
                        j_err.error_message = _sanitize_error_message(exc)
                        await err_session.commit()
        except Exception as db_err:
            logger.error(f"Failed to record FAILED status on intelligence job: {db_err}")

        raise exc

    finally:
        # Release distributed lock
        if lock_acquired and redis_client:
            try:
                redis_client.delete(lock_key)
            except Exception:
                pass

        # Clean asyncpg connection pool for this event loop (non-testing)
        import sys
        if "pytest" not in sys.modules and not os.getenv("TESTING") and os.getenv("CELERY_WORKER"):
            try:
                await engine.dispose()
            except Exception:
                pass


import concurrent.futures


def _run_sync_coro(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()
    else:
        return asyncio.run(coro)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.intelligence_tasks.process_meeting_intelligence",
    max_retries=3,
)
def process_meeting_intelligence(
    self,
    meeting_id: str,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Celery task executing AI meeting intelligence extraction with backoff retry."""
    logger.info(
        f"Starting AI meeting intelligence Celery task for meeting {meeting_id} "
        f"(attempt {self.request.retries + 1})"
    )
    try:
        return _run_sync_coro(_async_process_meeting_intelligence(meeting_id, job_id))
    except LLMTransientError as trans_exc:
        countdown = 5 * (2 ** self.request.retries)
        logger.warning(
            f"Transient LLM failure for meeting {meeting_id}: {trans_exc}. "
            f"Retrying in {countdown}s (retry {self.request.retries + 1}/{self.max_retries})..."
        )
        try:
            self.retry(exc=trans_exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for AI intelligence on meeting {meeting_id}.")
            raise
    except Exception as exc:
        logger.error(
            f"Permanent or unhandled failure in AI intelligence for meeting {meeting_id}: {exc}"
        )
        raise
