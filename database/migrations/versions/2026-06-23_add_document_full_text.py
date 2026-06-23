"""Add original_text and translated_text columns to source_documents.

Stores Phase 2 full-text output (original-language and translated English)
directly in the database so the evidence detail API can serve document text
without reading JSON files from disk.

Revision ID: doc_text_20260623
Revises: repair_phase3_schema_20260623
Create Date: 2026-06-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "doc_text_20260623"
down_revision = "repair_phase3_schema_20260623"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_documents", sa.Column("original_text", sa.Text(), nullable=True))
    op.add_column("source_documents", sa.Column("translated_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_documents", "translated_text")
    op.drop_column("source_documents", "original_text")
