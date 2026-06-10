"""Add created_at to frontend_search_index.

Revision ID: add_created_at_search_idx
Revises: extract_pipeline_status_20260608
Create Date: 2026-06-10
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_created_at_search_idx"
down_revision: Union[str, None] = "extract_pipeline_status_20260608"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard: table may not be created yet.
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'frontend_search_index')"
        )
    ).scalar()
    if not result:
        return

    # Also guard against column already existing (idempotent).
    col_exists = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'frontend_search_index' "
            "AND column_name = 'created_at')"
        )
    ).scalar()
    if col_exists:
        return

    op.add_column(
        "frontend_search_index",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'frontend_search_index')"
        )
    ).scalar()
    if not result:
        return

    op.drop_column("frontend_search_index", "created_at")
