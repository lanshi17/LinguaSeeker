from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.core.evidence_extraction.api import EvidenceExtractionService
from src.core.evidence_extraction.contracts import (
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    Track,
)
from src.core.evidence_extraction.workflow import EvidenceExtractionWorkflow


_BACKEND_DIR = Path(__file__).resolve().parents[4]
_LEGACY_FABRY_OUTPUT_DIR = _BACKEND_DIR / "output" / "zh" / "法布雷病1例"
_CROSS_LINGUAL_FABRY_OUTPUT_DIR = _BACKEND_DIR / "output" / "cross_lingual" / "zh" / "法布雷病1例"
_FABRY_OUTPUT_DIR = _LEGACY_FABRY_OUTPUT_DIR if _LEGACY_FABRY_OUTPUT_DIR.exists() else _CROSS_LINGUAL_FABRY_OUTPUT_DIR
_FABRY_OUTPUT_READY = (_FABRY_OUTPUT_DIR / "original.json").exists() and (
    _FABRY_OUTPUT_DIR / "translated.json"
).exists()


@pytest.fixture
def mock_config() -> MagicMock:
    cfg = MagicMock()
    cfg.llm.api_key = "key"
    cfg.llm.base_url = "http://localhost:8001/v1"
    cfg.llm.model = "fast"
    cfg.llm.timeout = 60
    cfg.reasoning.api_key = "key"
    cfg.reasoning.base_url = "http://localhost:8001/v1"
    cfg.reasoning.model = "strong"
    cfg.reasoning.reasoning_effort = "high"
    cfg.reasoning.max_tokens = 8192
    cfg.reasoning.timeout = 180
    return cfg


class FabryFixtureProvider:
    """Deterministic provider for running the workflow over the real Fabry fixture."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Track]] = []

    def invoke_structured(
        self,
        prompt: str,
        output_schema: type[Any],
        tier: Any,
        stage: str,
        response_method: str = "json_schema",
    ) -> Any:
        track = self._track_from_prompt(prompt)
        self.calls.append((stage, track))
        if stage == "relevance_scan":
            return DocumentEvidenceMap(
                relevant=True,
                disease_terms=["法布雷病"] if track == Track.ORIGINAL else ["Fabry disease"],
                gene_terms=["GLA"],
            )
        if stage.startswith("catalog_extraction"):
            text = self._document_text_from_prompt(prompt)
            snippet = "法布雷病" if track == Track.ORIGINAL else "Fabry disease"
            start = text.index(snippet)
            return [
                EvidenceItem(
                    field_id="B.disease_diagnosis",
                    category="B",
                    field_name="Disease diagnosis",
                    status=EvidenceStatus.FOUND,
                    value=snippet,
                    source=SourceLocation(
                        span_id=self._span_for_offset(text, snippet, start, track).span_id,
                        page=self._span_for_offset(text, snippet, start, track).page,
                        start_offset=start,
                        end_offset=start + len(snippet),
                        context_type="text",
                        context_ref="fixture",
                        text_snippet=snippet,
                    ),
                    confidence=0.95,
                )
            ]
        if stage.startswith("special_evidence"):
            return []
        if stage.startswith("clinical_context"):
            return []
        raise AssertionError(f"unexpected stage: {stage}")

    async def ainvoke_structured(
        self,
        prompt: str,
        output_schema: type[Any],
        tier: Any,
        stage: str,
        response_method: str = "json_schema",
    ) -> Any:
        """Async mirror — delegates to sync invoke_structured."""
        return self.invoke_structured(prompt, output_schema, tier, stage, response_method)

    @staticmethod
    def _track_from_prompt(prompt: str) -> Track:
        if "Track: original" in prompt:
            return Track.ORIGINAL
        if "Track: translated" in prompt:
            return Track.TRANSLATED
        raise AssertionError("prompt did not include track")

    @staticmethod
    def _document_text_from_prompt(prompt: str) -> str:
        for marker in ("DOCUMENT BLOCKS:\n", "DOCUMENT TEXT:\n"):
            if marker in prompt:
                return prompt.split(marker, maxsplit=1)[1]
        raise AssertionError("prompt did not include document body")

    @staticmethod
    def _span_for_offset(text: str, snippet: str, start: int, track: Track) -> PageSpan:
        end = start + len(snippet)
        span_id = f"{track.value}-p1"
        if end <= len(text):
            return PageSpan(span_id=span_id, page=1, start_offset=0, end_offset=len(text))
        raise AssertionError("snippet outside document text")


@pytest.mark.asyncio
@pytest.mark.skipif(not _FABRY_OUTPUT_READY, reason="Fabry output fixture is not available in this worktree")
async def test_fabry_output_fixture_runs_original_and_translated_tracks_independently(mock_config: MagicMock):
    documents = EvidenceExtractionService.build_dual_documents_from_output_dir(_FABRY_OUTPUT_DIR)
    provider = FabryFixtureProvider()
    service = EvidenceExtractionService(cfg=mock_config)
    service._workflow = EvidenceExtractionWorkflow(provider=provider, extraction_mode="catalog")

    result = await service.run_dual(documents)

    assert result.document_id == "法布雷病1例"
    assert result.original_result.track == Track.ORIGINAL
    assert result.translated_result.track == Track.TRANSLATED
    original_diagnosis = next(
        item for item in result.original_result.evidence_items if item.field_id == "B.disease_diagnosis"
    )
    translated_diagnosis = next(
        item for item in result.translated_result.evidence_items if item.field_id == "B.disease_diagnosis"
    )
    assert original_diagnosis.value == "法布雷病"
    assert translated_diagnosis.value == "Fabry disease"
    assert "法布雷病" in documents.original.formatted_text
    assert "Fabry disease" in documents.translated.formatted_text
    assert documents.original.formatted_text != documents.translated.formatted_text
    assert [span.page for span in documents.original.page_spans] == [1, 2, 3, 4]
    assert [span.page for span in documents.translated.page_spans] == [1, 2, 3, 4]
    # Tracks run in parallel, so call order is non-deterministic.
    # catalog_extraction dispatches per group (catalog_extraction/<group>[/<chunk>]);
    # verify each track touched relevance_scan, catalog_extraction, and special_evidence,
    # with catalog_extraction called once per LLM-extractable group (high_signal, supporting).
    from collections import Counter

    stage_types: dict[tuple[str, Track], int] = Counter(
        (stage.split("/", 1)[0], track) for stage, track in provider.calls
    )
    expected_stage_types = {
        ("relevance_scan", Track.ORIGINAL): 1,
        ("catalog_extraction", Track.ORIGINAL): 2,
        ("special_evidence", Track.ORIGINAL): 1,
        ("clinical_context", Track.ORIGINAL): 1,
        ("relevance_scan", Track.TRANSLATED): 1,
        ("catalog_extraction", Track.TRANSLATED): 2,
        ("special_evidence", Track.TRANSLATED): 1,
        ("clinical_context", Track.TRANSLATED): 1,
    }
    assert stage_types == expected_stage_types
