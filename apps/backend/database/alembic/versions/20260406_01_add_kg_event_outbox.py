from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "20260406_01"
down_revision = "20260306_01"
branch_labels = None
depends_on = None


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

    if "kg_events" not in tables:
        op.create_table(
            "kg_events",
            sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("paper_task_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
            sa.Column(
                "payload",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("idempotency_key", name="uq_kg_events_idempotency_key"),
        )
        inspector = inspect(bind)

    _create_index_if_missing(inspector, "kg_events", "ix_kg_events_status", ["status"])
    _create_index_if_missing(
        inspector, "kg_events", "ix_kg_events_paper_task_id", ["paper_task_id"]
    )
    _create_index_if_missing(
        inspector, "kg_events", "ix_kg_events_document_id", ["document_id"]
    )
    _create_index_if_missing(
        inspector, "kg_events", "ix_kg_events_created_at", ["created_at"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "kg_events" not in tables:
        return

    for index_name in (
        "ix_kg_events_created_at",
        "ix_kg_events_document_id",
        "ix_kg_events_paper_task_id",
        "ix_kg_events_status",
    ):
        _drop_index_if_exists(inspector, "kg_events", index_name)

    op.drop_table("kg_events")
