"""Add M0 request/paper orchestration tables.

Revision ID: 20260303_01
Revises: 20260227_01
Create Date: 2026-03-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "20260303_01"
down_revision = "20260227_01"
branch_labels = None
depends_on = None


def _ensure_task_requests(inspector) -> None:
    if "task_requests" in inspector.get_table_names():
        return
    op.create_table(
        "task_requests",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("task_form_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_task_requests_status", "task_requests", ["status"])


def _ensure_paper_tasks(inspector) -> None:
    if "paper_tasks" in inspector.get_table_names():
        return
    op.create_table(
        "paper_tasks",
        sa.Column("paper_task_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("task_requests.request_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.document_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.String(length=500), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued"),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column(
            "duplicate_of",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("paper_tasks.paper_task_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("celery_task_id", sa.String(length=100), nullable=True),
        sa.Column("fulltext_unavailable", sa.String(length=10), nullable=False, server_default="false"),
        sa.Column("warning_codes", postgresql.JSONB(), nullable=True),
        sa.Column("node_trace", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_paper_tasks_request_id", "paper_tasks", ["request_id"])
    op.create_index("ix_paper_tasks_status", "paper_tasks", ["status"])
    op.create_index("ix_paper_tasks_file_hash", "paper_tasks", ["file_hash"])
    op.create_index("ix_paper_tasks_celery_task_id", "paper_tasks", ["celery_task_id"])


def _ensure_paper_task_logs(inspector) -> None:
    if "paper_task_logs" in inspector.get_table_names():
        return
    op.create_table(
        "paper_task_logs",
        sa.Column("log_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "paper_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("paper_tasks.paper_task_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("node", sa.String(length=50), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_paper_task_logs_paper_task_id", "paper_task_logs", ["paper_task_id"])
    op.create_index("ix_paper_task_logs_status", "paper_task_logs", ["status"])


def _ensure_sentence_alignments(inspector) -> None:
    if "sentence_alignments" in inspector.get_table_names():
        return
    op.create_table(
        "sentence_alignments",
        sa.Column("alignment_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "paper_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("paper_tasks.paper_task_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_sentence", sa.Text(), nullable=False),
        sa.Column("en_sentence", sa.Text(), nullable=False),
        sa.Column("source_start", sa.Integer(), nullable=True),
        sa.Column("source_end", sa.Integer(), nullable=True),
        sa.Column("en_start", sa.Integer(), nullable=True),
        sa.Column("en_end", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sentence_alignments_paper_task_id", "sentence_alignments", ["paper_task_id"])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    _ensure_task_requests(inspector)
    _ensure_paper_tasks(inspector)
    _ensure_paper_task_logs(inspector)
    _ensure_sentence_alignments(inspector)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "sentence_alignments" in tables:
        op.drop_index("ix_sentence_alignments_paper_task_id", table_name="sentence_alignments")
        op.drop_table("sentence_alignments")

    if "paper_task_logs" in tables:
        op.drop_index("ix_paper_task_logs_status", table_name="paper_task_logs")
        op.drop_index("ix_paper_task_logs_paper_task_id", table_name="paper_task_logs")
        op.drop_table("paper_task_logs")

    if "paper_tasks" in tables:
        op.drop_index("ix_paper_tasks_celery_task_id", table_name="paper_tasks")
        op.drop_index("ix_paper_tasks_file_hash", table_name="paper_tasks")
        op.drop_index("ix_paper_tasks_status", table_name="paper_tasks")
        op.drop_index("ix_paper_tasks_request_id", table_name="paper_tasks")
        op.drop_table("paper_tasks")

    if "task_requests" in tables:
        op.drop_index("ix_task_requests_status", table_name="task_requests")
        op.drop_table("task_requests")
