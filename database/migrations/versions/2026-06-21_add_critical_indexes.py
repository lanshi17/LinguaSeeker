"""Add critical performance indexes for hot query paths.

P0: pipeline_run_states.created_at, canonical_evidence_items (doc, field),
    literature_profiles.updated_at
P1: run_evidence_items source-linker composite, normalized_entities
    standardization composite, canonical_evidence_items.review_status
P2: source_document_identifiers (doc, type) composite replacing single-col,
    processing_runs.run_status

Revision ID: critical_indexes_20260621
Revises: chat_message_action_20260613
Create Date: 2026-06-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "critical_indexes_20260621"
down_revision = "chat_message_action_20260613"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── P0: High-frequency hot paths ──────────────────────────────

    # 1. pipeline_run_states.created_at DESC
    #    list_runs() sorts newest-first; group-detail looks up latest run.
    op.create_index(
        "ix_pipeline_run_states_created_at_desc",
        "pipeline_run_states",
        [sa.text("created_at DESC")],
    )

    # 2. canonical_evidence_items (source_document_id, field_id) composite
    #    search_service ORDER BY and group-detail filter on both columns.
    op.create_index(
        "ix_canonical_evidence_items_doc_field",
        "canonical_evidence_items",
        ["source_document_id", "field_id"],
    )

    # 3. literature_profiles.updated_at DESC
    #    literature search paginates by newest-updated first.
    op.create_index(
        "ix_literature_profiles_updated_at_desc",
        "literature_profiles",
        [sa.text("updated_at DESC")],
    )

    # ── P1: Medium-frequency paths ────────────────────────────────

    # 4. run_evidence_items 5-column composite for source linker fallback
    op.create_index(
        "ix_run_evidence_items_source_lookup",
        "run_evidence_items",
        [
            "source_document_id",
            "field_id",
            "position_hash",
            "entity_scope_hash",
            "track",
        ],
    )

    # 5. normalized_entities general standardization lookup
    op.create_index(
        "ix_normalized_entities_type_text_status",
        "normalized_entities",
        ["entity_type", "normalized_raw_text", "standardization_status"],
    )

    # 6. canonical_evidence_items.review_status for review dashboard
    op.create_index(
        "ix_canonical_evidence_items_review_status",
        "canonical_evidence_items",
        ["review_status"],
    )

    # ── P2: Lower priority but cheap to add ───────────────────────

    # 7. Replace single-column index with composite covering index
    op.drop_index("ix_source_document_identifiers_source_document_id", "source_document_identifiers")
    op.create_index(
        "ix_source_document_identifiers_doc_type",
        "source_document_identifiers",
        ["source_document_id", "identifier_type"],
    )

    # 8. processing_runs.run_status for status filtering
    op.create_index(
        "ix_processing_runs_run_status",
        "processing_runs",
        ["run_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_runs_run_status", "processing_runs")

    op.drop_index("ix_source_document_identifiers_doc_type", "source_document_identifiers")
    op.create_index(
        "ix_source_document_identifiers_source_document_id",
        "source_document_identifiers",
        ["source_document_id"],
    )

    op.drop_index("ix_canonical_evidence_items_review_status", "canonical_evidence_items")
    op.drop_index("ix_normalized_entities_type_text_status", "normalized_entities")
    op.drop_index("ix_run_evidence_items_source_lookup", "run_evidence_items")

    op.drop_index("ix_literature_profiles_updated_at_desc", "literature_profiles")
    op.drop_index("ix_canonical_evidence_items_doc_field", "canonical_evidence_items")
    op.drop_index("ix_pipeline_run_states_created_at_desc", "pipeline_run_states")
