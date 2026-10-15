"""API endpoints for SaaS billing, Razorpay integration, subscriptions, and webhooks."""

import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.schemas.billing import (
    SubscriptionPlanResponse,
    WorkspaceSubscriptionResponse,
    WorkspaceUsageResponse,
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
    PaymentVerificationRequest,
    PaymentVerificationResponse,
    PaymentTransactionResponse,
)
from app.services.billing_service import billing_service

router = APIRouter()


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def get_plans(db: AsyncSession = Depends(get_db)):
    """Fetch available SaaS subscription plans."""
    return await billing_service.get_plans(db)


@router.get("/subscription", response_model=WorkspaceSubscriptionResponse)
async def get_workspace_subscription(
    workspace_id: uuid.UUID = Query(..., description="Target workspace ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch current subscription status for a workspace."""
    return await billing_service.get_workspace_subscription(db, workspace_id)


@router.get("/usage", response_model=WorkspaceUsageResponse)
async def get_workspace_usage(
    workspace_id: uuid.UUID = Query(..., description="Target workspace ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch live workspace usage metrics and quota limits."""
    return await billing_service.get_workspace_usage(db, workspace_id)


@router.post("/subscriptions", response_model=CreateSubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    request_data: CreateSubscriptionRequest,
    workspace_id: uuid.UUID = Query(..., description="Target workspace ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a Razorpay subscription for workspace upgrade."""
    return await billing_service.create_subscription(
        db, workspace_id, current_user, request_data.plan_code
    )


@router.post("/payments/verify", response_model=PaymentVerificationResponse)
async def verify_payment(
    request_data: PaymentVerificationRequest,
    workspace_id: uuid.UUID = Query(..., description="Target workspace ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify Razorpay payment signature and activate workspace subscription."""
    return await billing_service.verify_payment(
        db, workspace_id, current_user, request_data
    )


@router.post("/subscriptions/cancel", response_model=WorkspaceSubscriptionResponse)
async def cancel_subscription(
    workspace_id: uuid.UUID = Query(..., description="Target workspace ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Schedule workspace subscription cancellation at period end."""
    return await billing_service.cancel_subscription(db, workspace_id, current_user)


@router.post("/subscriptions/resume", response_model=WorkspaceSubscriptionResponse)
async def resume_subscription(
    workspace_id: uuid.UUID = Query(..., description="Target workspace ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume a pending cancelled workspace subscription."""
    return await billing_service.resume_subscription(db, workspace_id, current_user)


@router.get("/payments", response_model=List[PaymentTransactionResponse])
async def get_payment_history(
    workspace_id: uuid.UUID = Query(..., description="Target workspace ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch payment history records for workspace."""
    return await billing_service.get_payment_history(db, workspace_id)


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """Public server-to-server webhook endpoint for Razorpay event notifications."""
    raw_body = await request.body()
    try:
        payload_dict = await request.json()
    except Exception:
        payload_dict = {}

    return await billing_service.process_webhook_event(
        db=db,
        raw_body=raw_body,
        signature=x_razorpay_signature or "",
        payload_dict=payload_dict,
    )
