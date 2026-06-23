"""Repair missing Phase 3 runtime tables in stamped databases.

Revision ID: repair_phase3_schema_20260623
Revises: doc_cache_20260622
Create Date: 2026-06-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision = "repair_phase3_schema_20260623"
down_revision = "doc_cache_20260622"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    return bool(conn.execute(sa.text(
        "SELECT EXISTS ("
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = current_schema() AND table_name = :table_name"
        ")",
    ), {"table_name": table_name}).scalar())


def _index_exists(index_name: str) -> bool:
    conn = op.get_bind()
    return bool(conn.execute(sa.text(
        "SELECT EXISTS ("
        "SELECT 1 FROM pg_indexes "
        "WHERE schemaname = current_schema() AND indexname = :index_name"
        ")",
    ), {"index_name": index_name}).scalar())


def _create_index_if_missing(index_name: str, table_name: str, columns, **kwargs) -> None:
    if not _index_exists(index_name):
        op.create_index(index_name, table_name, columns, **kwargs)


def _create_terminology_embeddings() -> None:
    if not _table_exists("terminology_embeddings"):
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.create_table(
            "terminology_embeddings",
            sa.Column("embedding_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=False),
            sa.Column("source_db", sa.String(length=64), nullable=False),
            sa.Column("external_id", sa.String(length=255), nullable=False),
            sa.Column("embedding_text", sa.Text(), nullable=False),
            sa.Column("embedding_text_hash", sa.String(length=64), nullable=False),
            sa.Column("embedding_model", sa.String(length=255), nullable=False),
            sa.Column("embedding", Vector(1024), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ["entry_id"],
                ["terminology_entries.entry_id"],
                name=op.f("fk_terminology_embeddings_entry_id"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("embedding_id", name=op.f("pk_terminology_embeddings")),
            sa.UniqueConstraint(
                "entry_id",
                "embedding_text_hash",
                "embedding_model",
                name=op.f("uq_terminology_embeddings_entry_text_model"),
            ),
        )

    _create_index_if_missing(
        "ix_terminology_embeddings_entity_type_model",
        "terminology_embeddings",
        ["entity_type", "embedding_model"],
    )
    _create_index_if_missing(
        "ix_terminology_embeddings_entry_id",
        "terminology_embeddings",
        ["entry_id"],
    )
    _create_index_if_missing(
        "ix_terminology_embeddings_embedding_hnsw",
        "terminology_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def _create_frontend_search_index() -> None:
    if not _table_exists("frontend_search_index"):
        op.create_table(
            "frontend_search_index",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("canonical_evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("pmid", sa.Text(), nullable=True),
            sa.Column("doi", sa.Text(), nullable=True),
            sa.Column("gene_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("variant_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("entity_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("field_id", sa.String(length=128), nullable=False),
            sa.Column("review_status", sa.String(length=32), nullable=False),
            sa.Column("current_best_confidence", sa.Numeric(5, 4), nullable=True),
            sa.Column("search_text", sa.Text(), nullable=False, server_default=sa.text("''")),
            sa.Column("active_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_frontend_search_index")),
        )

    _create_index_if_missing(
        "ix_frontend_search_index_canonical_evidence_id",
        "frontend_search_index",
        ["canonical_evidence_id"],
        unique=True,
    )
    _create_index_if_missing("ix_frontend_search_index_pmid", "frontend_search_index", ["pmid"])
    _create_index_if_missing("ix_frontend_search_index_doi", "frontend_search_index", ["doi"])
    _create_index_if_missing(
        "ix_frontend_search_index_gene_ids",
        "frontend_search_index",
        ["gene_ids"],
        postgresql_using="gin",
    )
    _create_index_if_missing(
        "ix_frontend_search_index_variant_ids",
        "frontend_search_index",
        ["variant_ids"],
        postgresql_using="gin",
    )


def upgrade() -> None:
    _create_terminology_embeddings()
    _create_frontend_search_index()


def downgrade() -> None:
    # Repair migration is intentionally non-destructive on downgrade because it
    # may be applied to databases where these tables were created by older
    # migrations or manual recovery.
    pass
