"""Add reviewed_unmappable to normalized_entities.standardization_status.

Revision ID: reviewed_unmappable_20260608
Revises: rm_canonical_fk_20260608
"""
from __future__ import annotations

from alembic import op

revision = "reviewed_unmappable_20260608"
down_revision = "rm_canonical_fk_20260608"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # standardization_status is a plain String(32), not a PostgreSQL ENUM.
    # No DDL change needed -- the column already accepts any string.
    # Recreate the partial unique index for 'unmapped' (idempotent).
    op.drop_index(
        "uq_normalized_entities_unmapped_raw_text",
        table_name="normalized_entities",
    )
    op.create_index(
        "uq_normalized_entities_unmapped_raw_text",
        "normalized_entities",
        ["entity_type", "normalized_raw_text"],
        unique=True,
        postgresql_where="standardization_status = 'unmapped'",
    )
    # Add a new partial unique index for 'reviewed_unmappable'
    op.create_index(
        "uq_normalized_entities_reviewed_unmappable_raw_text",
        "normalized_entities",
        ["entity_type", "normalized_raw_text"],
        unique=True,
        postgresql_where="standardization_status = 'reviewed_unmappable'",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_normalized_entities_reviewed_unmappable_raw_text",
        table_name="normalized_entities",
    )
