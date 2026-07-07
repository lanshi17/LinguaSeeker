"""Add LLM-generated title to chat sessions.

Revision ID: chat_session_title_20260705
Revises: pipeline_jobs_20260625
Create Date: 2026-07-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "chat_session_title_20260705"
down_revision = "pipeline_jobs_20260625"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("title", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_sessions", "title")
