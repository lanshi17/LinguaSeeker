"""Add partial unique index guaranteeing internal variant external_id uniqueness.

Every variant entity now carries a non-NULL external_id: ClinVar matches use
``ClinVarVariation:<id>`` and unmatched variants use a deterministic synthetic
``internal:variant:<sha12>`` id (see ``variant_id.make_internal_variant_id``).
This partial unique index enforces uniqueness of the synthetic internal ids so
repeated upserts of the same unmapped variant collapse onto one
``normalized_entities`` row.

The index predicate ``external_id LIKE 'internal:variant:%'`` is disjoint from
the existing partial unique indexes:
- ``uq_normalized_entities_standardized_external_id`` only covers rows with
  ``standardization_status = 'standardized'`` (internal ids are ``unmapped``).
- ``uq_normalized_entities_unmapped_raw_text`` /
  ``uq_normalized_entities_reviewed_unmappable_raw_text`` key on
  ``(entity_type, normalized_raw_text)``, a different column set.

Revision ID: variant_internal_id_20260621
Revises: critical_indexes_20260621
Create Date: 2026-06-21
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text


revision = "variant_internal_id_20260621"
down_revision = "critical_indexes_20260621"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_normalized_entities_variant_internal_id",
        "normalized_entities",
        ["external_id"],
        unique=True,
        postgresql_where=text("external_id LIKE 'internal:variant:%'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_normalized_entities_variant_internal_id",
        table_name="normalized_entities",
    )
