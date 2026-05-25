"""Tests for the Phase 3 public API facade."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from src.core.standardize_entities_and_align_knowledge import api as api_module


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
    monkeypatch.setattr(api_module, "parse_clinvar_rows", lambda *args, **kwargs: "clinvar-batch")

    batches = api_module._load_import_batches(
        terminology_root=Path("/tmp/terminology"),
        version="test-version",
        sources=("hgnc", "omim", "unknown"),
    )

    assert batches == ("hgnc-batch", "omim-batch")
    assert calls == [
        ("hgnc", Path("/tmp/terminology/hgnc_complete_set.txt")),
        ("omim", Path("/tmp/terminology/omim")),
    ]


@pytest.mark.asyncio
async def test_import_terminology_loads_batches_and_calls_repository(monkeypatch, tmp_path: Path) -> None:
    """The import facade loads selected batches and forwards them to the repository."""
    loaded_batches = ["batch-a", "batch-b"]
    received_batches: list[object] = []
    disposed = {"value": False}

    class FakeEngine:
        async def dispose(self) -> None:
            disposed["value"] = True

    monkeypatch.setattr(api_module, "_load_import_batches", lambda **kwargs: tuple(loaded_batches))
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
    assert commit_called["value"] is True
    assert disposed["value"] is True
