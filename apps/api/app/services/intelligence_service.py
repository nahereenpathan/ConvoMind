"""Meeting intelligence domain service handling AI analysis triggers, job tracking, RBAC, and intelligence queries."""

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select, or_, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import ActionItemStatus, IntelligenceStatus, PriorityLevel, TranscriptStatus, WorkspaceRole
from app.models.intelligence import (
    ActionItem,
    Decision,
    MeetingIntelligenceJob,
    MeetingQuestion,
    MeetingSummary,
)
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.intelligence import (
    ActionItemCreate,
    ActionItemUpdate,
    ActionItemResponse,
    DecisionResponse,
    IntelligenceJobResponse,
    MeetingIntelligenceResponse,
    MeetingQuestionResponse,
    MeetingSummaryResponse,
)

logger = logging.getLogger(__name__)


class IntelligenceService:
    """Service handling meeting intelligence trigger, status, and entity queries."""

    @staticmethod
    async def _verify_meeting_access(
        db: AsyncSession,
        meeting_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Tuple[Meeting, WorkspaceMember]:
        """Verify user is a member of the workspace that owns the meeting."""
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
    async def trigger_intelligence_processing(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
    ) -> MeetingIntelligenceJob:
        """Queue asynchronous AI intelligence processing for a meeting with a completed transcript."""
        meeting, member = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests are not permitted to trigger AI intelligence processing.",
            )

        # Verify transcript status & text validity
        stmt = (
            select(Transcript)
            .where(Transcript.meeting_id == meeting.id)
            .order_by(Transcript.created_at.desc())
        )
        trans_res = await db.execute(stmt)
        transcript = trans_res.scalars().first()

        if not transcript or transcript.status != TranscriptStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Meeting must have a completed transcript before triggering intelligence analysis.",
            )

        if not transcript.full_text or not transcript.full_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transcript has no usable speech content to analyze.",
            )

        # Check if an intelligence job is currently queued or processing
        active_stmt = select(MeetingIntelligenceJob).where(
            MeetingIntelligenceJob.meeting_id == meeting.id,
            MeetingIntelligenceJob.status.in_(
                [IntelligenceStatus.QUEUED, IntelligenceStatus.PROCESSING]
            ),
        )
        active_res = await db.execute(active_stmt)
        active_job = active_res.scalars().first()
        if active_job:
            now = datetime.now(timezone.utc)
            created_at = active_job.created_at.replace(tzinfo=timezone.utc) if active_job.created_at and active_job.created_at.tzinfo is None else active_job.created_at
            job_age = (now - created_at).total_seconds() if created_at else 0
            if job_age > 60:
                logger.warning(f"Marking stale intelligence job {active_job.id} (age {job_age}s) as FAILED.")
                active_job.status = IntelligenceStatus.FAILED
                active_job.completed_at = now
                active_job.error_message = "Job timed out or was superseded."
                await db.commit()
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="AI intelligence processing is already in progress for this meeting.",
                )

        # Determine next version
        ver_stmt = select(func.coalesce(func.max(MeetingIntelligenceJob.version), 0)).where(
            MeetingIntelligenceJob.meeting_id == meeting.id
        )
        ver_res = await db.execute(ver_stmt)
        latest_version = ver_res.scalar_one()
        next_version = latest_version + 1

        # Model resolution based on provider
        provider = settings.LLM_PROVIDER.lower()
        if provider == "openai":
            model = settings.OPENAI_MODEL
        elif provider == "gemini":
            model = settings.GEMINI_MODEL
        else:
            model = "mock-gpt-4o"

        # Create intelligence job
        job = MeetingIntelligenceJob(
            meeting_id=meeting.id,
            workspace_id=meeting.workspace_id,
            status=IntelligenceStatus.QUEUED,
            provider=provider,
            model=model,
            prompt_version="v1",
            version=next_version,
        )
        db.add(job)
        await db.commit()
        # Dispatch processing task to active Celery worker or in-process asyncio fallback
        if os.getenv("TESTING"):
            try:
                from app.workers.tasks.intelligence_tasks import process_meeting_intelligence
                process_meeting_intelligence.delay(str(meeting.id), str(job.id))
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
                    from app.workers.tasks.intelligence_tasks import process_meeting_intelligence
                    process_meeting_intelligence.delay(str(meeting.id), str(job.id))
                    logger.info(f"Queued intelligence processing for meeting {meeting.id}, job {job.id} via Celery.")
                else:
                    import asyncio
                    from app.workers.tasks.intelligence_tasks import _async_process_meeting_intelligence
                    asyncio.create_task(_async_process_meeting_intelligence(str(meeting.id), str(job.id)))
            except Exception as celery_err:
                logger.debug(f"Celery enqueue skipped/failed: {celery_err}")
                import asyncio
                from app.workers.tasks.intelligence_tasks import _async_process_meeting_intelligence
                asyncio.create_task(_async_process_meeting_intelligence(str(meeting.id), str(job.id)))

        return job
    @classmethod
    async def get_intelligence_job_status(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        job_id: Optional[uuid.UUID] = None,
    ) -> MeetingIntelligenceJob:
        """Retrieve status of a specific or latest intelligence job for a meeting."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        query = select(MeetingIntelligenceJob).where(
            MeetingIntelligenceJob.meeting_id == meeting.id
        )
        if job_id:
            query = query.where(MeetingIntelligenceJob.id == job_id)
        else:
            query = query.order_by(MeetingIntelligenceJob.created_at.desc())

        res = await db.execute(query)
        job = res.scalars().first()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intelligence job not found for this meeting.",
            )
        return job

    @classmethod
    async def get_latest_version(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
    ) -> Optional[int]:
        """Helper to get latest intelligence version for a meeting."""
        stmt = (
            select(MeetingIntelligenceJob.version)
            .where(
                MeetingIntelligenceJob.meeting_id == meeting_id,
                MeetingIntelligenceJob.status == IntelligenceStatus.COMPLETED,
            )
            .order_by(MeetingIntelligenceJob.version.desc())
        )
        res = await db.execute(stmt)
        return res.scalars().first()

    @classmethod
    async def get_meeting_intelligence(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        version: Optional[int] = None,
    ) -> MeetingIntelligenceResponse:
        """Fetch consolidated meeting intelligence (summary, decisions, action items, questions)."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        job_query = select(MeetingIntelligenceJob).where(
            MeetingIntelligenceJob.meeting_id == meeting.id
        )
        if version:
            job_query = job_query.where(MeetingIntelligenceJob.version == version)
        else:
            job_query = job_query.where(
                MeetingIntelligenceJob.status == IntelligenceStatus.COMPLETED
            ).order_by(MeetingIntelligenceJob.version.desc())

        job_res = await db.execute(job_query)
        job = job_res.scalars().first()

        # Fallback to latest job if no COMPLETED job found yet
        if not job and not version:
            fb_query = (
                select(MeetingIntelligenceJob)
                .where(MeetingIntelligenceJob.meeting_id == meeting.id)
                .order_by(MeetingIntelligenceJob.version.desc())
            )
            job = (await db.execute(fb_query)).scalars().first()

        # If no COMPLETED job exists yet, check if meeting has a COMPLETED transcript and auto-generate inline
        if not job or job.status != IntelligenceStatus.COMPLETED:
            from app.models.transcript import Transcript, TranscriptStatus
            t_stmt = select(Transcript).where(
                Transcript.meeting_id == meeting.id,
                Transcript.status == TranscriptStatus.COMPLETED
            )
            t_res = await db.execute(t_stmt)
            t_obj = t_res.scalars().first()
            if t_obj and t_obj.full_text and t_obj.full_text.strip():
                logger.info(f"Auto-generating intelligence inline for meeting {meeting.id} with completed transcript.")
                from app.workers.tasks.intelligence_tasks import _async_process_meeting_intelligence
                await _async_process_meeting_intelligence(str(meeting.id))

                # Re-query for COMPLETED job
                job_res = await db.execute(job_query)
                job = job_res.scalars().first()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No intelligence found for this meeting.",
            )

        target_version = job.version

        # Fetch summary
        sum_stmt = select(MeetingSummary).where(
            MeetingSummary.meeting_id == meeting.id,
            MeetingSummary.version == target_version,
        )
        sum_res = await db.execute(sum_stmt)
        summary = sum_res.scalars().first()

        # Fetch decisions
        dec_stmt = (
            select(Decision)
            .where(
                Decision.meeting_id == meeting.id,
                Decision.version == target_version,
            )
            .order_by(Decision.created_at.asc())
        )
        dec_res = await db.execute(dec_stmt)
        decisions = list(dec_res.scalars().all())

        # Fetch action items
        act_stmt = (
            select(ActionItem)
            .where(
                ActionItem.meeting_id == meeting.id,
                ActionItem.version == target_version,
            )
            .order_by(ActionItem.created_at.asc())
        )
        act_res = await db.execute(act_stmt)
        action_items = list(act_res.scalars().all())

        # Fetch questions
        que_stmt = (
            select(MeetingQuestion)
            .where(
                MeetingQuestion.meeting_id == meeting.id,
                MeetingQuestion.version == target_version,
            )
            .order_by(MeetingQuestion.created_at.asc())
        )
        que_res = await db.execute(que_stmt)
        questions = list(que_res.scalars().all())

        return MeetingIntelligenceResponse(
            meeting_id=meeting.id,
            workspace_id=meeting.workspace_id,
            version=target_version,
            job=IntelligenceJobResponse.model_validate(job),
            summary=MeetingSummaryResponse.model_validate(summary) if summary else None,
            decisions=[DecisionResponse.model_validate(d) for d in decisions],
            action_items=[ActionItemResponse.model_validate(a) for a in action_items],
            questions=[MeetingQuestionResponse.model_validate(q) for q in questions],
        )

    @classmethod
    async def get_summary(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        version: Optional[int] = None,
    ) -> MeetingSummary:
        """Fetch AI executive/detailed summary for a meeting."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        query = select(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id)
        if version:
            query = query.where(MeetingSummary.version == version)
        else:
            query = query.order_by(MeetingSummary.version.desc())

        res = await db.execute(query)
        summary = res.scalars().first()
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting summary not found.",
            )
        return summary

    @classmethod
    async def get_decisions(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        version: Optional[int] = None,
    ) -> List[Decision]:
        """Fetch extracted decisions for a meeting."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        query = select(Decision).where(Decision.meeting_id == meeting.id)
        if version is not None:
            query = query.where(Decision.version == version)
        else:
            latest_v = await cls.get_latest_version(db, meeting.id)
            if latest_v is not None:
                query = query.where(Decision.version == latest_v)

        query = query.order_by(Decision.created_at.asc())
        res = await db.execute(query)
        return list(res.scalars().all())

    @classmethod
    async def get_action_items(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        version: Optional[int] = None,
    ) -> List[ActionItem]:
        """Fetch extracted action items for a meeting."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        query = select(ActionItem).where(ActionItem.meeting_id == meeting.id)
        if version is not None:
            query = query.where(ActionItem.version == version)
        else:
            latest_v = await cls.get_latest_version(db, meeting.id)
            if latest_v is not None:
                query = query.where(ActionItem.version == latest_v)

        query = query.order_by(ActionItem.created_at.asc())
        res = await db.execute(query)
        return list(res.scalars().all())

    @classmethod
    async def get_questions(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        version: Optional[int] = None,
    ) -> List[MeetingQuestion]:
        """Fetch extracted questions for a meeting."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        query = select(MeetingQuestion).where(MeetingQuestion.meeting_id == meeting.id)
        if version is not None:
            query = query.where(MeetingQuestion.version == version)
        else:
            latest_v = await cls.get_latest_version(db, meeting.id)
            if latest_v is not None:
                query = query.where(MeetingQuestion.version == latest_v)

        query = query.order_by(MeetingQuestion.created_at.asc())
        res = await db.execute(query)
        return list(res.scalars().all())

    @classmethod
    async def create_action_item(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        payload: ActionItemCreate,
        current_user: User,
    ) -> ActionItem:
        """Create a new action item under a meeting."""
        meeting, _ = await cls._verify_meeting_access(
            db, meeting_id, current_user.id
        )

        action_item = ActionItem(
            meeting_id=meeting.id,
            workspace_id=meeting.workspace_id,
            title=payload.title,
            description=payload.description,
            assignee_id=payload.assignee_id,
            assignee_name=payload.assignee_name,
            due_date=payload.due_date,
            priority=payload.priority,
            status=payload.status or ActionItemStatus.OPEN,
            timestamp_marker=payload.timestamp_marker,
            source_segment_id=payload.source_segment_id,
            created_by_id=current_user.id,
        )
        db.add(action_item)
        await db.commit()
        await db.refresh(action_item)
        action_item.meeting = meeting
        return action_item

    @classmethod
    async def update_action_item(
        cls,
        db: AsyncSession,
        action_item_id: uuid.UUID,
        payload: ActionItemUpdate,
        current_user: User,
    ) -> ActionItem:
        """Update an existing action item."""
        stmt = (
            select(ActionItem, Meeting, WorkspaceMember)
            .join(Meeting, Meeting.id == ActionItem.meeting_id)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Meeting.workspace_id)
            .where(
                ActionItem.id == action_item_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Action item not found.",
            )

        action_item = row[0]
        update_data = payload.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(action_item, field, value)

        if payload.status == ActionItemStatus.COMPLETED and not action_item.completed_at:
            action_item.completed_at = datetime.now(timezone.utc)
        elif payload.status and payload.status != ActionItemStatus.COMPLETED:
            action_item.completed_at = None

        action_item.updated_by_id = current_user.id
        await db.commit()
        await db.refresh(action_item)
        action_item.meeting = row[1]
        return action_item

    @classmethod
    async def delete_action_item(
        cls,
        db: AsyncSession,
        action_item_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """Delete an action item."""
        stmt = (
            select(ActionItem, Meeting, WorkspaceMember)
            .join(Meeting, Meeting.id == ActionItem.meeting_id)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Meeting.workspace_id)
            .where(
                ActionItem.id == action_item_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Action item not found.",
            )

        action_item = row[0]
        await db.delete(action_item)
        await db.commit()

    @classmethod
    async def get_workspace_action_items(
        cls,
        db: AsyncSession,
        workspace_id: uuid.UUID,
        current_user: User,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        assignee_id: Optional[uuid.UUID] = None,
        assignee_name: Optional[str] = None,
        priority_filter: Optional[str] = None,
        meeting_id: Optional[uuid.UUID] = None,
        due_date_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "due_date",
        sort_order: str = "asc",
    ) -> Tuple[List[ActionItem], int]:
        """Fetch workspace action items with filtering, search, sorting, and pagination."""
        wm_stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
        wm_res = await db.execute(wm_stmt)
        if not wm_res.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access action items for this workspace.",
            )

        now = datetime.now(timezone.utc)
        base_query = select(ActionItem).where(ActionItem.workspace_id == workspace_id)

        # 1. Search (Title, Description, Assignee Name)
        if search and search.strip():
            term = f"%{search.strip()}%"
            base_query = base_query.where(
                or_(
                    ActionItem.title.ilike(term),
                    ActionItem.description.ilike(term),
                    ActionItem.assignee_name.ilike(term),
                )
            )

        # 2. Status Filter
        if status_filter and status_filter.upper() != "ALL":
            st_upper = status_filter.upper().strip()
            if st_upper == "OVERDUE":
                base_query = base_query.where(
                    ActionItem.due_date < now,
                    ActionItem.status.notin_([ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED]),
                )
            elif st_upper in ActionItemStatus.__members__:
                base_query = base_query.where(ActionItem.status == ActionItemStatus[st_upper])

        # 3. Assignee Filter
        if assignee_id:
            base_query = base_query.where(ActionItem.assignee_id == assignee_id)
        elif assignee_name and assignee_name.strip():
            if assignee_name.upper() == "UNASSIGNED":
                base_query = base_query.where(
                    or_(ActionItem.assignee_name.is_(None), ActionItem.assignee_name == "")
                )
            elif assignee_name.upper() == "MY_TASKS":
                base_query = base_query.where(
                    or_(
                        ActionItem.assignee_id == current_user.id,
                        ActionItem.assignee_name.ilike(f"%{current_user.full_name}%") if current_user.full_name else False,
                    )
                )
            else:
                base_query = base_query.where(ActionItem.assignee_name.ilike(f"%{assignee_name.strip()}%"))

        # 4. Priority Filter
        if priority_filter and priority_filter.upper() != "ALL":
            pr_upper = priority_filter.upper().strip()
            if pr_upper in PriorityLevel.__members__:
                base_query = base_query.where(ActionItem.priority == PriorityLevel[pr_upper])

        # 5. Meeting Filter
        if meeting_id:
            base_query = base_query.where(ActionItem.meeting_id == meeting_id)

        # 6. Due Date Filter
        if due_date_filter and due_date_filter.upper() != "ALL":
            dd_upper = due_date_filter.upper().strip()
            if dd_upper == "NO_DUE_DATE":
                base_query = base_query.where(ActionItem.due_date.is_(None))
            elif dd_upper == "OVERDUE":
                base_query = base_query.where(
                    ActionItem.due_date < now,
                    ActionItem.status.notin_([ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED]),
                )
            elif dd_upper in ("TODAY", "THIS_WEEK", "THIS_MONTH"):
                start_of_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
                if dd_upper == "TODAY":
                    end_of_today = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=timezone.utc)
                    base_query = base_query.where(ActionItem.due_date >= start_of_today, ActionItem.due_date <= end_of_today)
                elif dd_upper == "THIS_WEEK":
                    end_of_week = start_of_today + timedelta(days=7)
                    base_query = base_query.where(ActionItem.due_date >= start_of_today, ActionItem.due_date <= end_of_week)
                elif dd_upper == "THIS_MONTH":
                    end_of_month = datetime(now.year, now.month, 28, 23, 59, 59, tzinfo=timezone.utc)
                    base_query = base_query.where(ActionItem.due_date >= start_of_today, ActionItem.due_date <= end_of_month)

        # Count total matching query
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_res = await db.execute(count_stmt)
        total_count = total_res.scalar_one()

        # Sorting allowlist
        sort_column = ActionItem.due_date
        if sort_by == "priority":
            sort_column = ActionItem.priority
        elif sort_by == "status":
            sort_column = ActionItem.status
        elif sort_by == "created_at":
            sort_column = ActionItem.created_at
        elif sort_by == "title":
            sort_column = ActionItem.title

        if sort_order.lower() == "desc":
            base_query = base_query.order_by(sort_column.desc().nulls_last())
        else:
            base_query = base_query.order_by(sort_column.asc().nulls_last())

        # Pagination & Eager loading of meeting
        offset = (page - 1) * page_size
        paginated_query = base_query.offset(offset).limit(page_size).options(selectinload(ActionItem.meeting))

        res = await db.execute(paginated_query)
        items = list(res.scalars().all())

        return items, total_count

    @classmethod
    async def get_workspace_action_item_metrics(
        cls,
        db: AsyncSession,
        workspace_id: uuid.UUID,
        current_user: User,
    ) -> dict:
        """Compute workspace metrics (total, my_tasks, overdue, completed)."""
        wm_stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
        wm_res = await db.execute(wm_stmt)
        if not wm_res.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access action item metrics for this workspace.",
            )

        now = datetime.now(timezone.utc)

        # Total
        tot_stmt = select(func.count(ActionItem.id)).where(ActionItem.workspace_id == workspace_id)
        tot_res = await db.execute(tot_stmt)
        total = tot_res.scalar_one()

        # My Tasks
        user_filter = [ActionItem.assignee_id == current_user.id]
        if current_user.full_name:
            user_filter.append(ActionItem.assignee_name.ilike(f"%{current_user.full_name}%"))
        my_stmt = select(func.count(ActionItem.id)).where(
            ActionItem.workspace_id == workspace_id,
            or_(*user_filter),
        )
        my_res = await db.execute(my_stmt)
        my_tasks = my_res.scalar_one()

        # Overdue
        ov_stmt = select(func.count(ActionItem.id)).where(
            ActionItem.workspace_id == workspace_id,
            ActionItem.due_date < now,
            ActionItem.status.notin_([ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED]),
        )
        ov_res = await db.execute(ov_stmt)
        overdue = ov_res.scalar_one()

        # Completed
        comp_stmt = select(func.count(ActionItem.id)).where(
            ActionItem.workspace_id == workspace_id,
            ActionItem.status == ActionItemStatus.COMPLETED,
        )
        comp_res = await db.execute(comp_stmt)
        completed = comp_res.scalar_one()

        return {
            "total": total,
            "my_tasks": my_tasks,
            "overdue": overdue,
            "completed": completed,
        }


