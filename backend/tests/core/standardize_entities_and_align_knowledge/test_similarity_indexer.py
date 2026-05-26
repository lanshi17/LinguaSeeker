"""Tests for terminology embedding index building."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.similarity_match.indexer import (
    build_embedding_text,
    make_embedding_text_hash,
)


class Entry:
    """Simple entry stub for embedding text tests."""

    display_name = "BRCA1"
    aliases = ["BRCA1", "BRCC1"]
    external_id = "HGNC:1100"
    source_db = "HGNC"


def test_build_embedding_text_includes_display_name_aliases_and_source_identity() -> None:
    """Embedding text is deterministic and contains useful terminology context."""
    text = build_embedding_text(Entry())

    assert text == "BRCA1\nBRCC1\nHGNC:1100\nHGNC"


def test_make_embedding_text_hash_is_stable_sha256() -> None:
    """Embedding text hash is stable for upsert identity."""
    assert len(make_embedding_text_hash("BRCA1")) == 64
    assert make_embedding_text_hash("BRCA1") == make_embedding_text_hash("BRCA1")
