"""Service for enforcing subscription plan feature quotas and entitlements."""

import uuid
from datetime import datetime
from typing import Tuple, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import WorkspaceSubscription, SubscriptionPlan
from app.models.enums import SubscriptionStatus, PlanCode, MeetingStatus
from app.models.meeting import Meeting
from app.models.chat import ChatMessage
from app.models.workspace import WorkspaceMember


class EntitlementService:
    """Service to verify workspace limits before costly AI / transcription operations."""

    async def get_active_subscription_and_plan(
        self, db: AsyncSession, workspace_id: uuid.UUID
    ) -> Tuple[WorkspaceSubscription, SubscriptionPlan]:
        """Retrieve active subscription and associated plan entity for workspace."""
        # Query workspace subscription
        stmt = (
            select(WorkspaceSubscription, SubscriptionPlan)
            .join(SubscriptionPlan, WorkspaceSubscription.plan_id == SubscriptionPlan.id)
            .where(WorkspaceSubscription.workspace_id == workspace_id)
            .order_by(WorkspaceSubscription.created_at.desc())
        )
        res = await db.execute(stmt)
        row = res.first()

        if not row:
            # Fallback to default FREE plan if no subscription record exists
            plan_stmt = select(SubscriptionPlan).where(SubscriptionPlan.code == PlanCode.FREE.value)
            plan_res = await db.execute(plan_stmt)
            plan = plan_res.scalar_one_or_none()

            if not plan:
                # Seed temporary FREE plan instance if DB unseeded
                plan = SubscriptionPlan(
                    id=uuid.uuid4(),
                    code=PlanCode.FREE.value,
                    name="Starter Tier",
                    amount=0,
                    currency="INR",
                    max_transcription_hours=5.0,
                    max_rag_queries=100,
                    max_members=2,
                )

            sub = WorkspaceSubscription(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                plan_id=plan.id,
                status=SubscriptionStatus.ACTIVE.value,
            )
            sub.plan = plan
            return sub, plan

        sub, plan = row
        sub.plan = plan
        return sub, plan


    async def calculate_workspace_usage(
        self, db: AsyncSession, workspace_id: uuid.UUID, period_start: Optional[datetime] = None
    ) -> Tuple[float, int, int]:
        """Calculate current transcribed hours, RAG queries, and total members."""
        # 1. Transcribed Hours
        t_stmt = select(func.coalesce(func.sum(Meeting.duration_seconds), 0)).where(
            Meeting.workspace_id == workspace_id,
            Meeting.status == MeetingStatus.COMPLETED,
            Meeting.deleted_at.is_(None)
        )
        if period_start:
            t_stmt = t_stmt.where(Meeting.created_at >= period_start)
        t_seconds = (await db.execute(t_stmt)).scalar() or 0
        transcribed_hours = round(t_seconds / 3600.0, 2)

        # 2. RAG Queries (chat messages with role 'user')
        rag_stmt = (
            select(func.count(ChatMessage.id))
            .where(
                ChatMessage.role == "user",
                ChatMessage.created_at >= period_start if period_start else True
            )
        )
        rag_queries = (await db.execute(rag_stmt)).scalar() or 0

        # 3. Workspace Members Count
        mem_stmt = select(func.count(WorkspaceMember.id)).where(WorkspaceMember.workspace_id == workspace_id)
        members_count = (await db.execute(mem_stmt)).scalar() or 0

        return transcribed_hours, rag_queries, members_count

    async def check_transcription_entitlement(
        self, db: AsyncSession, workspace_id: uuid.UUID, additional_hours: float = 0.0
    ) -> None:
        """Verify workspace has not exceeded transcription hours limit."""
        sub, plan = await self.get_active_subscription_and_plan(db, workspace_id)
        current_hours, _, _ = await self.calculate_workspace_usage(db, workspace_id, sub.current_period_start)

        if (current_hours + additional_hours) > plan.max_transcription_hours:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Transcription quota exceeded ({current_hours:.1f} / {plan.max_transcription_hours} hrs). Upgrade your ConvoMind subscription to proceed."
            )

    async def check_rag_entitlement(self, db: AsyncSession, workspace_id: uuid.UUID) -> None:
        """Verify workspace has not exceeded RAG AI query limit."""
        sub, plan = await self.get_active_subscription_and_plan(db, workspace_id)
        _, rag_queries, _ = await self.calculate_workspace_usage(db, workspace_id, sub.current_period_start)

        if rag_queries >= plan.max_rag_queries:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"RAG AI query quota reached ({rag_queries} / {plan.max_rag_queries} queries). Upgrade to Pro for increased RAG queries."
            )

    async def check_member_entitlement(self, db: AsyncSession, workspace_id: uuid.UUID) -> None:
        """Verify workspace member limit has not been reached."""
        sub, plan = await self.get_active_subscription_and_plan(db, workspace_id)
        _, _, members_count = await self.calculate_workspace_usage(db, workspace_id)

        if members_count >= plan.max_members:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Workspace member limit reached ({members_count} / {plan.max_members} seats). Upgrade your subscription plan to add more team members."
            )


entitlement_service = EntitlementService()
