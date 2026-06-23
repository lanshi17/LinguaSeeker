"""Add original_blocks and translated_blocks JSONB columns to source_documents.

Stores Phase 2 structured block output (ContentBlock dicts) so the evidence
detail API can render documents with proper formatting (headings, tables,
lists, figures) instead of plain concatenated text.

Revision ID: content_blocks_20260623
Revises: doc_text_20260623
Create Date: 2026-06-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "content_blocks_20260623"
down_revision = "doc_text_20260623"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_documents", sa.Column("original_blocks", JSONB, nullable=True))
    op.add_column("source_documents", sa.Column("translated_blocks", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("source_documents", "translated_blocks")
    op.drop_column("source_documents", "original_blocks")
