from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.e2e_standardize_entities import (
    DEFAULT_EXTRACT_EVIDENCE_DIR,
    run_standardize_entities,
)
from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityMatch,
    EntityType,
    MatchStatus,
    StandardizationCandidate,
    StandardizationResult,
)


class FakeStandardizationService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def run_dual_result(
        self,
        result,
        *,
        source_document_id: str,
        processing_run_id: str,
    ) -> StandardizationResult:
        self.calls.append((result.document_id, source_document_id, processing_run_id))
        matches = (
            EntityMatch(
                candidate=StandardizationCandidate(
                    candidate_id="c1",
                    entity_type=EntityType.GENE,
                    role=BindingRole.SUBJECT,
                    raw_text="GLA",
                    chain_id="chain-1",
                    track="original",
                ),
                status=MatchStatus.STANDARDIZED,
                external_id="HGNC:4296",
                display_name="GLA",
            ),
        )
        return StandardizationResult(
            document_id=result.document_id,
            match_count=4,
            standardized_count=3,
            ambiguous_count=1,
            unmapped_count=0,
            normalized_entity_ids=("entity-1", "entity-2", "entity-3", "entity-4"),
            matches=matches,
        )


class FakeAsyncSession:
    def __init__(self) -> None:
        self.commit_called = False

    async def commit(self) -> None:
        self.commit_called = True


