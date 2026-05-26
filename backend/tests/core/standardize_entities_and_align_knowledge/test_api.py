"""Tests for the Phase 3 public API facade."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from src.core.standardize_entities_and_align_knowledge import api as api_module
from src.core.standardize_entities_and_align_knowledge.contracts import EntityType
from src.core.standardize_entities_and_align_knowledge.importers import (
    ImportAlias,
    ImportBatch,
    ImportEntry,
    ImportRelationship,
)


def test_api_exposes_standardization_service_class() -> None:
    """The public facade exports the entity standardization service."""
    from src.core.standardize_entities_and_align_knowledge.api import EntityStandardizationService

    assert EntityStandardizationService is not None


def test_load_import_batches_dispatches_requested_sources_only(monkeypatch) -> None:
    """Batch loading calls only the selected source parsers and skips unknown names."""
    calls: list[tuple[str, object]] = []

    def _fake_hgnc(path: Path, *, version: str):
        calls.append(("hgnc", path))
        return "hgnc-batch"

    def _fake_omim(path: Path, *, version: str):
        calls.append(("omim", path))
        return "omim-batch"

    monkeypatch.setattr(api_module, "parse_hgnc_rows", _fake_hgnc)
    monkeypatch.setattr(api_module, "parse_omim_rows", _fake_omim)
    monkeypatch.setattr(api_module, "parse_hpo_rows", lambda *args, **kwargs: "hpo-batch")
    monkeypatch.setattr(api_module, "parse_clingen_rows", lambda *args, **kwargs: "clingen-batch")

    batches = api_module._load_import_batches(
        terminology_root=Path("/tmp/terminology"),
        version="test-version",
        sources=("hgnc", "omim", "unknown"),
    )

    assert batches == ("hgnc-batch", "omim-batch")
    assert calls == [
        ("hgnc", Path("/tmp/terminology/hgnc/hgnc_complete_set.txt")),
        ("omim", Path("/tmp/terminology/omim")),
    ]


@pytest.mark.asyncio
async def test_import_terminology_loads_batches_and_calls_repository(monkeypatch, tmp_path: Path) -> None:
    """The import facade loads selected batches and forwards them to the repository."""
    loaded_batches = [
        ImportBatch(),
        ImportBatch(),
    ]
    received_batches: list[object] = []
    disposed = {"value": False}

    class FakeEngine:
        async def dispose(self) -> None:
            disposed["value"] = True

    monkeypatch.setattr(api_module, "_load_import_batches", lambda **kwargs: tuple(loaded_batches))
    clinvar_stream_calls: list[tuple[Path, str, int]] = []
    preprocess_calls: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        api_module,
        "_import_clinvar_stream",
        lambda *, repository, path, version, chunk_size: clinvar_stream_calls.append((path, version, chunk_size)),
    )
    monkeypatch.setattr(
        api_module,
        "_ensure_clinvar_core_path",
        lambda path: preprocess_calls.append((path, path.with_name("variant_summary.core.tsv"))) or path.with_name("variant_summary.core.tsv"),
    )
    monkeypatch.setattr(api_module, "build_async_engine", lambda cfg: FakeEngine())
    monkeypatch.setattr(api_module, "async_session_factory", lambda engine: "factory")
    commit_called = {"value": False}

    class FakeRepository:
        def __init__(self, session) -> None:
            self.session = session

        async def upsert_terminology_batch(self, batch) -> None:
            received_batches.append(batch)

    @asynccontextmanager
    async def fake_get_async_session(factory):
        assert factory == "factory"
        class FakeSession:
            async def commit(self) -> None:
                commit_called["value"] = True

        yield FakeSession()

    monkeypatch.setattr(api_module, "StandardizationRepository", FakeRepository)
    monkeypatch.setattr(api_module, "get_async_session", fake_get_async_session)

    await api_module.import_terminology(
        cfg=object(),
        terminology_root=tmp_path,
        version="test-version",
        sources=["hgnc", "clinvar"],
    )

    assert received_batches == loaded_batches
    assert preprocess_calls == [(
        tmp_path / "clinvar" / "variant_summary.txt",
        tmp_path / "clinvar" / "variant_summary.core.tsv",
    )]
    assert clinvar_stream_calls == [(
        tmp_path / "clinvar" / "variant_summary.core.tsv",
        "test-version",
        10_000,
    )]
    assert commit_called["value"] is True
    assert disposed["value"] is True


def test_describe_batch_source_prefers_entries_then_aliases_then_relationships() -> None:
    batch_from_entries = ImportBatch(
        entries=(
            ImportEntry(
                entity_type=EntityType.GENE,
                source_db="HGNC",
                external_id="HGNC:1",
                display_name="A1BG",
                normalized_name="a1bg",
                aliases=("A1BG",),
                raw_payload={},
                version="v1",
            ),
        ),
    )
    batch_from_aliases = ImportBatch(
        aliases=(
            ImportAlias(
                external_id="OMIM:1",
                entity_type=EntityType.DISEASE,
                source_db="OMIM",
                alias_text="Disease",
                normalized_alias="disease",
                alias_type="name",
            ),
        ),
    )
    batch_from_relationships = ImportBatch(
        relationships=(
            ImportRelationship(
                subject_external_id="ClinVar:1",
                object_external_id="OMIM:1",
                relationship_type="variant_associated_with_disease",
                source_db="ClinVar",
                evidence_level=None,
                raw_payload={},
            ),
        ),
    )
    empty_batch = ImportBatch()

    assert api_module._describe_batch_source(batch_from_entries) == "HGNC"
    assert api_module._describe_batch_source(batch_from_aliases) == "OMIM"
    assert api_module._describe_batch_source(batch_from_relationships) == "ClinVar"
    assert api_module._describe_batch_source(empty_batch) == "empty"
