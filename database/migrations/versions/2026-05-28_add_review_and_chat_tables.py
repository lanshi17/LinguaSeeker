"""add review and chat tables for Phase 4

Revision ID: review_chat_20260528
Revises: add_nulls_distinct_20260527
Create Date: 2026-05-28
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "review_chat_20260528"
down_revision: Union[str, None] = "add_nulls_distinct_20260527"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Review audit events: track status transitions and field-level deltas
    op.create_table(
        "review_audit_events",
        sa.Column("review_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("old_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=True),
        sa.Column("field_deltas", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["canonical_evidence_id"],
            ["canonical_evidence_items.canonical_evidence_id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.user_id"],
        ),
        sa.PrimaryKeyConstraint("review_event_id"),
    )
    op.create_index(
        "ix_review_audit_events_canonical_evidence_id",
        "review_audit_events",
        ["canonical_evidence_id"],
    )
    op.create_index(
        "ix_review_audit_events_reviewer_id",
        "review_audit_events",
        ["reviewer_id"],
    )

    # Chat sessions: bind conversation to a processing run
    op.create_table(
        "chat_sessions",
        sa.Column("chat_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("processing_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.processing_run_id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
        ),
        sa.PrimaryKeyConstraint("chat_session_id"),
    )
    op.create_index(
        "ix_chat_sessions_processing_run_id",
        "chat_sessions",
        ["processing_run_id"],
    )

    # Chat messages: persist conversation history
    op.create_table(
        "chat_messages",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chat_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chat_session_id"],
            ["chat_sessions.chat_session_id"],
        ),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        "ix_chat_messages_chat_session_id",
        "chat_messages",
        ["chat_session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_chat_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_processing_run_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index("ix_review_audit_events_reviewer_id", table_name="review_audit_events")
    op.drop_index("ix_review_audit_events_canonical_evidence_id", table_name="review_audit_events")
    op.drop_table("review_audit_events")
