"""add terminology embeddings pgvector table

Revision ID: add_term_embed_20260525
Revises: add_terminology_20260525
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "add_term_embed_20260525"
down_revision: Union[str, None] = "add_terminology_20260525"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.create_index(
        "ix_terminology_embeddings_entity_type_model",
        "terminology_embeddings",
        ["entity_type", "embedding_model"],
        unique=False,
    )
    op.create_index(
        "ix_terminology_embeddings_entry_id",
        "terminology_embeddings",
        ["entry_id"],
        unique=False,
    )
    op.create_index(
        "ix_terminology_embeddings_embedding_hnsw",
        "terminology_embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_terminology_embeddings_embedding_hnsw", table_name="terminology_embeddings")
    op.drop_index("ix_terminology_embeddings_entry_id", table_name="terminology_embeddings")
    op.drop_index("ix_terminology_embeddings_entity_type_model", table_name="terminology_embeddings")
    op.drop_table("terminology_embeddings")
