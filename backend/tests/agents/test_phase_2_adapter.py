"""Tests for Phase 2 adapter (translation + evidence extraction)."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.contracts import (
    PipelineGraphState,
    PipelineMode,
    SourceType,
    Phase1Output,
    Phase2Output,
    RetryablePhaseError,
)
from src.agents.phase_2_adapter import Phase2Adapter


@pytest.fixture
def sample_state(tmp_path) -> PipelineGraphState:
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"pages": [], "content_blocks": []}))
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        ExtractionTarget,
    )

    return PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        phase_1_output=Phase1Output(
            pdf_path=str(tmp_path / "test.pdf"),
            md_path=str(tmp_path / "test.md"),
            metadata_path=str(metadata),
            output_dir=str(tmp_path / "output"),
            images_dir=str(tmp_path / "images"),
        ),
        extraction_target=ExtractionTarget(
            gene_symbol="ABCA3",
            disease_name="ABCA3 deficiency",
        ),
    )



@pytest.mark.asyncio
async def test_phase_2_adapter_success(sample_state: PipelineGraphState):
    """Phase 2 adapter successfully translates and extracts evidence."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import (
        TranslationResult,
        CrossLingualOutput,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        DualEvidenceExtractionResult,
        DualTrackDocuments,
        EvidenceExtractionResult,
        EvidenceExtractionStatus,
        Track,
        DocumentEvidenceMap,
        TrackDocument,
    )

    mock_translation = MagicMock()
    mock_translation.run = AsyncMock(
        return_value=TranslationResult(
            formatted_original="Original text",
            translated_english="Translated text",
            source_language="zh",
            terminology_map={},
            translation_warnings=[],
            sentences=[],
            segments=[],
        )
    )
    mock_translation.save = MagicMock(
        return_value=CrossLingualOutput(
            formatted_original="Original text",
            translated_english="Translated text",
            source_language="zh",
            terminology_map={},
            translation_warnings=[],
            output_dir="/tmp/phase2/output",
            original_json_path="/tmp/phase2/output/original.json",
            translated_json_path="/tmp/phase2/output/translated.json",
            image_paths=[],
        )
    )

    mock_extraction_service = MagicMock()
    mock_extraction_service.run_dual = AsyncMock(
        return_value=DualEvidenceExtractionResult(
            document_id="doc-456",
            original_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-456",
                track=Track.ORIGINAL,
                evidence_map=DocumentEvidenceMap(relevant=True),
            ),
            translated_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-456",
                track=Track.TRANSLATED,
                evidence_map=DocumentEvidenceMap(relevant=True),
            ),
        )
    )

    adapter = Phase2Adapter(
        translation_service=mock_translation,
        extraction_service=mock_extraction_service,
    )

    with patch(
        "src.agents.phase_2_adapter.EvidenceExtractionService.build_dual_documents_from_output_dir"
    ) as mock_build:
        mock_build.return_value = DualTrackDocuments(
            document_id="doc-456",
            original=TrackDocument(
                document_id="doc-456",
                track=Track.ORIGINAL,
                formatted_text="original",
                page_spans=[],
            ),
            translated=TrackDocument(
                document_id="doc-456",
                track=Track.TRANSLATED,
                formatted_text="translated",
                page_spans=[],
            ),
        )

        result_state = await adapter.run(sample_state)

    assert result_state.phase_2_output is not None
    assert result_state.phase_2_output.source_language == "zh"
    assert isinstance(result_state.phase_2_output, Phase2Output)
    mock_build.assert_called_once()
    assert mock_build.call_args.args[1] == sample_state.extraction_target


