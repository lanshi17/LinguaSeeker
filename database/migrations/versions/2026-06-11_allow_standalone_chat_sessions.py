"""Allow standalone chat sessions without a processing run.

Revision ID: 2026_06_11_allow_standalone_chat_sessions
Revises: add_created_at_search_idx
Create Date: 2026-06-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2026_06_11_allow_standalone_chat_sessions"
down_revision = "add_created_at_search_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "chat_sessions",
        "processing_run_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM chat_messages "
            "WHERE chat_session_id IN ("
            "SELECT chat_session_id FROM chat_sessions "
            "WHERE processing_run_id IS NULL"
            ")"
        )
    )
    op.execute(
        sa.text("DELETE FROM chat_sessions WHERE processing_run_id IS NULL")
    )
    op.alter_column(
        "chat_sessions",
        "processing_run_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
