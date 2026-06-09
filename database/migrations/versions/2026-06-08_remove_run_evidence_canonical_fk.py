"""Remove dead canonical_evidence_id FK from run_evidence_items.

Revision ID: rm_canonical_fk_20260608
Revises: lit_profiles_20260608
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "rm_canonical_fk_20260608"
down_revision = "lit_profiles_20260608"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "ix_run_evidence_items_canonical_evidence_id",
        table_name="run_evidence_items",
    )
    op.drop_column("run_evidence_items", "canonical_evidence_id")


def downgrade() -> None:
    op.add_column(
        "run_evidence_items",
        sa.Column("canonical_evidence_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "ix_run_evidence_items_canonical_evidence_id",
        "run_evidence_items",
        ["canonical_evidence_id"],
    )
    op.create_foreign_key(
        "fk_run_evidence_items_canonical_evidence_id",
        "run_evidence_items",
        "canonical_evidence_items",
        ["canonical_evidence_id"],
        ["canonical_evidence_id"],
    )
