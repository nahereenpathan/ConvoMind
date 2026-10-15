"""AI Follow-Up service handling grounded LLM draft generation, human approval workflows, and email dispatch."""

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import FollowUpStatus, FollowUpType, NotificationType, WorkspaceRole
from app.models.follow_up import FollowUp
from app.models.intelligence import ActionItem, Decision, MeetingQuestion, MeetingSummary
from app.models.meeting import Meeting, MeetingParticipant, Speaker
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.follow_up import FollowUpCreateRequest, FollowUpEmailDraftOutput, FollowUpUpdateRequest
from app.services.email import EmailProviderError, MockEmailProvider, get_email_provider
from app.services.intelligence.factory import get_llm_provider
from app.services.notifications.notification_service import NotificationService

logger = logging.getLogger(__name__)


class FollowUpService:
    """Service handling AI follow-up draft generation, editing, and explicit human-approved email sending."""

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
        row = (await db.execute(stmt)).first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found.",
            )
        return row[0], row[1]

    @classmethod
    async def generate_follow_up(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
        data: FollowUpCreateRequest,
    ) -> FollowUp:
        """Generate a grounded AI follow-up draft based on finalized meeting summary, decisions, and action items."""
        meeting, member = await cls._verify_meeting_access(db, meeting_id, current_user.id)

        if member.role == WorkspaceRole.GUEST:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guests cannot generate follow-up drafts.",
            )

        # Fetch meeting intelligence entities
        sum_stmt = select(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id).order_by(MeetingSummary.created_at.desc())
        summary = (await db.execute(sum_stmt)).scalars().first()

        # Fetch transcript as fallback if intelligence summary is missing
        from app.models.transcript import Transcript
        from app.models.enums import TranscriptStatus
        tx_stmt = select(Transcript).where(Transcript.meeting_id == meeting.id, Transcript.status == TranscriptStatus.COMPLETED)
        transcript = (await db.execute(tx_stmt)).scalars().first()

        if not summary and not transcript:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No meeting transcript or AI intelligence found. Please process the meeting recording first.",
            )

        overview_text = summary.overview if summary else (transcript.full_text[:1000] if transcript and transcript.full_text else f"Meeting discussion for '{meeting.title}'.")

        items_stmt = select(ActionItem).options(selectinload(ActionItem.assignee)).where(ActionItem.meeting_id == meeting.id)
        action_items = list((await db.execute(items_stmt)).scalars().all())

        dec_stmt = select(Decision).where(Decision.meeting_id == meeting.id)
        decisions = list((await db.execute(dec_stmt)).scalars().all())

        part_stmt = select(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting.id)
        participants = list((await db.execute(part_stmt)).scalars().all())

        spk_stmt = select(Speaker).where(Speaker.meeting_id == meeting.id)
        speakers = list((await db.execute(spk_stmt)).scalars().all())

        participant_emails = [p.email for p in participants if p.email]
        participant_names = [p.name for p in participants if p.name]
        for s in speakers:
            if s.name and s.name not in participant_names:
                participant_names.append(s.name)

        if not participant_names:
            participant_names = [current_user.full_name or "Team Member"]

        default_recipients = participant_emails if participant_emails else [current_user.email]

        # Construct grounded context text for LLM
        context_lines = [
            f"Meeting Title: {meeting.title}",
            f"Overview: {overview_text}",
            "\nDecisions Agreed:",
        ]
        if decisions:
            for d in decisions:
                dec_str = f"{d.title}: {d.context}" if d.context else d.title
                context_lines.append(f"- {dec_str}")
        else:
            context_lines.append("- None")


        context_lines.append("\nAction Items:")
        if action_items:
            for ai in action_items:
                assignee_str = ai.assignee.full_name if ai.assignee else (ai.assignee_name or "Unassigned")
                context_lines.append(f"- {ai.description or ai.title} (Assignee: {assignee_str})")
        else:
            context_lines.append("- None")


        context_text = "\n".join(context_lines)

        # Invoke LLM provider for grounded draft synthesis
        prompt = (
            f"Generate a professional, structured follow-up email draft for the meeting titled '{meeting.title}'.\n"
            f"Grounded Meeting Intelligence Context:\n{context_text}\n\n"
            f"Strict Grounding Rules:\n"
            f"1. Rely ONLY on the provided decisions and action items.\n"
            f"2. Do NOT invent new decisions, participants, or commitments.\n"
        )
        if data.additional_instructions:
            prompt += f"3. User Instruction: {data.additional_instructions}\n"

        llm_provider = get_llm_provider()

        try:
            draft_output: FollowUpEmailDraftOutput = await llm_provider.generate_structured_json(
                prompt=prompt,
                response_schema=FollowUpEmailDraftOutput,
            )
            subject = draft_output.subject
            content = draft_output.body
            recipients = default_recipients
        except Exception as llm_err:
            logger.warning(f"Structured LLM follow-up generation failed: {llm_err}. Using deterministic fallback.")
            subject = f"Next Steps & Action Items: {meeting.title}"
            content = (
                f"Hello Team,\n\nHere is a summary of next steps from '{meeting.title}':\n\n"
                f"Summary:\n{overview_text}\n\n"
                f"Action Items:\n"
                + ("\n".join(f"- {ai.description}" for ai in action_items) if action_items else "- Review recording transcript")
                + "\n\nBest regards,\nConvoMind AI"
            )
            recipients = default_recipients

        follow_up = FollowUp(
            id=uuid.uuid4(),
            workspace_id=meeting.workspace_id,
            meeting_id=meeting.id,
            created_by_id=current_user.id,
            type=data.type,
            status=FollowUpStatus.READY,
            subject=subject,
            content=content,
            recipients=recipients,
            follow_up_metadata={"generated_by": "ConvoMind AI FollowUp Engine"},
        )
        db.add(follow_up)
        await db.commit()
        await db.refresh(follow_up)


        # Dispatch notification to user
        await NotificationService.create_and_dispatch_notification(
            db=db,
            user_id=current_user.id,
            workspace_id=meeting.workspace_id,
            type=NotificationType.FOLLOW_UP_READY,
            title="AI Follow-up Draft Ready",
            message=f"Follow-up email draft for '{meeting.title}' is ready for review.",
            entity_type="follow_up",
            entity_id=follow_up.id,
        )

        return follow_up

    @classmethod
    async def list_follow_ups(
        cls,
        db: AsyncSession,
        meeting_id: uuid.UUID,
        current_user: User,
    ) -> List[FollowUp]:
        """List all follow-up drafts for a meeting."""
        meeting, _ = await cls._verify_meeting_access(db, meeting_id, current_user.id)

        stmt = (
            select(FollowUp)
            .where(FollowUp.meeting_id == meeting.id)
            .order_by(FollowUp.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_follow_up(
        cls,
        db: AsyncSession,
        follow_up_id: uuid.UUID,
        current_user: User,
    ) -> FollowUp:
        """Retrieve details for a single follow-up item with workspace isolation check."""
        stmt = (
            select(FollowUp, Meeting, WorkspaceMember)
            .join(Meeting, Meeting.id == FollowUp.meeting_id)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Meeting.workspace_id)
            .where(
                FollowUp.id == follow_up_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Follow-up draft not found.",
            )
        return row[0]

    @classmethod
    async def update_follow_up(
        cls,
        db: AsyncSession,
        follow_up_id: uuid.UUID,
        current_user: User,
        data: FollowUpUpdateRequest,
    ) -> FollowUp:
        """Update subject, content, recipients, or status of a follow-up draft before sending."""
        follow_up = await cls.get_follow_up(db, follow_up_id, current_user)

        for key, val in data.model_dump(exclude_unset=True).items():
            if val is not None:
                setattr(follow_up, key, val)

        await db.commit()
        await db.refresh(follow_up)
        return follow_up

    @classmethod
    async def send_follow_up(
        cls,
        db: AsyncSession,
        follow_up_id: uuid.UUID,
        current_user: User,
    ) -> FollowUp:
        """Explicitly execute dispatch of human-approved follow-up email."""
        follow_up = await cls.get_follow_up(db, follow_up_id, current_user)

        if follow_up.status == FollowUpStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot send a cancelled follow-up draft.",
            )

        target_recipients = follow_up.recipients or [current_user.email]

        email_provider = get_email_provider()

        import sys
        from app.core.config import settings
        is_testing = settings.ENVIRONMENT == "testing" or "pytest" in sys.modules

        if isinstance(email_provider, MockEmailProvider) and not is_testing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email delivery service is not configured. Please configure SMTP settings (EMAIL_PROVIDER=smtp, SMTP_HOST, SMTP_USER, SMTP_PASSWORD) in .env to send live emails.",
            )

        from app.services.email.dispatch import EmailDispatchService

        dispatched_count = 0
        last_error = None

        for r_email in target_recipients:
            clean_email = r_email.strip()
            if "@" in clean_email:
                try:
                    log = await EmailDispatchService.enqueue_email(
                        db=db,
                        recipient_email=clean_email,
                        recipient_name=clean_email,
                        event_type="follow_up_draft",
                        template_data={
                            "meeting_id": str(follow_up.meeting_id),
                            "meeting_title": follow_up.subject,
                            "follow_up_content": follow_up.content,
                            "recipients": target_recipients,
                        },
                        user_id=current_user.id,
                        workspace_id=follow_up.workspace_id,
                        meeting_id=follow_up.meeting_id,
                        idempotency_key=f"follow_up:{follow_up.id}:{clean_email}",
                        check_preference=False,  # Human approved follow-up email
                    )
                    if log:
                        dispatched_count += 1
                except Exception as exc:
                    logger.error(f"Failed queueing follow-up email to {clean_email}: {exc}")
                    last_error = str(exc)

        if dispatched_count == 0:
            err_msg = last_error or "No valid recipient email addresses found or email dispatch failed."
            status_code = (
                status.HTTP_400_BAD_REQUEST
                if ("SMTP authentication" in err_msg or "not configured" in err_msg or "No valid recipient" in err_msg)
                else status.HTTP_530_SERVICE_UNAVAILABLE
            )
            raise HTTPException(
                status_code=status_code,
                detail=f"Email dispatch failed: {err_msg}",
            )

        follow_up.status = FollowUpStatus.SENT
        await db.commit()
        await db.refresh(follow_up)

        logger.info(f"Human-approved follow-up {follow_up.id} sent to {dispatched_count} recipients.")
        return follow_up
