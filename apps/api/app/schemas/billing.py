"""Pydantic schemas for SaaS billing, plans, checkout, and payments."""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class SubscriptionPlanResponse(BaseModel):
    """Schema for public subscription plan response."""

    id: uuid.UUID
    code: str
    name: str
    description: Optional[str] = None
    amount: int  # in paise (e.g. 249900 = ₹2,499)
    currency: str = "INR"
    billing_interval: str = "monthly"
    max_transcription_hours: float
    max_rag_queries: int
    max_members: int
    active: bool

    class Config:
        from_attributes = True


class WorkspaceSubscriptionResponse(BaseModel):
    """Schema for workspace subscription response."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    razorpay_subscription_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    cancelled_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    plan: SubscriptionPlanResponse

    class Config:
        from_attributes = True


class WorkspaceUsageResponse(BaseModel):
    """Schema for workspace live usage metrics and plan limits."""

    transcribed_hours: float
    max_transcription_hours: float
    rag_queries: int
    max_rag_queries: int
    members_count: int
    max_members: int
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    transcription_percentage: float
    rag_percentage: float
    members_percentage: float


class CreateSubscriptionRequest(BaseModel):
    """Request payload to initiate a plan upgrade / subscription."""

    plan_code: str = Field(..., example="PRO", description="Target plan code ('PRO', 'ENTERPRISE')")


class CreateSubscriptionResponse(BaseModel):
    """Safe Razorpay checkout initiation payload sent to frontend."""

    subscription_id: uuid.UUID
    razorpay_subscription_id: str
    razorpay_key_id: str
    plan_code: str
    plan_name: str
    amount: int
    currency: str
    status: str


class PaymentVerificationRequest(BaseModel):
    """Payload sent by frontend checkout handler to verify payment signature."""

    razorpay_payment_id: str
    razorpay_subscription_id: str
    razorpay_signature: str


class PaymentVerificationResponse(BaseModel):
    """Response payload for payment verification."""

    success: bool
    status: str
    message: str


class PaymentTransactionResponse(BaseModel):
    """Payment transaction history record."""

    id: uuid.UUID
    razorpay_payment_id: Optional[str] = None
    razorpay_subscription_id: Optional[str] = None
    amount: int
    currency: str
    status: str
    payment_method: Optional[str] = None
    failure_reason: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
