"""Add pipeline_jobs table for persistent job queue.

Replaces the in-memory asyncio.create_task approach with a PostgreSQL-backed
queue that guarantees at-most-one running job via SELECT FOR UPDATE SKIP LOCKED.
Jobs survive server restarts and can be retried.

Revision ID: pipeline_jobs_20260625
Revises: doc_ann_20260623
Create Date: 2026-06-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "pipeline_jobs_20260625"
down_revision = "doc_ann_20260623"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_jobs",
        sa.Column("job_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("processing_run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("request_data", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("worker_id", sa.String(128), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_pipeline_jobs_status",
        ),
    )
    op.create_index(
        "ix_pipeline_jobs_status_priority",
        "pipeline_jobs",
        ["status", "priority", "created_at"],
    )
    op.create_index(
        "ix_pipeline_jobs_processing_run_id",
        "pipeline_jobs",
        ["processing_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_jobs_processing_run_id", table_name="pipeline_jobs")
    op.drop_index("ix_pipeline_jobs_status_priority", table_name="pipeline_jobs")
    op.drop_table("pipeline_jobs")
