"""Add document_annotations table for user text-selection annotations.

Stores per-paragraph character-offset annotations (original/translated track)
so the bilingual reader can persist user highlights and notes.

Revision ID: doc_ann_20260623
Revises: doc_text_20260623
Create Date: 2026-06-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "doc_ann_20260623"
down_revision = "doc_text_20260623"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_annotations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "source_document_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("source_documents.source_document_id"),
            nullable=False,
        ),
        sa.Column("track", sa.String(length=16), nullable=False),
        sa.Column("paragraph_id", sa.String(length=128), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=128), nullable=True),
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
        sa.CheckConstraint(
            "end_offset > start_offset AND start_offset >= 0",
            name="ck_document_annotations_offsets_valid",
        ),
    )
    op.create_index(
        "ix_document_annotations_doc_track",
        "document_annotations",
        ["source_document_id", "track"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_annotations_doc_track", table_name="document_annotations")
    op.drop_table("document_annotations")
