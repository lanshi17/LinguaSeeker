"""Tests for Phase 3 adapter (entity standardization)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    Phase2Output,
    Phase3Output,
    PermanentPhaseError,
    SkipPhase3Reason,
)
from src.agents.phase_3_adapter import Phase3Adapter


@pytest.fixture
def sample_state() -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        phase_2_output=Phase2Output(
            output_dir="/tmp/phase2/output",
            original_json_path="/tmp/phase2/output/original.json",
            translated_json_path="/tmp/phase2/output/translated.json",
            extraction_result_path="/tmp/extraction.json",
            source_language="zh",
        ),
    )


@pytest.mark.asyncio
async def test_phase_3_adapter_success(sample_state: PipelineGraphState):
    """Phase 3 adapter successfully standardizes entities."""
    from src.core.standardize_entities_and_align_knowledge.contracts import (
        StandardizationResult,
    )

    mock_standardization = MagicMock()
    mock_standardization.run_dual_result = AsyncMock(
        return_value=StandardizationResult(
            document_id="doc-456",
            match_count=10,
            standardized_count=8,
            ambiguous_count=1,
            unmapped_count=1,
            normalized_entity_ids=("entity-1", "entity-2"),
            matches=(),
        )
    )

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    adapter = Phase3Adapter(
        standardization_service=mock_standardization,
        session_factory=mock_session_factory,
    )

    with patch("builtins.open", MagicMock()):
        with patch("json.load", return_value={}):
            with patch(
                "src.agents.phase_3_adapter.DualEvidenceExtractionResult.model_validate",
                return_value=MagicMock(),
            ):
                result_state = await adapter.run(sample_state)

    assert result_state.phase_3_output is not None
    assert result_state.phase_3_output.match_count == 10
    assert isinstance(result_state.phase_3_output, Phase3Output)


@pytest.mark.asyncio
async def test_phase_3_adapter_skipped_not_relevant(sample_state: PipelineGraphState):
    """Phase 3 adapter skips when skip_phase_3_reason is NOT_RELEVANT."""
    sample_state.skip_phase_3_reason = SkipPhase3Reason.NOT_RELEVANT

    mock_standardization = MagicMock()
    mock_standardization.run_dual_result = AsyncMock()

    mock_session_factory = MagicMock()
    adapter = Phase3Adapter(
        standardization_service=mock_standardization,
        session_factory=mock_session_factory,
    )

    result_state = await adapter.run(sample_state)

    assert result_state.phase_3_status.status == PhaseStatus.SKIPPED
    assert result_state.phase_3_status.summary == {"reason": "not_relevant"}
    mock_standardization.run_dual_result.assert_not_called()


@pytest.mark.asyncio
async def test_phase_3_adapter_skipped_no_entities(sample_state: PipelineGraphState):
    """Phase 3 adapter skips when skip_phase_3_reason is NO_ENTITIES."""
    sample_state.skip_phase_3_reason = SkipPhase3Reason.NO_ENTITIES

    mock_standardization = MagicMock()

    mock_session_factory = MagicMock()
    adapter = Phase3Adapter(
        standardization_service=mock_standardization,
        session_factory=mock_session_factory,
    )

    result_state = await adapter.run(sample_state)

    assert result_state.phase_3_status.status == PhaseStatus.SKIPPED
    assert result_state.phase_3_status.summary == {"reason": "no_entities"}


@pytest.mark.asyncio
async def test_phase_3_adapter_skipped_when_zero_standardized(
    sample_state: PipelineGraphState,
):
    """Phase 3 adapter sets skip reason when standardized_count == 0."""
    from src.core.standardize_entities_and_align_knowledge.contracts import (
        StandardizationResult,
    )

    mock_standardization = MagicMock()
    mock_standardization.run_dual_result = AsyncMock(
        return_value=StandardizationResult(
            document_id="doc-456",
            match_count=0,
            standardized_count=0,
            ambiguous_count=0,
            unmapped_count=0,
            normalized_entity_ids=(),
            matches=(),
        )
    )

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    adapter = Phase3Adapter(
        standardization_service=mock_standardization,
        session_factory=mock_session_factory,
    )

    with patch("builtins.open", MagicMock()):
        with patch("json.load", return_value={}):
            with patch(
                "src.agents.phase_3_adapter.DualEvidenceExtractionResult.model_validate",
                return_value=MagicMock(),
            ):
                result_state = await adapter.run(sample_state)

    assert result_state.phase_3_status.status == PhaseStatus.COMPLETED
    assert result_state.skip_phase_3_reason == SkipPhase3Reason.NO_CANDIDATES
    assert result_state.phase_3_status.summary["skip_reason"] == "no_candidates"
