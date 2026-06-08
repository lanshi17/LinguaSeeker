"""add_performance_indexes

Add missing indexes identified during schema review:
- canonical_evidence_items: JSONB expression index on group_id, B-tree on field_id
- terminology_entries: B-tree on external_id (standalone lookup)
- chat_messages: composite (chat_session_id, created_at)
- chat_sessions: composite (processing_run_id, created_at DESC)
- review_audit_events: composite with created_at DESC for filter+sort
- frontend_search_index: B-tree on pmid/doi, GIN on gene_ids/variant_ids
- pipeline_run_states: JSONB expression index on pipeline_status

Also drops 4 redundant single-column indexes fully covered by the new composites.

Revision ID: 6a8f3b1c2d4e
Revises: 547f7e3f71e3
Create Date: 2026-06-08 10:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "6a8f3b1c2d4e"
down_revision: Union[str, None] = "547f7e3f71e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Prevent long lock holds during index creation on production tables.
_LOCK_TIMEOUT_MS = 30_000


def upgrade() -> None:
    op.execute(f"SET lock_timeout = '{_LOCK_TIMEOUT_MS}ms'")

    # ── New indexes ────────────────────────────────────────────────────

    # canonical_evidence_items: JSONB expression index for group_id lookups
    op.create_index(
        "ix_canonical_evidence_items_group_id",
        "canonical_evidence_items",
        [sa.text("(active_payload ->> 'group_id')")],
    )
    # canonical_evidence_items: field_id for ORDER BY in group detail
    op.create_index(
        "ix_canonical_evidence_items_field_id",
        "canonical_evidence_items",
        ["field_id"],
    )

    # terminology_entries: external_id standalone lookup
    op.create_index(
        "ix_terminology_entries_external_id",
        "terminology_entries",
        ["external_id"],
    )

    # chat_messages: composite for list_messages (WHERE session = X ORDER BY created_at)
    op.create_index(
        "ix_chat_messages_session_created",
        "chat_messages",
        ["chat_session_id", "created_at"],
    )

    # chat_sessions: composite for list_sessions (WHERE run = X ORDER BY created_at DESC)
    op.create_index(
        "ix_chat_sessions_run_created",
        "chat_sessions",
        ["processing_run_id", sa.text("created_at DESC")],
    )

    # review_audit_events: composite indexes for filter + sort patterns
    op.create_index(
        "ix_review_audit_events_canonical_created",
        "review_audit_events",
        ["canonical_evidence_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_review_audit_events_reviewer_created",
        "review_audit_events",
        ["reviewer_id", sa.text("created_at DESC")],
    )

    # pipeline_run_states: JSONB expression index for crash recovery WHERE filter
    op.create_index(
        "ix_pipeline_run_states_pipeline_status",
        "pipeline_run_states",
        [sa.text("(state_json ->> 'pipeline_status')")],
    )

    # frontend_search_index: B-tree on pmid/doi, GIN on JSONB array columns
    op.create_index(
        "ix_frontend_search_index_pmid",
        "frontend_search_index",
        ["pmid"],
    )
    op.create_index(
        "ix_frontend_search_index_doi",
        "frontend_search_index",
        ["doi"],
    )
    op.create_index(
        "ix_frontend_search_index_gene_ids",
        "frontend_search_index",
        ["gene_ids"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_frontend_search_index_variant_ids",
        "frontend_search_index",
        ["variant_ids"],
        postgresql_using="gin",
    )

    # ── Drop redundant single-column indexes ───────────────────────────
    # These are fully covered by the new composite indexes above (leftmost prefix).

    op.drop_index("ix_review_audit_events_canonical_evidence_id", table_name="review_audit_events")
    op.drop_index("ix_review_audit_events_reviewer_id", table_name="review_audit_events")
    op.drop_index("ix_chat_sessions_processing_run_id", table_name="chat_sessions")
    op.drop_index("ix_chat_messages_chat_session_id", table_name="chat_messages")


def downgrade() -> None:
    # Re-create dropped single-column indexes
    op.create_index(
        "ix_chat_messages_chat_session_id",
        "chat_messages",
        ["chat_session_id"],
    )
    op.create_index(
        "ix_chat_sessions_processing_run_id",
        "chat_sessions",
        ["processing_run_id"],
    )
    op.create_index(
        "ix_review_audit_events_reviewer_id",
        "review_audit_events",
        ["reviewer_id"],
    )
    op.create_index(
        "ix_review_audit_events_canonical_evidence_id",
        "review_audit_events",
        ["canonical_evidence_id"],
    )

    # Drop new indexes (reverse order)
    op.drop_index("ix_frontend_search_index_variant_ids", table_name="frontend_search_index")
    op.drop_index("ix_frontend_search_index_gene_ids", table_name="frontend_search_index")
    op.drop_index("ix_frontend_search_index_doi", table_name="frontend_search_index")
    op.drop_index("ix_frontend_search_index_pmid", table_name="frontend_search_index")
    op.drop_index("ix_pipeline_run_states_pipeline_status", table_name="pipeline_run_states")
    op.drop_index("ix_review_audit_events_reviewer_created", table_name="review_audit_events")
    op.drop_index("ix_review_audit_events_canonical_created", table_name="review_audit_events")
    op.drop_index("ix_chat_sessions_run_created", table_name="chat_sessions")
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_index("ix_terminology_entries_external_id", table_name="terminology_entries")
    op.drop_index("ix_canonical_evidence_items_field_id", table_name="canonical_evidence_items")
    op.drop_index("ix_canonical_evidence_items_group_id", table_name="canonical_evidence_items")
