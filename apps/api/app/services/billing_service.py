"""Production Billing Service for Razorpay Subscriptions, Checkout, Payments, and Webhooks."""

import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import (
    SubscriptionPlan,
    WorkspaceSubscription,
    PaymentTransaction,
    WebhookEvent,
)
from app.models.enums import SubscriptionStatus, PlanCode, WorkspaceRole, NotificationType
from app.models.workspace import WorkspaceMember
from app.models.user import User
from app.schemas.billing import (
    SubscriptionPlanResponse,
    WorkspaceSubscriptionResponse,
    WorkspaceUsageResponse,
    CreateSubscriptionResponse,
    PaymentVerificationRequest,
    PaymentVerificationResponse,
    PaymentTransactionResponse,
)
from app.services.razorpay_service import razorpay_service
from app.services.entitlement_service import entitlement_service
from app.services.notifications.notification_service import NotificationService

logger = logging.getLogger(__name__)


class BillingService:
    """Core domain logic for Razorpay SaaS billing operations."""

    async def seed_default_plans(self, db: AsyncSession) -> None:
        """Ensure system plans (FREE, PRO, ENTERPRISE) exist in DB."""
        default_plans = [
            {
                "code": PlanCode.FREE.value,
                "name": "Starter Tier",
                "description": "Ideal for individuals and tiny teams starting out with meeting intelligence.",
                "razorpay_plan_id": None,
                "amount": 0,
                "currency": "INR",
                "billing_interval": "monthly",
                "max_transcription_hours": 5.0,
                "max_rag_queries": 100,
                "max_members": 2,
            },
            {
                "code": PlanCode.PRO.value,
                "name": "Pro SaaS Plan",
                "description": "For growing teams needing higher quotas, priority processing, and extra AI capabilities.",
                "razorpay_plan_id": "plan_PRO_monthly_inr",
                "amount": 249900,  # ₹2,499 per month
                "currency": "INR",
                "billing_interval": "monthly",
                "max_transcription_hours": 50.0,
                "max_rag_queries": 5000,
                "max_members": 10,
            },
            {
                "code": PlanCode.ENTERPRISE.value,
                "name": "Enterprise Intelligence",
                "description": "Unlimited enterprise scale with customized compliance, security, and priority SLAs.",
                "razorpay_plan_id": "plan_ENT_monthly_inr",
                "amount": 799900,  # ₹7,999 per month
                "currency": "INR",
                "billing_interval": "monthly",
                "max_transcription_hours": 500.0,
                "max_rag_queries": 50000,
                "max_members": 100,
            },
        ]

        for p_data in default_plans:
            stmt = select(SubscriptionPlan).where(SubscriptionPlan.code == p_data["code"])
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if not existing:
                plan = SubscriptionPlan(id=uuid.uuid4(), **p_data)
                db.add(plan)
        
        await db.commit()

    async def get_plans(self, db: AsyncSession) -> List[SubscriptionPlanResponse]:
        """List active SaaS billing plans."""
        await self.seed_default_plans(db)
        stmt = select(SubscriptionPlan).where(SubscriptionPlan.active == True).order_by(SubscriptionPlan.amount.asc())
        plans = (await db.execute(stmt)).scalars().all()
        return [SubscriptionPlanResponse.model_validate(p) for p in plans]

    async def verify_workspace_billing_permission(
        self, db: AsyncSession, workspace_id: uuid.UUID, user: User
    ) -> WorkspaceMember:
        """Ensure requesting user is a member of the workspace with OWNER or ADMIN role."""
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id
        )
        member = (await db.execute(stmt)).scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this workspace's billing settings."
            )
        if member.role not in [WorkspaceRole.OWNER.value, WorkspaceRole.ADMIN.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace Owners or Admins can modify subscription settings."
            )
        return member

    async def get_workspace_subscription(
        self, db: AsyncSession, workspace_id: uuid.UUID
    ) -> WorkspaceSubscriptionResponse:
        """Fetch workspace active subscription or provision FREE default."""
        await self.seed_default_plans(db)
        sub, plan = await entitlement_service.get_active_subscription_and_plan(db, workspace_id)
        
        # Ensure subscription is saved in DB if newly created
        stmt = (
            select(WorkspaceSubscription)
            .options(selectinload(WorkspaceSubscription.plan))
            .where(WorkspaceSubscription.id == sub.id)
        )
        db_sub = (await db.execute(stmt)).scalar_one_or_none()
        if not db_sub:
            sub.plan = plan
            db.add(sub)
            await db.commit()
            stmt = (
                select(WorkspaceSubscription)
                .options(selectinload(WorkspaceSubscription.plan))
                .where(WorkspaceSubscription.id == sub.id)
            )
            db_sub = (await db.execute(stmt)).scalar_one()
        
        db_sub.plan = db_sub.plan or plan
        return WorkspaceSubscriptionResponse.model_validate(db_sub)

    async def get_workspace_usage(
        self, db: AsyncSession, workspace_id: uuid.UUID
    ) -> WorkspaceUsageResponse:
        """Fetch live usage metrics against plan quotas."""
        sub, plan = await entitlement_service.get_active_subscription_and_plan(db, workspace_id)
        hours, rag, members = await entitlement_service.calculate_workspace_usage(
            db, workspace_id, sub.current_period_start
        )

        h_pct = min(100.0, round((hours / plan.max_transcription_hours) * 100, 1)) if plan.max_transcription_hours > 0 else 0.0
        r_pct = min(100.0, round((rag / plan.max_rag_queries) * 100, 1)) if plan.max_rag_queries > 0 else 0.0
        m_pct = min(100.0, round((members / plan.max_members) * 100, 1)) if plan.max_members > 0 else 0.0

        return WorkspaceUsageResponse(
            transcribed_hours=hours,
            max_transcription_hours=plan.max_transcription_hours,
            rag_queries=rag,
            max_rag_queries=plan.max_rag_queries,
            members_count=members,
            max_members=plan.max_members,
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            transcription_percentage=h_pct,
            rag_percentage=r_pct,
            members_percentage=m_pct,
        )

    async def create_subscription(
        self, db: AsyncSession, workspace_id: uuid.UUID, user: User, plan_code: str
    ) -> CreateSubscriptionResponse:
        """Initiate Razorpay recurring subscription for workspace upgrade."""
        await self.verify_workspace_billing_permission(db, workspace_id, user)
        await self.seed_default_plans(db)

        # Load selected plan from database
        stmt = select(SubscriptionPlan).where(
            SubscriptionPlan.code == plan_code.upper(),
            SubscriptionPlan.active == True
        )
        plan = (await db.execute(stmt)).scalar_one_or_none()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription plan '{plan_code}' is not available."
            )

        if plan.code == PlanCode.FREE.value:
            # Downgrade directly to FREE plan
            sub_stmt = select(WorkspaceSubscription).where(WorkspaceSubscription.workspace_id == workspace_id)
            db_sub = (await db.execute(sub_stmt)).scalar_one_or_none()
            if not db_sub:
                db_sub = WorkspaceSubscription(id=uuid.uuid4(), workspace_id=workspace_id, plan_id=plan.id)
                db.add(db_sub)
            else:
                db_sub.plan_id = plan.id
                db_sub.status = SubscriptionStatus.ACTIVE.value
                db_sub.cancel_at_period_end = False
            
            await db.commit()
            return CreateSubscriptionResponse(
                subscription_id=db_sub.id,
                razorpay_subscription_id="free_subscription",
                razorpay_key_id=razorpay_service.key_id,
                plan_code=plan.code,
                plan_name=plan.name,
                amount=0,
                currency="INR",
                status="ACTIVE",
            )

        # Create subscription in Razorpay
        rzp_sub = razorpay_service.create_subscription(
            razorpay_plan_id=plan.razorpay_plan_id,
            notes={"workspace_id": str(workspace_id), "user_id": str(user.id), "plan_code": plan.code},
        )

        razorpay_sub_id = rzp_sub.get("id")

        # Save or update WorkspaceSubscription
        sub_stmt = select(WorkspaceSubscription).where(WorkspaceSubscription.workspace_id == workspace_id)
        db_sub = (await db.execute(sub_stmt)).scalar_one_or_none()
        if not db_sub:
            db_sub = WorkspaceSubscription(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                plan_id=plan.id,
                razorpay_subscription_id=razorpay_sub_id,
                status=SubscriptionStatus.AUTHENTICATION_PENDING.value,
            )
            db.add(db_sub)
        else:
            db_sub.plan_id = plan.id
            db_sub.razorpay_subscription_id = razorpay_sub_id
            db_sub.status = SubscriptionStatus.AUTHENTICATION_PENDING.value
            db_sub.cancel_at_period_end = False

        await db.commit()
        await db.refresh(db_sub)

        return CreateSubscriptionResponse(
            subscription_id=db_sub.id,
            razorpay_subscription_id=razorpay_sub_id,
            razorpay_key_id=razorpay_service.key_id,
            plan_code=plan.code,
            plan_name=plan.name,
            amount=plan.amount,
            currency=plan.currency,
            status=db_sub.status,
        )

    async def verify_payment(
        self,
        db: AsyncSession,
        workspace_id: uuid.UUID,
        user: User,
        payload: PaymentVerificationRequest,
    ) -> PaymentVerificationResponse:
        """Verify payment signature from checkout and activate subscription."""
        await self.verify_workspace_billing_permission(db, workspace_id, user)

        # Signature verification
        valid = razorpay_service.verify_payment_signature(
            payload.razorpay_payment_id,
            payload.razorpay_subscription_id,
            payload.razorpay_signature,
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Razorpay payment signature verification failed."
            )

        # Update workspace subscription status to ACTIVE
        sub_stmt = select(WorkspaceSubscription).where(WorkspaceSubscription.workspace_id == workspace_id)
        db_sub = (await db.execute(sub_stmt)).scalar_one_or_none()
        if not db_sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace subscription record not found."
            )

        now = datetime.now(timezone.utc)
        db_sub.status = SubscriptionStatus.ACTIVE.value
        db_sub.current_period_start = now
        db_sub.current_period_end = now + timedelta(days=30)
        db_sub.razorpay_subscription_id = payload.razorpay_subscription_id

        # Record payment transaction
        plan_stmt = select(SubscriptionPlan).where(SubscriptionPlan.id == db_sub.plan_id)
        plan = (await db.execute(plan_stmt)).scalar_one_or_none()
        amount = plan.amount if plan else 249900

        tx = PaymentTransaction(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            subscription_id=db_sub.id,
            razorpay_payment_id=payload.razorpay_payment_id,
            razorpay_subscription_id=payload.razorpay_subscription_id,
            amount=amount,
            currency=plan.currency if plan else "INR",
            status="captured",
            payment_method="razorpay_checkout",
            paid_at=now,
        )
        db.add(tx)
        await db.commit()

        # Send notification
        try:
            await NotificationService.create_and_dispatch_notification(
                db=db,
                user_id=user.id,
                workspace_id=workspace_id,
                type=NotificationType.PAYMENT_SUCCESSFUL,
                title="Payment Successful",
                message=f"Your ConvoMind {plan.name if plan else 'Pro'} subscription is now ACTIVE.",
            )
        except Exception as n_err:
            logger.warning(f"Failed to dispatch billing notification: {n_err}")

        return PaymentVerificationResponse(
            success=True,
            status=SubscriptionStatus.ACTIVE.value,
            message="Payment verified successfully. Workspace plan upgraded!"
        )

    async def process_webhook_event(
        self, db: AsyncSession, raw_body: bytes, signature: str, payload_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Idempotent server-side processing of Razorpay webhook notifications."""
        # Signature Verification
        if not razorpay_service.verify_webhook_signature(raw_body, signature):
            logger.warning("Razorpay Webhook signature verification failed.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Razorpay webhook signature."
            )

        event_id = payload_dict.get("event_id") or payload_dict.get("id") or str(uuid.uuid4())
        event_type = payload_dict.get("event", "unknown")

        # Idempotency check: check if event processed already
        evt_stmt = select(WebhookEvent).where(WebhookEvent.event_id == event_id)
        existing_evt = (await db.execute(evt_stmt)).scalar_one_or_none()
        if existing_evt and existing_evt.processed:
            logger.info(f"Webhook event {event_id} already processed. Skipping.")
            return {"status": "already_processed", "event_id": event_id}

        if not existing_evt:
            evt = WebhookEvent(
                id=uuid.uuid4(),
                provider="razorpay",
                event_id=event_id,
                event_type=event_type,
                processed=False,
            )
            db.add(evt)
            await db.flush()
        else:
            evt = existing_evt

        # Extract entity payload
        entity_data = (
            payload_dict.get("payload", {})
            .get("subscription", {})
            .get("entity", {})
        ) or (
            payload_dict.get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )

        sub_id = entity_data.get("subscription_id") or entity_data.get("id")
        notes = entity_data.get("notes", {})
        workspace_id_str = notes.get("workspace_id")

        if sub_id or workspace_id_str:
            # Query target subscription
            query = select(WorkspaceSubscription)
            if workspace_id_str:
                query = query.where(WorkspaceSubscription.workspace_id == uuid.UUID(workspace_id_str))
            elif sub_id:
                query = query.where(WorkspaceSubscription.razorpay_subscription_id == sub_id)
            
            sub = (await db.execute(query)).scalar_one_or_none()
            now = datetime.now(timezone.utc)

            if sub:
                if event_type in ["subscription.authenticated", "subscription.activated", "subscription.charged"]:
                    sub.status = SubscriptionStatus.ACTIVE.value
                    sub.current_period_start = now
                    sub.current_period_end = now + timedelta(days=30)
                    
                    # Record payment transaction if payment entity exists
                    payment_id = entity_data.get("id") if "pay_" in str(entity_data.get("id")) else None
                    if payment_id:
                        tx = PaymentTransaction(
                            id=uuid.uuid4(),
                            workspace_id=sub.workspace_id,
                            subscription_id=sub.id,
                            razorpay_payment_id=payment_id,
                            razorpay_subscription_id=sub_id,
                            amount=entity_data.get("amount", 249900),
                            currency=entity_data.get("currency", "INR"),
                            status="captured",
                            paid_at=now,
                        )
                        db.add(tx)

                elif event_type in ["subscription.pending"]:
                    sub.status = SubscriptionStatus.PENDING.value

                elif event_type in ["subscription.halted"]:
                    sub.status = SubscriptionStatus.HALTED.value

                elif event_type in ["subscription.cancelled", "subscription.completed"]:
                    sub.status = SubscriptionStatus.CANCELLED.value
                    sub.cancelled_at = now

        # Mark event processed
        evt.processed = True
        evt.processed_at = datetime.now(timezone.utc)
        await db.commit()

        return {"status": "success", "event_id": event_id, "event_type": event_type}

    async def cancel_subscription(
        self, db: AsyncSession, workspace_id: uuid.UUID, user: User
    ) -> WorkspaceSubscriptionResponse:
        """Schedule subscription cancellation at current billing period end."""
        await self.verify_workspace_billing_permission(db, workspace_id, user)
        stmt = (
            select(WorkspaceSubscription)
            .options(selectinload(WorkspaceSubscription.plan))
            .where(WorkspaceSubscription.workspace_id == workspace_id)
        )
        sub = (await db.execute(stmt)).scalar_one_or_none()
        if not sub:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace subscription not found.")

        if sub.razorpay_subscription_id:
            razorpay_service.cancel_subscription(sub.razorpay_subscription_id, cancel_at_cycle_end=True)

        sub.cancel_at_period_end = True
        sub.cancelled_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(sub)
        return WorkspaceSubscriptionResponse.model_validate(sub)

    async def resume_subscription(
        self, db: AsyncSession, workspace_id: uuid.UUID, user: User
    ) -> WorkspaceSubscriptionResponse:
        """Resume subscription and clear pending cancellation."""
        await self.verify_workspace_billing_permission(db, workspace_id, user)
        stmt = (
            select(WorkspaceSubscription)
            .options(selectinload(WorkspaceSubscription.plan))
            .where(WorkspaceSubscription.workspace_id == workspace_id)
        )
        sub = (await db.execute(stmt)).scalar_one_or_none()
        if not sub:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace subscription not found.")

        sub.cancel_at_period_end = False
        sub.cancelled_at = None
        await db.commit()
        await db.refresh(sub)
        return WorkspaceSubscriptionResponse.model_validate(sub)

    async def get_payment_history(
        self, db: AsyncSession, workspace_id: uuid.UUID
    ) -> List[PaymentTransactionResponse]:
        """Fetch payment history records for workspace."""
        stmt = (
            select(PaymentTransaction)
            .where(PaymentTransaction.workspace_id == workspace_id)
            .order_by(PaymentTransaction.created_at.desc())
        )
        txs = (await db.execute(stmt)).scalars().all()
        return [PaymentTransactionResponse.model_validate(t) for t in txs]


billing_service = BillingService()