@pytest.mark.asyncio
async def test_phase_2_adapter_passes_review_reject_policy(
    sample_state: PipelineGraphState,
):
    """Phase 2 forwards review reject policy to evidence extraction."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import (
        CrossLingualOutput,
        TranslationResult,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        DualEvidenceExtractionResult,
        DualTrackDocuments,
        EvidenceExtractionResult,
        EvidenceExtractionStatus,
        Track,
        TrackDocument,
    )

    state = sample_state.model_copy(update={"review_reject_policy": "tristate_review"})
    mock_translation = MagicMock()
    mock_translation.run = AsyncMock(
        return_value=TranslationResult(
            formatted_original="Original text",
            translated_english="Translated text",
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            sentences=[],
            segments=[],
        )
    )
    mock_translation.save = MagicMock(
        return_value=CrossLingualOutput(
            formatted_original="Original text",
            translated_english="Translated text",
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            output_dir="/tmp/phase2/output",
            original_json_path="/tmp/phase2/output/original.json",
            translated_json_path="/tmp/phase2/output/translated.json",
            image_paths=[],
        )
    )
    mock_extraction_service = MagicMock()
    mock_extraction_service.run_dual = AsyncMock(
        return_value=DualEvidenceExtractionResult(
            document_id="doc-456",
            original_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-456",
                track=Track.ORIGINAL,
            ),
            translated_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-456",
                track=Track.TRANSLATED,
            ),
        )
    )
    adapter = Phase2Adapter(
        translation_service=mock_translation,
        extraction_service=mock_extraction_service,
    )

    with patch(
        "src.agents.phase_2_adapter.EvidenceExtractionService.build_dual_documents_from_output_dir"
    ) as mock_build:
        mock_build.return_value = DualTrackDocuments(
            document_id="doc-456",
            original=TrackDocument(
                document_id="doc-456",
                track=Track.ORIGINAL,
                formatted_text="original",
                page_spans=[],
            ),
            translated=TrackDocument(
                document_id="doc-456",
                track=Track.TRANSLATED,
                formatted_text="translated",
                page_spans=[],
            ),
        )

        await adapter.run(state)

    assert mock_extraction_service.run_dual.call_args.kwargs["review_reject_policy"] == "tristate_review"


@pytest.mark.asyncio
async def test_phase_2_adapter_passes_extraction_track_mode(
    sample_state: PipelineGraphState,
):
    """Phase 2 forwards the English-pivot extraction track mode."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import (
        CrossLingualOutput,
        TranslationResult,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        DualEvidenceExtractionResult,
        DualTrackDocuments,
        EvidenceExtractionResult,
        EvidenceExtractionStatus,
        Track,
        TrackDocument,
    )

    state = sample_state.model_copy(update={"extraction_track_mode": "english_pivot"})
    mock_translation = MagicMock()
    mock_translation.run = AsyncMock(
        return_value=TranslationResult(
            formatted_original="Original text",
            translated_english="Translated text",
            source_language="zh",
            terminology_map={},
            translation_warnings=[],
            sentences=[],
            segments=[],
        )
    )
    mock_translation.save = MagicMock(
        return_value=CrossLingualOutput(
            formatted_original="Original text",
            translated_english="Translated text",
            source_language="zh",
            terminology_map={},
            translation_warnings=[],
            output_dir="/tmp/phase2/output",
            original_json_path="/tmp/phase2/output/original.json",
            translated_json_path="/tmp/phase2/output/translated.json",
            image_paths=[],
        )
    )
    mock_extraction_service = MagicMock()
    mock_extraction_service.run_dual = AsyncMock(
        return_value=DualEvidenceExtractionResult(
            document_id="doc-456",
            original_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.NOT_RELEVANT,
                document_id="doc-456",
                track=Track.ORIGINAL,
            ),
            translated_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-456",
                track=Track.TRANSLATED,
            ),
        )
    )
    adapter = Phase2Adapter(
        translation_service=mock_translation,
        extraction_service=mock_extraction_service,
    )

    with patch(
        "src.agents.phase_2_adapter.EvidenceExtractionService.build_dual_documents_from_output_dir"
    ) as mock_build:
        mock_build.return_value = DualTrackDocuments(
            document_id="doc-456",
            original=TrackDocument(
                document_id="doc-456",
                track=Track.ORIGINAL,
                formatted_text="original",
                page_spans=[],
            ),
            translated=TrackDocument(
                document_id="doc-456",
                track=Track.TRANSLATED,
                formatted_text="translated",
                page_spans=[],
            ),
        )

        await adapter.run(state)

    assert mock_extraction_service.run_dual.call_args.kwargs["extraction_track_mode"] == "english_pivot"



