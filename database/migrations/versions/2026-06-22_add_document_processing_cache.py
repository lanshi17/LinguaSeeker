"""Add document_processing_cache table for L2 PostgreSQL result caching.

Stores the final PipelineGraphState as JSONB keyed by a content hash, so
re-submission of an identical document (same bytes or same source key +
extraction target scope) returns the prior completed result without
re-running the pipeline. The L1 cache is Redis; this table is the L2
durable fallback.

Revision ID: doc_cache_20260622
Revises: variant_internal_id_20260621
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "doc_cache_20260622"
down_revision = "variant_internal_id_20260621"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_processing_cache",
        sa.Column("cache_id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=True),
        sa.Column("processing_run_id", sa.UUID(), nullable=False),
        sa.Column("result_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["processing_run_id"], ["source_documents.source_document_id"]),
        sa.PrimaryKeyConstraint("cache_id"),
        sa.UniqueConstraint("content_hash", name="uq_document_processing_cache_content_hash"),
    )
    op.create_index(
        "ix_document_processing_cache_created_at",
        "document_processing_cache",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_processing_cache_created_at", table_name="document_processing_cache")
    op.drop_table("document_processing_cache")
