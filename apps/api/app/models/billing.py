"""SQLAlchemy models for production Razorpay billing, subscriptions, and webhooks."""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.enums import SubscriptionStatus, PlanCode


class SubscriptionPlan(Base):
    """SaaS Billing Plan definitions (e.g., FREE, PRO, ENTERPRISE)."""

    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    razorpay_plan_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Amount in paise (e.g. 249900 = ₹2,499)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    billing_interval: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    
    # Feature Entitlements & Quotas
    max_transcription_hours: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    max_rag_queries: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    max_members: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    subscriptions: Mapped[List["WorkspaceSubscription"]] = relationship(
        "WorkspaceSubscription", back_populates="plan"
    )


class WorkspaceSubscription(Base):
    """Active or historical workspace subscription details."""

    __tablename__ = "workspace_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscription_plans.id"), nullable=False, index=True
    )
    razorpay_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(100), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=SubscriptionStatus.ACTIVE.value, index=True
    )
    current_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", backref="subscription_records")
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="subscriptions")
    transactions: Mapped[List["PaymentTransaction"]] = relationship(
        "PaymentTransaction", back_populates="subscription", cascade="all, delete-orphan"
    )


class PaymentTransaction(Base):
    """Audit log of payments, renewals, and refunds for a workspace."""

    __tablename__ = "payment_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("workspace_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(
        String(100), index=True, nullable=True
    )
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    razorpay_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    subscription: Mapped[Optional["WorkspaceSubscription"]] = relationship(
        "WorkspaceSubscription", back_populates="transactions"
    )


class WebhookEvent(Base):
    """Idempotency and audit store for incoming Razorpay webhook events."""

    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="razorpay")
    event_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
