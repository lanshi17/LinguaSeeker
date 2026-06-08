"""Tests for LiteratureProfile ORM model."""
from __future__ import annotations


def test_literature_profile_model_exists() -> None:
    """LiteratureProfile is importable from models module."""
    from src.dao.postgresql.models import LiteratureProfile

    assert LiteratureProfile.__tablename__ == "literature_profiles"


def test_literature_profile_has_required_columns() -> None:
    """LiteratureProfile has all required columns."""
    from src.dao.postgresql.models import LiteratureProfile

    column_names = {c.name for c in LiteratureProfile.__table__.columns}
    required = {
        "literature_profile_id",
        "source_document_id",
        "pmid",
        "doi",
        "title",
        "authors",
        "journal",
        "publication_year",
        "evidence_groups",
        "review_status",
        "review_notes",
        "overall_confidence",
        "total_evidence_fields",
        "found_count",
        "not_found_count",
        "latest_processing_run_id",
        "created_at",
        "updated_at",
    }
    assert required <= column_names, f"Missing columns: {required - column_names}"


def test_literature_profile_unique_source_document() -> None:
    """LiteratureProfile has a unique constraint on source_document_id."""
    from src.dao.postgresql.models import LiteratureProfile

    table = LiteratureProfile.__table__
    # Check unique=True on the column itself
    col = table.columns["source_document_id"]
    assert col.unique is True
