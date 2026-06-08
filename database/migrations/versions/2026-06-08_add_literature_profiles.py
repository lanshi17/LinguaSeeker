"""add_literature_profiles

Add the literature_profiles table: a document-level aggregated read model
for literature evidence (CQRS read side).

Revision ID: lit_profiles_20260608
Revises: 6a8f3b1c2d4e
Create Date: 2026-06-08 16:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "lit_profiles_20260608"
down_revision: Union[str, None] = "6a8f3b1c2d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── literature_profiles ──────────────────────────────────────────────
    op.create_table(
        "literature_profiles",
        sa.Column(
            "literature_profile_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("pmid", sa.Text(), nullable=True),
        sa.Column("doi", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column(
            "authors",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("journal", sa.Text(), nullable=True),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column(
            "evidence_groups",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "review_status",
            sa.String(32),
            nullable=False,
            server_default="provisional",
        ),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "overall_confidence",
            sa.Numeric(5, 4),
            nullable=True,
        ),
        sa.Column(
            "total_evidence_fields",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "found_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "not_found_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "latest_processing_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
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
            onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "literature_profile_id",
            name=op.f("pk_literature_profiles"),
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_documents.source_document_id"],
            name=op.f("fk_literature_profiles_source_document_id_source_documents"),
        ),
        sa.UniqueConstraint(
            "source_document_id",
            name=op.f("uq_literature_profiles_source_document_id"),
        ),
    )

    # ── Indexes ──────────────────────────────────────────────────────────
    op.create_index(
        "ix_literature_profiles_pmid",
        "literature_profiles",
        ["pmid"],
    )
    op.create_index(
        "ix_literature_profiles_doi",
        "literature_profiles",
        ["doi"],
    )
    op.create_index(
        "ix_literature_profiles_evidence_groups_gin",
        "literature_profiles",
        ["evidence_groups"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_literature_profiles_review_status",
        "literature_profiles",
        ["review_status"],
    )


def downgrade() -> None:
    op.drop_table("literature_profiles")
