"""create_billing_and_subscription_tables

Revision ID: k0l1m2n3o4p5
Revises: j9k0l1m2n3o4
Create Date: 2026-09-20 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'k0l1m2n3o4p5'
down_revision: Union[str, None] = 'j9k0l1m2n3o4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. subscription_plans
    op.create_table(
        'subscription_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('razorpay_plan_id', sa.String(length=100), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='INR'),
        sa.Column('billing_interval', sa.String(length=20), nullable=False, server_default='monthly'),
        sa.Column('max_transcription_hours', sa.Float(), nullable=False, server_default='5.0'),
        sa.Column('max_rag_queries', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('max_members', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscription_plans_code'), 'subscription_plans', ['code'], unique=True)
    op.create_index(op.f('ix_subscription_plans_razorpay_plan_id'), 'subscription_plans', ['razorpay_plan_id'], unique=False)

    # 2. workspace_subscriptions
    op.create_table(
        'workspace_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('razorpay_subscription_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workspace_subscriptions_workspace_id'), 'workspace_subscriptions', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_workspace_subscriptions_plan_id'), 'workspace_subscriptions', ['plan_id'], unique=False)
    op.create_index(op.f('ix_workspace_subscriptions_razorpay_subscription_id'), 'workspace_subscriptions', ['razorpay_subscription_id'], unique=False)
    op.create_index(op.f('ix_workspace_subscriptions_status'), 'workspace_subscriptions', ['status'], unique=False)

    # 3. payment_transactions
    op.create_table(
        'payment_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('razorpay_payment_id', sa.String(length=100), nullable=True),
        sa.Column('razorpay_order_id', sa.String(length=100), nullable=True),
        sa.Column('razorpay_subscription_id', sa.String(length=100), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='INR'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='created'),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['workspace_subscriptions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payment_transactions_workspace_id'), 'payment_transactions', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_payment_transactions_subscription_id'), 'payment_transactions', ['subscription_id'], unique=False)
    op.create_index(op.f('ix_payment_transactions_razorpay_payment_id'), 'payment_transactions', ['razorpay_payment_id'], unique=False)

    # 4. webhook_events
    op.create_table(
        'webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='razorpay'),
        sa.Column('event_id', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload_hash', sa.String(length=64), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_webhook_events_event_id'), 'webhook_events', ['event_id'], unique=True)
    op.create_index(op.f('ix_webhook_events_event_type'), 'webhook_events', ['event_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_webhook_events_event_type'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_event_id'), table_name='webhook_events')
    op.drop_table('webhook_events')

    op.drop_index(op.f('ix_payment_transactions_razorpay_payment_id'), table_name='payment_transactions')
    op.drop_index(op.f('ix_payment_transactions_subscription_id'), table_name='payment_transactions')
    op.drop_index(op.f('ix_payment_transactions_workspace_id'), table_name='payment_transactions')
    op.drop_table('payment_transactions')

    op.drop_index(op.f('ix_workspace_subscriptions_status'), table_name='workspace_subscriptions')
    op.drop_index(op.f('ix_workspace_subscriptions_razorpay_subscription_id'), table_name='workspace_subscriptions')
    op.drop_index(op.f('ix_workspace_subscriptions_plan_id'), table_name='workspace_subscriptions')
    op.drop_index(op.f('ix_workspace_subscriptions_workspace_id'), table_name='workspace_subscriptions')
    op.drop_table('workspace_subscriptions')

    op.drop_index(op.f('ix_subscription_plans_razorpay_plan_id'), table_name='subscription_plans')
    op.drop_index(op.f('ix_subscription_plans_code'), table_name='subscription_plans')
    op.drop_table('subscription_plans')
