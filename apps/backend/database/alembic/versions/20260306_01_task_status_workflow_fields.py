from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "20260306_01"
down_revision = "20260303_01"
branch_labels = None
depends_on = None


def _add_column_if_missing(inspector, table_name: str, column: sa.Column[Any]) -> None:
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column.name in columns:
        return
    op.add_column(table_name, column)


def _drop_column_if_exists(inspector, table_name: str, column_name: str) -> None:
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column_name in columns:
        op.drop_column(table_name, column_name)


def _create_index_if_missing(
    inspector, table_name: str, index_name: str, columns: list[str]
) -> None:
    index_names = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if index_name in index_names:
        return
    op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(inspector, table_name: str, index_name: str) -> None:
    index_names = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if index_name in index_names:
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "tasks" in tables:
        _add_column_if_missing(
            inspector,
            "tasks",
            sa.Column(
                "workflow_status",
                sa.String(length=80),
                nullable=False,
                server_default="PENDING",
            ),
        )
        _add_column_if_missing(
            inspector,
            "tasks",
            sa.Column("processing_steps", postgresql.JSONB(), nullable=True),
        )
        _add_column_if_missing(
            inspector,
            "tasks",
            sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        )
        _add_column_if_missing(
            inspector,
            "tasks",
            sa.Column("processing_duration_seconds", sa.Float(), nullable=True),
        )
        _add_column_if_missing(
            inspector,
            "tasks",
            sa.Column("error_details", postgresql.JSONB(), nullable=True),
        )
        _create_index_if_missing(
            inspector,
            "tasks",
            "ix_tasks_workflow_status",
            ["workflow_status"],
        )

    if "paper_tasks" in tables:
        _add_column_if_missing(
            inspector,
            "paper_tasks",
            sa.Column(
                "workflow_status",
                sa.String(length=80),
                nullable=False,
                server_default="PENDING",
            ),
        )
        _add_column_if_missing(
            inspector,
            "paper_tasks",
            sa.Column("processing_steps", postgresql.JSONB(), nullable=True),
        )
        _add_column_if_missing(
            inspector,
            "paper_tasks",
            sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        )
        _add_column_if_missing(
            inspector,
            "paper_tasks",
            sa.Column("processing_duration_seconds", sa.Float(), nullable=True),
        )
        _add_column_if_missing(
            inspector,
            "paper_tasks",
            sa.Column("error_details", postgresql.JSONB(), nullable=True),
        )
        _create_index_if_missing(
            inspector,
            "paper_tasks",
            "ix_paper_tasks_workflow_status",
            ["workflow_status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "paper_tasks" in tables:
        _drop_index_if_exists(inspector, "paper_tasks", "ix_paper_tasks_workflow_status")
        for column_name in (
            "error_details",
            "processing_duration_seconds",
            "file_size_bytes",
            "processing_steps",
            "workflow_status",
        ):
            _drop_column_if_exists(inspector, "paper_tasks", column_name)

    if "tasks" in tables:
        _drop_index_if_exists(inspector, "tasks", "ix_tasks_workflow_status")
        for column_name in (
            "error_details",
            "processing_duration_seconds",
            "file_size_bytes",
            "processing_steps",
            "workflow_status",
        ):
            _drop_column_if_exists(inspector, "tasks", column_name)
