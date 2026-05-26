"""Tests for MVP database ORM metadata."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, Table, UniqueConstraint

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
    "terminology_entries",
    "terminology_aliases",
    "terminology_relationships",
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


def _check_constraint_by_name(table: Table, name: str) -> CheckConstraint:
    matching = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name == name
    ]
    assert len(matching) == 1
    return matching[0]


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


def test_run_evidence_confidence_has_database_range_constraint() -> None:
    """Run-level confidence cannot be outside the normalized 0..1 range."""
    constraint = _check_constraint_by_name(
        _table("run_evidence_items"),
        "ck_run_evidence_items_confidence_range",
    )

    assert str(constraint.sqltext) == "confidence >= 0 AND confidence <= 1"


def test_canonical_evidence_confidence_has_database_range_constraint() -> None:
    """Canonical confidence cannot be outside the normalized 0..1 range."""
    constraint = _check_constraint_by_name(
        _table("canonical_evidence_items"),
        "ck_canonical_evidence_items_current_best_confidence_range",
    )

    assert str(constraint.sqltext) == "current_best_confidence >= 0 AND current_best_confidence <= 1"


def test_terminology_reference_tables_exist() -> None:
    """ORM metadata includes the terminology reference tables."""
    metadata = Base.metadata

    assert "terminology_entries" in metadata.tables
    assert "terminology_aliases" in metadata.tables
    assert "terminology_relationships" in metadata.tables


def test_terminology_entries_unique_source_external_id() -> None:
    """Terminology entries are unique within a source by external ID."""
    table = _table("terminology_entries")

    assert ("source_db", "external_id") in _unique_constraint_columns(table)


def test_terminology_aliases_lookup_index_exists() -> None:
    """Terminology aliases expose the entity-type plus normalized-alias lookup index."""
    table = _table("terminology_aliases")
    index = _index_by_name(table, "ix_terminology_aliases_lookup")

    assert tuple(expression.name for expression in index.expressions) == (
        "entity_type",
        "normalized_alias",
    )


def test_terminology_relationship_object_is_nullable() -> None:
    """Terminology relationships allow scalar assertions without object entries."""
    table = _table("terminology_relationships")

    assert table.c.object_entry_id.nullable is True


def test_terminology_relationships_identity_unique_constraint() -> None:
    """Terminology relationships are unique by subject/object/type/source for bulk upsert."""
    table = _table("terminology_relationships")

    assert (
        "subject_entry_id",
        "object_entry_id",
        "relationship_type",
        "source_db",
    ) in _unique_constraint_columns(table)


def test_terminology_embeddings_table_in_metadata() -> None:
    """ORM metadata includes the terminology_embeddings table."""
    assert "terminology_embeddings" in Base.metadata.tables


def test_terminology_embeddings_has_embedding_column() -> None:
    """Terminology embeddings table has an embedding column."""
    table = _table("terminology_embeddings")
    assert "embedding" in table.columns


def test_terminology_embeddings_entry_model_unique() -> None:
    """Each entry has at most one embedding per model version."""
    assert ("entry_id", "embedding_text_hash", "embedding_model") in _unique_constraint_columns(
        _table("terminology_embeddings")
    )


def test_terminology_embeddings_cascade_delete() -> None:
    """Embedding is deleted when the parent entry is deleted (CASCADE)."""
    table = _table("terminology_embeddings")
    fk = next(c for c in table.foreign_key_constraints if "entry_id" in [p.name for p in c.columns])
    assert fk.ondelete == "CASCADE"


def test_terminology_embeddings_embedding_is_vector_type() -> None:
    """The embedding column is pgvector Vector type, not plain ARRAY."""
    from pgvector.sqlalchemy import Vector

    col = _table("terminology_embeddings").c.embedding
    assert isinstance(col.type, Vector)
