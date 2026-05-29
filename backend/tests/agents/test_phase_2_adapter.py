"""Tests for Phase 2 adapter (translation + evidence extraction)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    Phase1Output,
    Phase2Output,
    RetryablePhaseError,
    PermanentPhaseError,
)
from src.agents.phase_2_adapter import Phase2Adapter


@pytest.fixture
def sample_state() -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        phase_1_output=Phase1Output(
            pdf_path="/tmp/test.pdf",
            md_path="/tmp/test.md",
            metadata_path="/tmp/test.json",
            output_dir="/tmp/output",
            images_dir="/tmp/images",
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

        with patch("builtins.open", MagicMock()):
            with patch("json.load", return_value={"pages": [], "content_blocks": []}):
                result_state = await adapter.run(sample_state)

    assert result_state.phase_2_output is not None
    assert result_state.phase_2_output.source_language == "zh"
    assert isinstance(result_state.phase_2_output, Phase2Output)


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

        with patch("builtins.open", MagicMock()):
            with patch("json.load", return_value={"pages": [], "content_blocks": []}):
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
