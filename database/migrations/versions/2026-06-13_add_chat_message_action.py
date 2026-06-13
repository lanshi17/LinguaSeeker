"""Add nullable JSONB action column to chat_messages.

Revision ID: chat_message_action_20260613
Revises: pipeline_run_leases_20260611
Create Date: 2026-06-13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "chat_message_action_20260613"
down_revision = "pipeline_run_leases_20260611"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("action", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "action")