@pytest.mark.asyncio
async def test_phase_2_adapter_sets_skip_when_not_relevant(
    sample_state: PipelineGraphState,
):
    """Phase 2 adapter sets skip_phase_3_reason when both tracks are NOT_RELEVANT."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import (
        TranslationResult,
        CrossLingualOutput,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        DualEvidenceExtractionResult,
        DualTrackDocuments,
        EvidenceExtractionResult,
        EvidenceExtractionStatus,
        Track,
        TrackDocument,
    )
    from src.agents.contracts import SkipPhase3Reason

    mock_translation = MagicMock()
    mock_translation.run = AsyncMock(
        return_value=TranslationResult(
            formatted_original="Original",
            translated_english="Translated",
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            sentences=[],
            segments=[],
        )
    )
    mock_translation.save = MagicMock(
        return_value=CrossLingualOutput(
            formatted_original="Original",
            translated_english="Translated",
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            output_dir="/tmp/phase2/output",
            original_json_path="/tmp/phase2/output/original.json",
            translated_json_path="/tmp/phase2/output/translated.json",
            image_paths=[],
        )
    )

    mock_extraction_service = MagicMock()
    mock_extraction_service.run_dual = AsyncMock(
        return_value=DualEvidenceExtractionResult(
            document_id="doc-456",
            original_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.NOT_RELEVANT,
                document_id="doc-456",
                track=Track.ORIGINAL,
            ),
            translated_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.NOT_RELEVANT,
                document_id="doc-456",
                track=Track.TRANSLATED,
            ),
        )
    )

    adapter = Phase2Adapter(
        translation_service=mock_translation,
        extraction_service=mock_extraction_service,
    )

    with patch(
        "src.agents.phase_2_adapter.EvidenceExtractionService.build_dual_documents_from_output_dir"
    ) as mock_build:
        mock_build.return_value = DualTrackDocuments(
            document_id="doc-456",
            original=TrackDocument(
                document_id="doc-456",
                track=Track.ORIGINAL,
                formatted_text="original",
                page_spans=[],
            ),
            translated=TrackDocument(
                document_id="doc-456",
                track=Track.TRANSLATED,
                formatted_text="translated",
                page_spans=[],
            ),
        )

        result_state = await adapter.run(sample_state)

    assert result_state.skip_phase_3_reason == SkipPhase3Reason.NOT_RELEVANT


@pytest.mark.asyncio
async def test_phase_2_adapter_raises_retryable_on_api_timeout(
    sample_state: PipelineGraphState,
):
    """Phase 2 adapter raises RetryablePhaseError on OpenAI API timeout."""
    import openai

    mock_translation = MagicMock()
    mock_translation.run = AsyncMock(
        side_effect=openai.APITimeoutError(request=None)
    )

    mock_extraction_service = MagicMock()

    adapter = Phase2Adapter(
        translation_service=mock_translation,
        extraction_service=mock_extraction_service,
    )

    with pytest.raises(RetryablePhaseError):
        await adapter.run(sample_state)


@pytest.mark.asyncio
async def test_phase2_adapter_reads_metadata_async(tmp_path, monkeypatch):
    """Phase 2 adapter uses aiofiles to read/write, not sync open()."""
    import aiofiles

    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"pages": [], "content_blocks": []}))
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        phase_1_output=Phase1Output(
            pdf_path=str(tmp_path / "test.pdf"),
            md_path=str(tmp_path / "test.md"),
            metadata_path=str(metadata),
            output_dir=str(tmp_path / "output"),
            images_dir=str(tmp_path / "images"),
        ),
    )

    from src.core.cross_lingual_process_and_extract_evidence.contracts import (
        TranslationResult,
        CrossLingualOutput,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        DualEvidenceExtractionResult,
        DualTrackDocuments,
        EvidenceExtractionResult,
        EvidenceExtractionStatus,
        Track,
        DocumentEvidenceMap,
        TrackDocument,
    )

    mock_translation = MagicMock()
    mock_translation.run = AsyncMock(
        return_value=TranslationResult(
            formatted_original="Original",
            translated_english="Translated",
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            sentences=[],
            segments=[],
        )
    )
    mock_translation.save = MagicMock(
        return_value=CrossLingualOutput(
            formatted_original="Original",
            translated_english="Translated",
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            output_dir="/tmp/phase2/output",
            original_json_path="/tmp/phase2/output/original.json",
            translated_json_path="/tmp/phase2/output/translated.json",
            image_paths=[],
        )
    )

    mock_extraction_service = MagicMock()
    mock_extraction_service.run_dual = AsyncMock(
        return_value=DualEvidenceExtractionResult(
            document_id="doc-456",
            original_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-456",
                track=Track.ORIGINAL,
                evidence_map=DocumentEvidenceMap(relevant=True),
            ),
            translated_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-456",
                track=Track.TRANSLATED,
                evidence_map=DocumentEvidenceMap(relevant=True),
            ),
        )
    )

    adapter = Phase2Adapter(
        translation_service=mock_translation,
        extraction_service=mock_extraction_service,
    )

    # Patch aiofiles.open to verify it's called (not sync open)
    original_open = aiofiles.open
    call_log = []

    def spy_open(*a, **kw):
        call_log.append(a)
        return original_open(*a, **kw)

    monkeypatch.setattr(aiofiles, "open", spy_open)

    with patch(
        "src.agents.phase_2_adapter.EvidenceExtractionService.build_dual_documents_from_output_dir"
    ) as mock_build:
        mock_build.return_value = DualTrackDocuments(
            document_id="doc-456",
            original=TrackDocument(
                document_id="doc-456",
                track=Track.ORIGINAL,
                formatted_text="original",
                page_spans=[],
            ),
            translated=TrackDocument(
                document_id="doc-456",
                track=Track.TRANSLATED,
                formatted_text="translated",
                page_spans=[],
            ),
        )

        result = await asyncio.wait_for(adapter.run(state), timeout=5.0)

    assert result.phase_2_output is not None
    assert len(call_log) >= 1, "Expected aiofiles.open to be called"


@pytest.mark.asyncio
async def test_phase_2_adapter_raises_retryable_on_catalog_extraction_error(
    sample_state: PipelineGraphState,
):
    """CatalogExtractionError is classified as retryable, not permanent.

    This is intentional: LLM API timeouts (the primary cause) are transient
    and should be retried by the orchestrator.
    """
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import (
        CatalogExtractionError,
    )

    mock_translation = MagicMock()
    mock_translation.run = AsyncMock(
        side_effect=CatalogExtractionError("All 2 extraction chunks failed, last error: timeout")
    )

    mock_extraction_service = MagicMock()

    adapter = Phase2Adapter(
        translation_service=mock_translation,
        extraction_service=mock_extraction_service,
    )

    with pytest.raises(RetryablePhaseError, match="Phase 2 transient error"):
        await adapter.run(sample_state)
