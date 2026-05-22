from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import EvidenceExtractionService
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    Track,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import EvidenceExtractionWorkflow


_BACKEND_DIR = Path(__file__).resolve().parents[4]
_LEGACY_FABRY_OUTPUT_DIR = _BACKEND_DIR / "output" / "zh" / "法布雷病1例"
_CROSS_LINGUAL_FABRY_OUTPUT_DIR = _BACKEND_DIR / "output" / "cross_lingual" / "zh" / "法布雷病1例"
_FABRY_OUTPUT_DIR = (
    _LEGACY_FABRY_OUTPUT_DIR
    if _LEGACY_FABRY_OUTPUT_DIR.exists()
    else _CROSS_LINGUAL_FABRY_OUTPUT_DIR
)


@pytest.fixture
def mock_config() -> MagicMock:
    cfg = MagicMock()
    cfg.evidence_extraction.api_key = "key"
    cfg.evidence_extraction.base_url = "http://localhost:8001/v1"
    cfg.evidence_extraction.fast_model = "fast"
    cfg.evidence_extraction.standard_model = "standard"
    cfg.evidence_extraction.strong_model = "strong"
    cfg.evidence_extraction.temperature = 0.0
    cfg.evidence_extraction.timeout = 60
    cfg.evidence_extraction.max_retries = 3
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
    ) -> Any:
        track = self._track_from_prompt(prompt)
        self.calls.append((stage, track))
        if stage == "evidence_map":
            return DocumentEvidenceMap(
                relevant=True,
                disease_terms=["法布雷病"] if track == Track.ORIGINAL else ["Fabry disease"],
                gene_terms=["GLA"],
            )
        if stage == "catalog_extraction":
            text = self._document_text_from_prompt(prompt)
            snippet = "法布雷病" if track == Track.ORIGINAL else "Fabry disease"
            start = text.index(snippet)
            return [
                EvidenceItem(
                    field_id="A.disease_name",
                    category="A",
                    field_name="Disease name",
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
        if stage == "special_evidence":
            return []
        raise AssertionError(f"unexpected stage: {stage}")

    @staticmethod
    def _track_from_prompt(prompt: str) -> Track:
        if "Track: original" in prompt:
            return Track.ORIGINAL
        if "Track: translated" in prompt:
            return Track.TRANSLATED
        raise AssertionError("prompt did not include track")

    @staticmethod
    def _document_text_from_prompt(prompt: str) -> str:
        marker = "DOCUMENT TEXT:\n"
        return prompt.split(marker, maxsplit=1)[1]

    @staticmethod
    def _span_for_offset(text: str, snippet: str, start: int, track: Track) -> PageSpan:
        end = start + len(snippet)
        span_id = f"{track.value}-p1"
        if end <= len(text):
            return PageSpan(span_id=span_id, page=1, start_offset=0, end_offset=len(text))
        raise AssertionError("snippet outside document text")


@pytest.mark.asyncio
async def test_fabry_output_fixture_runs_original_and_translated_tracks_independently(mock_config: MagicMock):
    documents = EvidenceExtractionService.build_dual_documents_from_output_dir(_FABRY_OUTPUT_DIR)
    provider = FabryFixtureProvider()
    service = EvidenceExtractionService(cfg=mock_config)
    service._workflow = EvidenceExtractionWorkflow(provider=provider)

    result = await service.run_dual(documents)

    assert result.document_id == "法布雷病1例"
    assert result.original_result.track == Track.ORIGINAL
    assert result.translated_result.track == Track.TRANSLATED
    assert result.original_result.evidence_items[0].value == "法布雷病"
    assert result.translated_result.evidence_items[0].value == "Fabry disease"
    assert "法布雷病" in documents.original.formatted_text
    assert "Fabry disease" in documents.translated.formatted_text
    assert documents.original.formatted_text != documents.translated.formatted_text
    assert [span.page for span in documents.original.page_spans] == [1, 2, 3, 4]
    assert [span.page for span in documents.translated.page_spans] == [1, 2, 3, 4]
    assert provider.calls == [
        ("evidence_map", Track.ORIGINAL),
        ("catalog_extraction", Track.ORIGINAL),
        ("special_evidence", Track.ORIGINAL),
        ("evidence_map", Track.TRANSLATED),
        ("catalog_extraction", Track.TRANSLATED),
        ("special_evidence", Track.TRANSLATED),
    ]
