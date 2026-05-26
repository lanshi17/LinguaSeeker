"""enable pgvector and embeddings

Revision ID: enable_pgvector_20260525
Revises: add_terminology_20260525
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "enable_pgvector_20260525"
down_revision: Union[str, None] = "add_terminology_20260525"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "terminology_embeddings",
        sa.Column("embedding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("terminology_entries.entry_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("embedding_id", name=op.f("pk_terminology_embeddings")),
        sa.UniqueConstraint("entry_id", "model_version", name=op.f("uq_terminology_embeddings_entry_model")),
    )

    op.create_index(
        "ix_terminology_embeddings_hnsw",
        "terminology_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 200},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_terminology_embeddings_entity_type",
        "terminology_embeddings",
        ["entity_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_terminology_embeddings_entity_type", table_name="terminology_embeddings")
    op.drop_index("ix_terminology_embeddings_hnsw", table_name="terminology_embeddings")
    op.drop_constraint("uq_terminology_embeddings_entry_model", "terminology_embeddings")
    op.drop_table("terminology_embeddings")