class FakeSessionContext:
    def __init__(self, session: FakeAsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> FakeAsyncSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakeSessionFactory:
    def __init__(self, session: FakeAsyncSession) -> None:
        self._session = session

    def __call__(self) -> FakeSessionContext:
        return FakeSessionContext(self._session)


@pytest.mark.asyncio
async def test_run_standardize_entities_writes_outputs_without_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "extract_evidence" / "法布雷病1例" / "latest"
    _write_extract_evidence_fixture(input_dir)
    output_dir = tmp_path / "standardize_entities"
    service = FakeStandardizationService()
    session = FakeAsyncSession()
    import_calls: list[tuple[Path, str, tuple[str, ...]]] = []
    refresh_calls: list[tuple[Path, Path, str]] = []

    monkeypatch.setattr(
        "scripts.e2e_standardize_entities._open_standardization_session",
        lambda cfg: FakeSessionFactory(session),
    )
    monkeypatch.setattr(
        "scripts.e2e_standardize_entities._import_terminology_if_requested",
        lambda *, cfg, terminology_root, version, sources: import_calls.append(
            (terminology_root, version, tuple(sources)),
        ),
    )
    monkeypatch.setattr(
        "scripts.e2e_standardize_entities._refresh_upstream_if_requested",
        lambda **kwargs: refresh_calls.append(
            (
                kwargs["cross_lingual_input_dir"],
                kwargs["extract_output_dir"],
                kwargs["refresh_run_id"],
            ),
        ),
    )

    saved_dir = await run_standardize_entities(
        extract_evidence_dir=input_dir,
        output_dir=output_dir,
        service=service,
        source_document_id="source-doc-1",
        processing_run_id="processing-run-1",
        run_id="test-run",
        terminology_root=Path("/tmp/terminology"),
        terminology_version="2026-05-25",
        terminology_sources=["hgnc", "omim"],
        import_terminology=False,
        refresh_upstream=False,
    )

    assert saved_dir == output_dir / "法布雷病1例" / "test-run"
    assert service.calls == [("法布雷病1例", "source-doc-1", "processing-run-1")]
    assert session.commit_called is True
    assert import_calls == []
    assert refresh_calls == []

    result_data = json.loads((saved_dir / "result.json").read_text(encoding="utf-8"))
    matches_data = json.loads((saved_dir / "matches.json").read_text(encoding="utf-8"))
    summary_data = json.loads((saved_dir / "summary.json").read_text(encoding="utf-8"))
    upstream_data = json.loads((saved_dir / "upstream_result.json").read_text(encoding="utf-8"))

    assert result_data["document_id"] == "法布雷病1例"
    assert result_data["standardized_count"] == 3
    assert len(matches_data["matches"]) == 1
    assert matches_data["matches"][0]["raw_text"] == "GLA"
    assert matches_data["matches"][0]["status"] == "standardized"
    assert summary_data["document_id"] == "法布雷病1例"
    assert summary_data["extract_evidence_dir"] == str(input_dir.resolve())
    assert summary_data["output_dir"] == str(saved_dir)
    assert summary_data["match_count"] == 4
    assert summary_data["normalized_entity_count"] == 4
    assert summary_data["refreshed_upstream"] is False
    assert summary_data["imported_terminology"] is False
    assert upstream_data["document_id"] == "法布雷病1例"


@pytest.mark.asyncio
async def test_run_standardize_entities_can_refresh_and_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extract_dir = tmp_path / "extract_evidence" / "法布雷病1例" / "latest"
    _write_extract_evidence_fixture(extract_dir)
    output_dir = tmp_path / "standardize_entities"
    service = FakeStandardizationService()
    session = FakeAsyncSession()
    import_calls: list[tuple[Path, str, tuple[str, ...]]] = []
    refresh_calls: list[tuple[Path, Path, str]] = []

    monkeypatch.setattr(
        "scripts.e2e_standardize_entities._open_standardization_session",
        lambda cfg: FakeSessionFactory(session),
    )
    monkeypatch.setattr(
        "scripts.e2e_standardize_entities._import_terminology_if_requested",
        lambda *, cfg, terminology_root, version, sources: import_calls.append(
            (terminology_root, version, tuple(sources)),
        ),
    )
    monkeypatch.setattr(
        "scripts.e2e_standardize_entities._refresh_upstream_if_requested",
        lambda **kwargs: refresh_calls.append(
            (
                kwargs["cross_lingual_input_dir"],
                kwargs["extract_output_dir"],
                kwargs["refresh_run_id"],
            ),
        ),
    )

    await run_standardize_entities(
        extract_evidence_dir=extract_dir,
        output_dir=output_dir,
        service=service,
        source_document_id="source-doc-2",
        processing_run_id="processing-run-2",
        run_id="test-run",
        terminology_root=Path("/tmp/terminology"),
        terminology_version="2026-05-26",
        terminology_sources=["hgnc", "clinvar"],
        import_terminology=True,
        refresh_upstream=True,
        cross_lingual_input_dir=tmp_path / "cross_lingual" / "zh" / "法布雷病1例",
        refresh_run_id="refresh-1",
    )

    assert import_calls == [(Path("/tmp/terminology"), "2026-05-26", ("hgnc", "clinvar"))]
    assert refresh_calls == [
        (
            tmp_path / "cross_lingual" / "zh" / "法布雷病1例",
            extract_dir.parent.parent,
            "refresh-1",
        )
    ]


def test_default_extract_evidence_dir_points_to_fabry_latest() -> None:
    assert DEFAULT_EXTRACT_EVIDENCE_DIR.as_posix().endswith("backend/output/extract_evidence/法布雷病1例/latest")


def _write_extract_evidence_fixture(input_dir: Path) -> None:
    input_dir.mkdir(parents=True)
    result = {
        "document_id": "法布雷病1例",
        "original_result": {
            "status": "completed",
            "document_id": "法布雷病1例",
            "track": "original",
            "evidence_chains": [
                {
                    "chain_id": "gene=GLA|variant=p.R227X",
                    "gene_text": "GLA",
                    "disease_text": "法布雷病",
                    "variant_text": "p.R227X",
                    "case_ids": ["case-1"],
                    "special_evidence_ids": [],
                    "chain_level": "singleton",
                },
            ],
            "evidence_items": [
                {
                    "field_id": "B.clinical_phenotypes",
                    "category": "B",
                    "field_name": "Clinical phenotypes",
                    "status": "found",
                    "value": ["肢端感觉异常"],
                    "confidence": 0.9,
                    "group_id": "gene=GLA|variant=p.R227X",
                    "assigned_acmg_codes": [],
                    "assigned_clingen_modules": [],
                },
            ],
        },
        "translated_result": {
            "status": "completed",
            "document_id": "法布雷病1例",
            "track": "translated",
            "evidence_chains": [
                {
                    "chain_id": "gene=GLA|variant=p.R227X",
                    "gene_text": "GLA",
                    "disease_text": "Fabry disease",
                    "variant_text": "p.R227X",
                    "case_ids": ["case-1"],
                    "special_evidence_ids": [],
                    "chain_level": "singleton",
                },
            ],
            "evidence_items": [
                {
                    "field_id": "B.clinical_phenotypes",
                    "category": "B",
                    "field_name": "Clinical phenotypes",
                    "status": "found",
                    "value": ["acroparesthesia"],
                    "confidence": 0.95,
                    "group_id": "gene=GLA|variant=p.R227X",
                    "assigned_acmg_codes": [],
                    "assigned_clingen_modules": [],
                },
            ],
        },
    }
    (input_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False),
        encoding="utf-8",
    )
