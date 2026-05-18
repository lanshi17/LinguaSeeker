"""Tests for MVP database ORM metadata."""
from __future__ import annotations

from sqlalchemy import Index, Table, UniqueConstraint

from src.dao.models import Base


EXPECTED_TABLES = {
    "source_documents",
    "source_document_identifiers",
    "processing_runs",
    "normalized_entities",
    "entity_merge_events",
    "run_evidence_items",
    "evidence_entity_bindings",
    "canonical_evidence_items",
    "users",
}


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


def _unique_constraint_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _index_by_name(table: Table, name: str) -> Index:
    matching = [index for index in table.indexes if index.name == name]
    assert len(matching) == 1
    return matching[0]


def test_mvp_metadata_contains_required_tables() -> None:
    """ORM metadata includes all normalized MVP persistence tables."""
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_source_identifier_uniqueness_constraint() -> None:
    """External identifiers deduplicate source documents by type and value."""
    assert ("identifier_type", "identifier_value") in _unique_constraint_columns(
        _table("source_document_identifiers"),
    )


def test_canonical_evidence_identity_uniqueness_constraint() -> None:
    """Canonical evidence identity is source document plus field, position, and entity scope."""
    assert (
        "source_document_id",
        "field_id",
        "position_hash",
        "entity_scope_hash",
    ) in _unique_constraint_columns(_table("canonical_evidence_items"))


def test_normalized_entity_standardized_external_id_unique_index() -> None:
    """Standardized entities are unique by entity type and external ID."""
    index = _index_by_name(
        _table("normalized_entities"),
        "uq_normalized_entities_standardized_external_id",
    )

    assert index.unique
    assert tuple(expression.name for expression in index.expressions) == ("entity_type", "external_id")
    assert str(index.dialect_options["postgresql"]["where"]) == (
        "external_id IS NOT NULL AND standardization_status = 'standardized'"
    )


def test_normalized_entity_unmapped_raw_text_unique_index() -> None:
    """Unmapped entities are unique by entity type and normalized raw text."""
    index = _index_by_name(
        _table("normalized_entities"),
        "uq_normalized_entities_unmapped_raw_text",
    )

    assert index.unique
    assert tuple(expression.name for expression in index.expressions) == ("entity_type", "normalized_raw_text")
    assert str(index.dialect_options["postgresql"]["where"]) == "standardization_status = 'unmapped'"
