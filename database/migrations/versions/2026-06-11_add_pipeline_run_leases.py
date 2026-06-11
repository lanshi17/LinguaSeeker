"""Add pipeline run worker leases.

Revision ID: pipeline_run_leases_20260611
Revises: add_created_at_search_idx
Create Date: 2026-06-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "pipeline_run_leases_20260611"
down_revision = "add_created_at_search_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipeline_run_states", sa.Column("source_key", sa.Text(), nullable=True))
    op.add_column("pipeline_run_states", sa.Column("owner_worker_id", sa.String(length=128), nullable=True))
    op.add_column("pipeline_run_states", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_pipeline_run_states_owner_heartbeat",
        "pipeline_run_states",
        ["owner_worker_id", "heartbeat_at"],
        unique=False,
    )
    op.create_index(
        "ux_pipeline_run_states_active_source_key",
        "pipeline_run_states",
        ["source_key"],
        unique=True,
        postgresql_where=sa.text("source_key IS NOT NULL AND pipeline_status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("ux_pipeline_run_states_active_source_key", table_name="pipeline_run_states")
    op.drop_index("ix_pipeline_run_states_owner_heartbeat", table_name="pipeline_run_states")
    op.drop_column("pipeline_run_states", "heartbeat_at")
    op.drop_column("pipeline_run_states", "owner_worker_id")
    op.drop_column("pipeline_run_states", "source_key")
