"""add account scopes for task and evidence isolation

Revision ID: account_scopes_20260709
Revises: chat_session_title_20260705
Create Date: 2026-07-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "account_scopes_20260709"
down_revision: Union[str, None] = "chat_session_title_20260705"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_owner_column(table_name: str) -> None:
    """Add nullable owner_user_id and FK to a table."""
    op.add_column(
        table_name,
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f(f"fk_{table_name}_owner_user_id_users"),
        table_name,
        "users",
        ["owner_user_id"],
        ["user_id"],
    )


def _drop_existing_unique_constraint(table_name: str, candidate_names: Sequence[str]) -> None:
    """Drop the first matching unique constraint from historical schemas."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = to_regclass(:table_name)::oid
              AND contype = 'u'
              AND conname = ANY(:candidate_names)
            ORDER BY array_position(:candidate_names, conname)
            LIMIT 1
            """
        ),
        {
            "table_name": table_name,
            "candidate_names": list(candidate_names),
        },
    )
    constraint_name = result.scalar_one_or_none()
    if constraint_name is not None:
        op.drop_constraint(constraint_name, table_name, type_="unique")


def upgrade() -> None:
    """Add owner scope columns and scoped uniqueness."""
    op.drop_constraint(op.f("uq_users_email"), "users", type_="unique")
    op.alter_column(
        "users",
        "email",
        new_column_name="username",
        existing_type=sa.String(length=320),
        existing_nullable=False,
    )
    op.create_unique_constraint(op.f("uq_users_username"), "users", ["username"])

    _add_owner_column("processing_runs")
    op.create_index(
        "ix_processing_runs_owner_created",
        "processing_runs",
        ["owner_user_id", sa.text("created_at DESC")],
    )

    _add_owner_column("pipeline_run_states")
    op.drop_index("ux_pipeline_run_states_active_source_key", table_name="pipeline_run_states")
    op.execute(
        """
        CREATE UNIQUE INDEX ux_pipeline_run_states_active_source_key
        ON pipeline_run_states (owner_user_id, source_key) NULLS NOT DISTINCT
        WHERE source_key IS NOT NULL AND pipeline_status IN ('pending', 'running')
        """
    )
    op.create_index(
        "ix_pipeline_run_states_owner_created",
        "pipeline_run_states",
        ["owner_user_id", sa.text("created_at DESC")],
    )

    _add_owner_column("pipeline_jobs")
    op.create_index(
        "ix_pipeline_jobs_owner_status",
        "pipeline_jobs",
        ["owner_user_id", "status", "created_at"],
    )

    _add_owner_column("run_evidence_items")
    op.create_index(
        "ix_run_evidence_items_owner_document",
        "run_evidence_items",
        ["owner_user_id", "source_document_id"],
    )

    _add_owner_column("canonical_evidence_items")
    op.drop_constraint(
        op.f("uq_canonical_evidence_items_identity"),
        "canonical_evidence_items",
        type_="unique",
    )
    op.execute(
        """
        ALTER TABLE canonical_evidence_items
        ADD CONSTRAINT uq_canonical_evidence_items_identity
        UNIQUE NULLS NOT DISTINCT (
            source_document_id,
            owner_user_id,
            field_id,
            position_hash,
            entity_scope_hash
        )
        """
    )
    op.create_index(
        "ix_canonical_evidence_items_owner_document",
        "canonical_evidence_items",
        ["owner_user_id", "source_document_id"],
    )

    _add_owner_column("literature_profiles")
    _drop_existing_unique_constraint(
        "literature_profiles",
        (
            op.f("uq_literature_profiles_source_document_id"),
            "literature_profiles_source_document_id_key",
        ),
    )
    op.execute(
        """
        ALTER TABLE literature_profiles
        ADD CONSTRAINT uq_literature_profiles_document_owner
        UNIQUE NULLS NOT DISTINCT (source_document_id, owner_user_id)
        """
    )
    op.create_index(
        "ix_literature_profiles_owner_updated",
        "literature_profiles",
        ["owner_user_id", sa.text("updated_at DESC")],
    )

    _add_owner_column("document_annotations")
    op.create_index(
        "ix_document_annotations_owner_doc_track",
        "document_annotations",
        ["owner_user_id", "source_document_id", "track"],
    )

    _add_owner_column("frontend_search_index")
    op.create_index(
        "ix_frontend_search_index_owner_pmid",
        "frontend_search_index",
        ["owner_user_id", "pmid"],
    )


def downgrade() -> None:
    """Remove owner scope columns and scoped uniqueness."""
    op.drop_index("ix_frontend_search_index_owner_pmid", table_name="frontend_search_index")
    op.drop_constraint(op.f("fk_frontend_search_index_owner_user_id_users"), "frontend_search_index", type_="foreignkey")
    op.drop_column("frontend_search_index", "owner_user_id")

    op.drop_index("ix_document_annotations_owner_doc_track", table_name="document_annotations")
    op.drop_constraint(op.f("fk_document_annotations_owner_user_id_users"), "document_annotations", type_="foreignkey")
    op.drop_column("document_annotations", "owner_user_id")

    op.drop_index("ix_literature_profiles_owner_updated", table_name="literature_profiles")
    op.drop_constraint("uq_literature_profiles_document_owner", "literature_profiles", type_="unique")
    op.create_unique_constraint(
        op.f("uq_literature_profiles_source_document_id"),
        "literature_profiles",
        ["source_document_id"],
    )
    op.drop_constraint(op.f("fk_literature_profiles_owner_user_id_users"), "literature_profiles", type_="foreignkey")
    op.drop_column("literature_profiles", "owner_user_id")

    op.drop_index("ix_canonical_evidence_items_owner_document", table_name="canonical_evidence_items")
    op.drop_constraint("uq_canonical_evidence_items_identity", "canonical_evidence_items", type_="unique")
    op.create_unique_constraint(
        op.f("uq_canonical_evidence_items_identity"),
        "canonical_evidence_items",
        ["source_document_id", "field_id", "position_hash", "entity_scope_hash"],
    )
    op.drop_constraint(
        op.f("fk_canonical_evidence_items_owner_user_id_users"),
        "canonical_evidence_items",
        type_="foreignkey",
    )
    op.drop_column("canonical_evidence_items", "owner_user_id")

    op.drop_index("ix_run_evidence_items_owner_document", table_name="run_evidence_items")
    op.drop_constraint(op.f("fk_run_evidence_items_owner_user_id_users"), "run_evidence_items", type_="foreignkey")
    op.drop_column("run_evidence_items", "owner_user_id")

    op.drop_index("ix_pipeline_jobs_owner_status", table_name="pipeline_jobs")
    op.drop_constraint(op.f("fk_pipeline_jobs_owner_user_id_users"), "pipeline_jobs", type_="foreignkey")
    op.drop_column("pipeline_jobs", "owner_user_id")

    op.drop_index("ix_pipeline_run_states_owner_created", table_name="pipeline_run_states")
    op.drop_index("ux_pipeline_run_states_active_source_key", table_name="pipeline_run_states")
    op.create_index(
        "ux_pipeline_run_states_active_source_key",
        "pipeline_run_states",
        ["source_key"],
        unique=True,
        postgresql_where=sa.text("source_key IS NOT NULL AND pipeline_status IN ('pending', 'running')"),
    )
    op.drop_constraint(op.f("fk_pipeline_run_states_owner_user_id_users"), "pipeline_run_states", type_="foreignkey")
    op.drop_column("pipeline_run_states", "owner_user_id")

    op.drop_index("ix_processing_runs_owner_created", table_name="processing_runs")
    op.drop_constraint(op.f("fk_processing_runs_owner_user_id_users"), "processing_runs", type_="foreignkey")
    op.drop_column("processing_runs", "owner_user_id")

    op.drop_constraint(op.f("uq_users_username"), "users", type_="unique")
    op.alter_column(
        "users",
        "username",
        new_column_name="email",
        existing_type=sa.String(length=320),
        existing_nullable=False,
    )
    op.create_unique_constraint(op.f("uq_users_email"), "users", ["email"])
