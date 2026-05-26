"""add terminology relationship identity unique constraint

Revision ID: add_term_rel_id_20260526
Revises: add_terminology_20260525
Create Date: 2026-05-26
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "add_term_rel_id_20260526"
down_revision: Union[str, None] = "add_terminology_20260525"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_terminology_relationships_identity",
        "terminology_relationships",
        ["subject_entry_id", "object_entry_id", "relationship_type", "source_db"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_terminology_relationships_identity",
        "terminology_relationships",
        type_="unique",
    )
