"""add NULLS NOT DISTINCT to terminology_relationships identity constraint

Revision ID: add_nulls_distinct_20260527
Revises: add_term_embed_20260525
Create Date: 2026-05-27
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "add_nulls_distinct_20260527"
down_revision: Union[str, None] = "add_term_embed_20260525"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_terminology_relationships_identity",
        "terminology_relationships",
        type_="unique",
    )
    op.execute(
        "ALTER TABLE terminology_relationships "
        "ADD CONSTRAINT uq_terminology_relationships_identity "
        "UNIQUE NULLS NOT DISTINCT "
        "(subject_entry_id, object_entry_id, relationship_type, source_db)"
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_terminology_relationships_identity",
        "terminology_relationships",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_terminology_relationships_identity",
        "terminology_relationships",
        ["subject_entry_id", "object_entry_id", "relationship_type", "source_db"],
    )
