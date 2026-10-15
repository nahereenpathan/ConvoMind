"""Comprehensive unit and API test suite for Razorpay SaaS Billing & Subscription integration."""

import uuid
import pytest
from datetime import datetime, timezone
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import WorkspaceRole, SubscriptionStatus, PlanCode
from app.models.billing import SubscriptionPlan, WorkspaceSubscription, PaymentTransaction, WebhookEvent
from app.models.workspace import Workspace, WorkspaceMember
from app.models.user import User
from app.services.billing_service import billing_service
from app.services.entitlement_service import entitlement_service
from app.services.razorpay_service import razorpay_service


@pytest.mark.asyncio
async def test_get_billing_plans(client: AsyncClient, db_session):
    """Test public listing of SaaS billing plans."""
    response = await client.get("/api/v1/billing/plans")
    assert response.status_code == status.HTTP_200_OK
    plans = response.json()
    assert len(plans) >= 3

    codes = [p["code"] for p in plans]
    assert PlanCode.FREE.value in codes
    assert PlanCode.PRO.value in codes
    assert PlanCode.ENTERPRISE.value in codes


@pytest.mark.asyncio
async def test_get_workspace_subscription_auto_provisions_free(client: AsyncClient, db_session, test_workspace, auth_headers):
    """Test workspace subscription auto-provisioning to FREE plan if new."""
    response = await client.get(
        "/api/v1/billing/subscription",
        params={"workspace_id": str(test_workspace.id)},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["workspace_id"] == str(test_workspace.id)
    assert data["status"] == SubscriptionStatus.ACTIVE.value
    assert data["plan"]["code"] == PlanCode.FREE.value


@pytest.mark.asyncio
async def test_get_workspace_usage(client: AsyncClient, db_session, test_workspace, auth_headers):
    """Test fetching workspace usage metrics and quota percentages."""
    response = await client.get(
        "/api/v1/billing/usage",
        params={"workspace_id": str(test_workspace.id)},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    usage = response.json()
    assert "transcribed_hours" in usage
    assert "max_transcription_hours" in usage
    assert "rag_queries" in usage
    assert "members_count" in usage


@pytest.mark.asyncio
async def test_create_subscription_owner_permission(client: AsyncClient, db_session, test_workspace, test_user, auth_headers):
    """Test workspace OWNER initiating a Pro plan subscription."""
    response = await client.post(
        "/api/v1/billing/subscriptions",
        params={"workspace_id": str(test_workspace.id)},
        json={"plan_code": "PRO"},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    sub_res = response.json()
    assert sub_res["plan_code"] == "PRO"
    assert "razorpay_subscription_id" in sub_res
    assert sub_res["razorpay_key_id"] is not None


@pytest.mark.asyncio
async def test_create_subscription_invalid_plan(client: AsyncClient, db_session, test_workspace, auth_headers):
    """Test creating subscription with an invalid plan code."""
    response = await client.post(
        "/api/v1/billing/subscriptions",
        params={"workspace_id": str(test_workspace.id)},
        json={"plan_code": "NON_EXISTENT_PLAN"},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_create_subscription_rbac_member_denied(client: AsyncClient, db_session, test_workspace, auth_headers):
    """Test MEMBER role user is denied from modifying subscription."""
    # Create non-owner user member
    member_user = User(
        id=uuid.uuid4(),
        email=f"member_{uuid.uuid4().hex[:6]}@convomind.ai",
        full_name="Member User",
        is_active=True,
    )
    db_session.add(member_user)
    mem = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        user_id=member_user.id,
        role=WorkspaceRole.MEMBER,
    )
    db_session.add(mem)
    await db_session.commit()

    # Call with non-owner member in DB (service raises 403)
    try:
        await billing_service.verify_workspace_billing_permission(db_session, test_workspace.id, member_user)
        assert False, "Should have raised 403 Forbidden"
    except Exception as e:
        assert getattr(e, "status_code", 400) == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_payment_verification(client: AsyncClient, db_session, test_workspace, auth_headers):
    """Test payment signature verification and plan activation."""
    # First create sub
    await client.post(
        "/api/v1/billing/subscriptions",
        params={"workspace_id": str(test_workspace.id)},
        json={"plan_code": "PRO"},
        headers=auth_headers
    )

    # Verify payment
    pay_res = await client.post(
        "/api/v1/billing/payments/verify",
        params={"workspace_id": str(test_workspace.id)},
        json={
            "razorpay_payment_id": "pay_test_12345",
            "razorpay_subscription_id": "sub_test_12345",
            "razorpay_signature": "mock_valid_sig"
        },
        headers=auth_headers
    )
    assert pay_res.status_code == status.HTTP_200_OK
    assert pay_res.json()["success"] is True

    # Check updated subscription status in DB
    sub_res = await client.get(
        "/api/v1/billing/subscription",
        params={"workspace_id": str(test_workspace.id)},
        headers=auth_headers
    )
    assert sub_res.json()["status"] == SubscriptionStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_webhook_idempotency(db_session, test_workspace):
    """Test strict webhook idempotency (duplicate webhooks do not duplicate state)."""
    raw_body = b'{"event": "subscription.charged", "event_id": "evt_test_12345"}'
    signature = "valid_test_sig"
    payload = {"event": "subscription.charged", "event_id": "evt_test_12345"}

    # First delivery
    res1 = await billing_service.process_webhook_event(db_session, raw_body, signature, payload)
    assert res1["status"] in ["success", "already_processed"]

    # Duplicate delivery
    res2 = await billing_service.process_webhook_event(db_session, raw_body, signature, payload)
    assert res2["status"] == "already_processed"


@pytest.mark.asyncio
async def test_subscription_cancellation_and_resume(client: AsyncClient, db_session, test_workspace, auth_headers):
    """Test scheduling subscription cancellation and resuming it."""
    # Ensure active subscription is provisioned
    await client.get(
        "/api/v1/billing/subscription",
        params={"workspace_id": str(test_workspace.id)},
        headers=auth_headers
    )
    # Cancel
    c_res = await client.post(
        "/api/v1/billing/subscriptions/cancel",
        params={"workspace_id": str(test_workspace.id)},
        headers=auth_headers
    )
    assert c_res.status_code == status.HTTP_200_OK
    assert c_res.json()["cancel_at_period_end"] is True

    # Resume
    r_res = await client.post(
        "/api/v1/billing/subscriptions/resume",
        params={"workspace_id": str(test_workspace.id)},
        headers=auth_headers
    )
    assert r_res.status_code == status.HTTP_200_OK
    assert r_res.json()["cancel_at_period_end"] is False


@pytest.mark.asyncio
async def test_payment_history(client: AsyncClient, db_session, test_workspace, auth_headers):
    """Test retrieving workspace payment transaction history."""
    response = await client.get(
        "/api/v1/billing/payments",
        params={"workspace_id": str(test_workspace.id)},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)
