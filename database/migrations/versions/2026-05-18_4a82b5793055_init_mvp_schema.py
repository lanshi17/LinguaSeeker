"""init MVP schema

Revision ID: 4a82b5793055
Revises:
Create Date: 2026-05-18 10:01:16.480757+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4a82b5793055"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
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
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    # ── source_documents ─────────────────────────────────────────────────
    op.create_table(
        "source_documents",
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.PrimaryKeyConstraint("source_document_id", name=op.f("pk_source_documents")),
    )

    # ── source_document_identifiers ──────────────────────────────────────
    op.create_table(
        "source_document_identifiers",
        sa.Column(
            "source_document_identifier_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("identifier_type", sa.String(64), nullable=False),
        sa.Column("identifier_value", sa.Text(), nullable=False),
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
            "source_document_identifier_id",
            name=op.f("pk_source_document_identifiers"),
        ),
        sa.UniqueConstraint(
            "identifier_type",
            "identifier_value",
            name=op.f("uq_source_document_identifiers_type_value"),
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_documents.source_document_id"],
            name=op.f("fk_source_document_identifiers_source_document_id"),
        ),
    )
    op.create_index(
        "ix_source_document_identifiers_source_document_id",
        "source_document_identifiers",
        ["source_document_id"],
    )

    # ── processing_runs ──────────────────────────────────────────────────
    op.create_table(
        "processing_runs",
        sa.Column("processing_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("parser_version", sa.String(128), nullable=True),
        sa.Column("translation_version", sa.String(128), nullable=True),
        sa.Column("extraction_version", sa.String(128), nullable=True),
        sa.Column("standardization_version", sa.String(128), nullable=True),
        sa.Column("fusion_version", sa.String(128), nullable=True),
        sa.Column("prompt_hash", sa.String(128), nullable=True),
        sa.Column("model_hash", sa.String(128), nullable=True),
        sa.Column("config_hash", sa.String(128), nullable=True),
        sa.Column(
            "input_artifacts",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "output_artifacts",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "run_status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("processing_run_id", name=op.f("pk_processing_runs")),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_documents.source_document_id"],
            name=op.f("fk_processing_runs_source_document_id"),
        ),
    )
    op.create_index(
        "ix_processing_runs_source_document_id",
        "processing_runs",
        ["source_document_id"],
    )

    # ── Add use_alter FK: source_documents.latest_processing_run_id ──────
    op.create_foreign_key(
        op.f("fk_source_documents_latest_processing_run_id"),
        "source_documents",
        "processing_runs",
        ["latest_processing_run_id"],
        ["processing_run_id"],
        use_alter=True,
    )

    # ── normalized_entities ──────────────────────────────────────────────
    op.create_table(
        "normalized_entities",
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("normalized_raw_text", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "aliases",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "standardization_status",
            sa.String(32),
            nullable=False,
            server_default="unmapped",
        ),
        sa.Column(
            "merged_into_entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.PrimaryKeyConstraint("entity_id", name=op.f("pk_normalized_entities")),
        sa.ForeignKeyConstraint(
            ["merged_into_entity_id"],
            ["normalized_entities.entity_id"],
            name=op.f("fk_normalized_entities_merged_into_entity_id"),
        ),
    )
    op.create_index(
        "uq_normalized_entities_standardized_external_id",
        "normalized_entities",
        ["entity_type", "external_id"],
        unique=True,
        postgresql_where=sa.text(
            "external_id IS NOT NULL AND standardization_status = 'standardized'"
        ),
    )
    op.create_index(
        "uq_normalized_entities_unmapped_raw_text",
        "normalized_entities",
        ["entity_type", "normalized_raw_text"],
        unique=True,
        postgresql_where=sa.text("standardization_status = 'unmapped'"),
    )
    op.create_index(
        "ix_normalized_entities_merged_into_entity_id",
        "normalized_entities",
        ["merged_into_entity_id"],
    )

    # ── entity_merge_events ──────────────────────────────────────────────
    op.create_table(
        "entity_merge_events",
        sa.Column(
            "entity_merge_event_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "from_entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "to_entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("merge_reason", sa.Text(), nullable=False),
        sa.Column(
            "merged_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "merged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint(
            "entity_merge_event_id",
            name=op.f("pk_entity_merge_events"),
        ),
        sa.ForeignKeyConstraint(
            ["from_entity_id"],
            ["normalized_entities.entity_id"],
            name=op.f("fk_entity_merge_events_from_entity_id"),
        ),
        sa.ForeignKeyConstraint(
            ["to_entity_id"],
            ["normalized_entities.entity_id"],
            name=op.f("fk_entity_merge_events_to_entity_id"),
        ),
        sa.ForeignKeyConstraint(
            ["merged_by_user_id"],
            ["users.user_id"],
            name=op.f("fk_entity_merge_events_merged_by_user_id"),
        ),
    )
    op.create_index(
        "ix_entity_merge_events_from_entity_id",
        "entity_merge_events",
        ["from_entity_id"],
    )
    op.create_index(
        "ix_entity_merge_events_to_entity_id",
        "entity_merge_events",
        ["to_entity_id"],
    )

    # ── canonical_evidence_items ─────────────────────────────────────────
    op.create_table(
        "canonical_evidence_items",
        sa.Column(
            "canonical_evidence_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("field_id", sa.String(128), nullable=False),
        sa.Column("position_hash", sa.String(128), nullable=False),
        sa.Column("text_hash", sa.String(128), nullable=False),
        sa.Column("entity_scope_hash", sa.String(128), nullable=False),
        sa.Column(
            "current_best_run_evidence_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("current_best_status", sa.String(32), nullable=False),
        sa.Column(
            "conflict_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "active_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "review_status",
            sa.String(32),
            nullable=False,
            server_default="provisional",
        ),
        sa.Column(
            "current_best_confidence",
            sa.Numeric(5, 4),
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
            "canonical_evidence_id",
            name=op.f("pk_canonical_evidence_items"),
        ),
        sa.UniqueConstraint(
            "source_document_id",
            "field_id",
            "position_hash",
            "entity_scope_hash",
            name=op.f("uq_canonical_evidence_items_identity"),
        ),
        sa.CheckConstraint(
            "current_best_confidence >= 0 AND current_best_confidence <= 1",
            name=op.f("ck_canonical_evidence_items_current_best_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_documents.source_document_id"],
            name=op.f("fk_canonical_evidence_items_source_document_id"),
        ),
    )
    op.create_index(
        "ix_canonical_evidence_items_source_document_id",
        "canonical_evidence_items",
        ["source_document_id"],
    )
    op.create_index(
        "ix_canonical_evidence_items_current_best_run_evidence_id",
        "canonical_evidence_items",
        ["current_best_run_evidence_id"],
    )

    # ── run_evidence_items ───────────────────────────────────────────────
    op.create_table(
        "run_evidence_items",
        sa.Column(
            "run_evidence_item_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "processing_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("track", sa.String(32), nullable=False),
        sa.Column("field_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "value",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("position_hash", sa.String(128), nullable=False),
        sa.Column("text_hash", sa.String(128), nullable=False),
        sa.Column(
            "source_span",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("entity_scope_hash", sa.String(128), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "canonical_evidence_id",
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
            "run_evidence_item_id",
            name=op.f("pk_run_evidence_items"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_run_evidence_items_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.processing_run_id"],
            name=op.f("fk_run_evidence_items_processing_run_id"),
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_documents.source_document_id"],
            name=op.f("fk_run_evidence_items_source_document_id"),
        ),
    )
    op.create_index(
        "ix_run_evidence_items_processing_run_id",
        "run_evidence_items",
        ["processing_run_id"],
    )
    op.create_index(
        "ix_run_evidence_items_source_document_id",
        "run_evidence_items",
        ["source_document_id"],
    )
    op.create_index(
        "ix_run_evidence_items_canonical_evidence_id",
        "run_evidence_items",
        ["canonical_evidence_id"],
    )

    # ── use_alter FKs for circular references ────────────────────────────
    op.create_foreign_key(
        op.f("fk_run_evidence_items_canonical_evidence_id"),
        "run_evidence_items",
        "canonical_evidence_items",
        ["canonical_evidence_id"],
        ["canonical_evidence_id"],
        use_alter=True,
    )
    op.create_foreign_key(
        op.f("fk_canonical_evidence_items_current_best_run_evidence_id"),
        "canonical_evidence_items",
        "run_evidence_items",
        ["current_best_run_evidence_id"],
        ["run_evidence_item_id"],
        use_alter=True,
    )

    # ── evidence_entity_bindings ─────────────────────────────────────────
    op.create_table(
        "evidence_entity_bindings",
        sa.Column(
            "evidence_entity_binding_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "run_evidence_item_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("binding_rank", sa.Integer(), nullable=True),
        sa.Column("raw_entity_text", sa.Text(), nullable=True),
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
            "evidence_entity_binding_id",
            name=op.f("pk_evidence_entity_bindings"),
        ),
        sa.ForeignKeyConstraint(
            ["run_evidence_item_id"],
            ["run_evidence_items.run_evidence_item_id"],
            name=op.f("fk_evidence_entity_bindings_run_evidence_item_id"),
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["normalized_entities.entity_id"],
            name=op.f("fk_evidence_entity_bindings_entity_id"),
        ),
    )
    op.create_index(
        "ix_evidence_entity_bindings_entity_type_entity_id",
        "evidence_entity_bindings",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_evidence_entity_bindings_run_evidence_item_id_role",
        "evidence_entity_bindings",
        ["run_evidence_item_id", "role"],
    )


def downgrade() -> None:
    op.drop_table("evidence_entity_bindings")
    # Drop circular FK constraints before dropping the tables they reference.
    op.drop_constraint("fk_run_evidence_items_canonical_evidence_id", "run_evidence_items", type_="foreignkey")
    op.drop_constraint("fk_canonical_evidence_items_current_best_run_evidence_id", "canonical_evidence_items", type_="foreignkey")
    op.drop_table("run_evidence_items")
    op.drop_table("canonical_evidence_items")
    op.drop_table("entity_merge_events")
    op.drop_table("normalized_entities")
    op.drop_table("processing_runs")
    op.drop_table("source_document_identifiers")
    op.drop_constraint("fk_source_documents_latest_processing_run_id", "source_documents", type_="foreignkey")
    op.drop_table("source_documents")
    op.drop_table("users")
