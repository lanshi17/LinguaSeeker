"""Add task_logs table and missing_fields_detail column.

Revision ID: 20260227_01
Revises: 20260226_01
Create Date: 2026-02-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "20260227_01"
down_revision = "20260226_01"
branch_labels = None
depends_on = None


def _ensure_task_logs(inspector) -> None:
    tables = inspector.get_table_names()
    if "task_logs" in tables:
        columns = {col["name"] for col in inspector.get_columns("task_logs")}
        if "missing_fields_detail" not in columns:
            op.add_column(
                "task_logs",
                sa.Column("missing_fields_detail", postgresql.JSONB(), nullable=True),
            )
        index_names = {idx["name"] for idx in inspector.get_indexes("task_logs")}
        if "idx_task_logs_document_id" not in index_names:
            op.create_index(
                "idx_task_logs_document_id",
                "task_logs",
                ["document_id"],
            )
        if "idx_task_logs_status" not in index_names:
            op.create_index(
                "idx_task_logs_status",
                "task_logs",
                ["status"],
            )
        return

    op.create_table(
        "task_logs",
        sa.Column("log_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.task_id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("missing_fields_detail", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_task_logs_document_id",
        "task_logs",
        ["document_id"],
    )
    op.create_index(
        "idx_task_logs_status",
        "task_logs",
        ["status"],
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    _ensure_task_logs(inspector)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    if "task_logs" in tables:
        op.drop_index("idx_task_logs_status", table_name="task_logs")
        op.drop_index("idx_task_logs_document_id", table_name="task_logs")
        op.drop_table("task_logs")
