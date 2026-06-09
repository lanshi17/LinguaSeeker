"""Extract pipeline_status as a dedicated column on pipeline_run_states.

Revision ID: extract_pipeline_status_20260608
Revises: reviewed_unmappable_20260608
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "extract_pipeline_status_20260608"
down_revision = "reviewed_unmappable_20260608"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column(
        "pipeline_run_states",
        sa.Column("pipeline_status", sa.String(32), nullable=False, server_default="pending"),
    )
    op.add_column(
        "pipeline_run_states",
        sa.Column("last_completed_stage", sa.String(64), nullable=True),
    )
    # Backfill from existing state_json
    op.execute("""
        UPDATE pipeline_run_states
        SET pipeline_status = COALESCE(state_json ->> 'pipeline_status', 'pending')
    """)
    # Drop the old expression index
    op.drop_index(
        "ix_pipeline_run_states_pipeline_status",
        table_name="pipeline_run_states",
    )
    # Create new B-tree index on the dedicated column (same name)
    op.create_index(
        "ix_pipeline_run_states_pipeline_status",
        "pipeline_run_states",
        ["pipeline_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_run_states_pipeline_status", table_name="pipeline_run_states")
    # Restore expression index
    op.create_index(
        "ix_pipeline_run_states_pipeline_status",
        "pipeline_run_states",
        [sa.text("(state_json ->> 'pipeline_status')")],
    )
    op.drop_column("pipeline_run_states", "last_completed_stage")
    op.drop_column("pipeline_run_states", "pipeline_status")
