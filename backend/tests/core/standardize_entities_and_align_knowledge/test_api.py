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


@pytest.mark.asyncio
async def test_import_clinvar_stream_commits_each_chunk(monkeypatch, tmp_path: Path) -> None:
    """ClinVar streaming should commit per chunk instead of holding one giant transaction."""
    chunk_commit_calls = {"value": 0}
    received_batches: list[ImportBatch] = []

    class FakeRepository:
        def __init__(self, session) -> None:
            self.session = session

        async def upsert_terminology_batch(self, batch) -> None:
            received_batches.append(batch)

    class FakeSession:
        async def commit(self) -> None:
            chunk_commit_calls["value"] += 1

    monkeypatch.setattr(
        api_module,
        "iter_clinvar_batches",
        lambda **kwargs: iter(
            (
                ImportBatch(entries=(ImportEntry(
                    entity_type=EntityType.VARIANT,
                    source_db="ClinVar",
                    external_id="ClinVarVariation:1",
                    display_name="variant-1",
                    normalized_name="variant-1",
                    aliases=("variant-1",),
                    raw_payload={},
                    version="v1",
                ),)),
                ImportBatch(entries=(ImportEntry(
                    entity_type=EntityType.VARIANT,
                    source_db="ClinVar",
                    external_id="ClinVarVariation:2",
                    display_name="variant-2",
                    normalized_name="variant-2",
                    aliases=("variant-2",),
                    raw_payload={},
                    version="v1",
                ),)),
            ),
        ),
    )

    await api_module._import_clinvar_stream(
        repository=FakeRepository(FakeSession()),
        path=tmp_path / "variant_summary.core.tsv",
        version="v1",
        chunk_size=10_000,
    )

    assert len(received_batches) == 2
    assert chunk_commit_calls["value"] == 2


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


def test_matches_json_serialization() -> None:
    """EntityMatch list serializes to auditable matches.json format."""
    from src.core.standardize_entities_and_align_knowledge.contracts import (
        BindingRole,
        EntityMatch,
        EntityType,
        MatchMethod,
        MatchStatus,
        StandardizationCandidate,
    )

    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="GLA",
        chain_id="chain-1",
        track="original",
    )
    match = EntityMatch(
        candidate=candidate,
        status=MatchStatus.STANDARDIZED,
        external_id="HGNC:4296",
        display_name="GLA",
        rationale="unique HGNC primary match",
        match_method=MatchMethod.PRECISE,
    )
    entries = api_module.serialize_matches((match,))
    assert len(entries) == 1
    entry = entries[0]
    assert entry["raw_text"] == "GLA"
    assert entry["entity_type"] == "gene"
    assert entry["status"] == "standardized"
    assert entry["external_id"] == "HGNC:4296"
    assert entry["display_name"] == "GLA"
    assert entry["rationale"] == "unique HGNC primary match"
    assert entry["match_method"] == "precise"


def test_summary_includes_terminology_health_status() -> None:
    """Summary output includes DB terminology count and embedding availability."""
    summary = api_module.build_summary_metadata(
        imported_terminology=False,
        terminology_sources=["hgnc", "omim"],
        terminology_version="2026-05-26",
        terminology_entry_count=0,
        embedding_available=False,
    )
    assert summary["imported_terminology"] is False
    assert summary["terminology_entry_count"] == 0
    assert summary["embedding_available"] is False
    assert summary["terminology_sources"] == ["hgnc", "omim"]


@pytest.mark.asyncio
async def test_build_terminology_embeddings_passes_scope_filters(monkeypatch) -> None:
    """Embedding facade should support narrowing the vectorization scope."""
    disposed = {"value": False}
    build_calls: list[dict[str, object]] = []

    class FakeEngine:
        async def dispose(self) -> None:
            disposed["value"] = True

    class FakeIndexer:
        def __init__(self, session, provider) -> None:
            self.session = session
            self.provider = provider

        async def build(self, **kwargs):
            build_calls.append(kwargs)
            return 7

    @asynccontextmanager
    async def fake_get_async_session(factory):
        class FakeSession:
            async def commit(self) -> None:
                return None

        yield FakeSession()

    monkeypatch.setattr(api_module, "build_async_engine", lambda cfg: FakeEngine())
    monkeypatch.setattr(api_module, "async_session_factory", lambda engine: "factory")
    monkeypatch.setattr(api_module, "get_async_session", fake_get_async_session)
    monkeypatch.setattr(
        "src.core.standardize_entities_and_align_knowledge.similarity_match.indexer.TerminologyEmbeddingIndexer",
        FakeIndexer,
    )

    class FakeCfg:
        model_server_url = "http://localhost:8001"
        embedding = type("EmbeddingCfg", (), {"base_url": "", "model": "embed-model", "batch_size": 16})()

    count = await api_module.build_terminology_embeddings(
        cfg=FakeCfg(),
        entity_types={EntityType.DISEASE, EntityType.PHENOTYPE},
        source_dbs={"OMIM", "HPO", "MONDO"},
    )

    assert count == 7
    assert build_calls == [{
        "embedding_model": "embed-model",
        "batch_size": 16,
        "entity_types": {EntityType.DISEASE, EntityType.PHENOTYPE},
        "source_dbs": {"OMIM", "HPO", "MONDO"},
    }]
    assert disposed["value"] is True
