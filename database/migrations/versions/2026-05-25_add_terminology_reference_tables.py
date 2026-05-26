"""add terminology reference tables

Revision ID: add_terminology_20260525
Revises: 4a82b5793055
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "add_terminology_20260525"
down_revision: Union[str, None] = "4a82b5793055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "terminology_entries",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("source_db", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("entry_id", name=op.f("pk_terminology_entries")),
        sa.UniqueConstraint("source_db", "external_id", name=op.f("uq_terminology_entries_source_external_id")),
    )
    op.create_index(
        "ix_terminology_entries_entity_type_normalized_name",
        "terminology_entries",
        ["entity_type", "normalized_name"],
        unique=False,
    )
    op.create_index("ix_terminology_entries_source_db", "terminology_entries", ["source_db"], unique=False)

    op.create_table(
        "terminology_aliases",
        sa.Column("alias_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("alias_text", sa.Text(), nullable=False),
        sa.Column("normalized_alias", sa.Text(), nullable=False),
        sa.Column("alias_type", sa.String(length=64), nullable=False),
        sa.Column("source_db", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["entry_id"], ["terminology_entries.entry_id"], name=op.f("fk_terminology_aliases_entry_id")),
        sa.PrimaryKeyConstraint("alias_id", name=op.f("pk_terminology_aliases")),
        sa.UniqueConstraint(
            "entry_id",
            "normalized_alias",
            "alias_type",
            name=op.f("uq_terminology_aliases_entry_alias_type"),
        ),
    )
    op.create_index(
        "ix_terminology_aliases_lookup",
        "terminology_aliases",
        ["entity_type", "normalized_alias"],
        unique=False,
    )
    op.create_index("ix_terminology_aliases_entry_id", "terminology_aliases", ["entry_id"], unique=False)

    op.create_table(
        "terminology_relationships",
        sa.Column("relationship_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("relationship_type", sa.String(length=96), nullable=False),
        sa.Column("source_db", sa.String(length=64), nullable=False),
        sa.Column("evidence_level", sa.String(length=96), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["object_entry_id"],
            ["terminology_entries.entry_id"],
            name=op.f("fk_terminology_relationships_object_entry_id"),
        ),
        sa.ForeignKeyConstraint(
            ["subject_entry_id"],
            ["terminology_entries.entry_id"],
            name=op.f("fk_terminology_relationships_subject_entry_id"),
        ),
        sa.PrimaryKeyConstraint("relationship_id", name=op.f("pk_terminology_relationships")),
        sa.UniqueConstraint(
            "subject_entry_id",
            "object_entry_id",
            "relationship_type",
            "source_db",
            name=op.f("uq_terminology_relationships_identity"),
        ),
    )
    op.create_index(
        "ix_terminology_relationships_subject_type",
        "terminology_relationships",
        ["subject_entry_id", "relationship_type"],
        unique=False,
    )
    op.create_index(
        "ix_terminology_relationships_object_type",
        "terminology_relationships",
        ["object_entry_id", "relationship_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_terminology_relationships_object_type", table_name="terminology_relationships")
    op.drop_index("ix_terminology_relationships_subject_type", table_name="terminology_relationships")
    op.drop_table("terminology_relationships")
    op.drop_index("ix_terminology_aliases_entry_id", table_name="terminology_aliases")
    op.drop_index("ix_terminology_aliases_lookup", table_name="terminology_aliases")
    op.drop_table("terminology_aliases")
    op.drop_index("ix_terminology_entries_source_db", table_name="terminology_entries")
    op.drop_index("ix_terminology_entries_entity_type_normalized_name", table_name="terminology_entries")
    op.drop_table("terminology_entries")
