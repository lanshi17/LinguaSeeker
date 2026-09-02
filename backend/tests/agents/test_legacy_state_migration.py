"""Tests for legacy 3-phase pipeline state migration.

``PipelineGraphState.model_validate`` transparently migrates state JSON
persisted before the 4-phase split (1=acquire+parse, 2=translate+extract,
3=standardize) to the new schema (1=acquire, 2=parse, 3=translate+extract,
4=standardize).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.contracts import (
    PipelineGraphState,
    PipelineMode,
    PipelineStatus,
    SourceType,
    validate_all_phase_transitions,
)
from src.agents.state_persistence import DirectStatePersistence


def _legacy_state_dict() -> dict:
    """A 3-phase state dict as persisted before the 4-phase split."""
    return {
        "processing_run_id": str(uuid.uuid4()),
        "source_document_id": str(uuid.uuid4()),
        "mode": "full",
        "source_type": "local",
        "pipeline_status": "running",
        "phase_1_status": {"status": "completed", "started_at": "2026-06-01T10:00:00"},
        "phase_2_status": {"status": "running"},
        "phase_3_status": {"status": "pending"},
        "phase_1_output": {
            "pdf_path": "/tmp/input.pdf",
            "md_path": "/tmp/output.md",
            "metadata_path": "/tmp/metadata.json",
            "output_dir": "/tmp/phase_1",
            "images_dir": "/tmp/images",
        },
        "phase_2_output": {
            "output_dir": "/tmp/phase_2",
            "original_json_path": "/tmp/phase_2/original.json",
            "translated_json_path": "/tmp/phase_2/translated.json",
            "source_language": "zh",
            "extraction_result_path": "/tmp/phase_2/extraction_result.json",
        },
        "phase_3_output": {
            "match_count": 2,
            "standardized_count": 1,
            "ambiguous_count": 1,
            "unmapped_count": 0,
        },
        "skip_phase_3_reason": "not_relevant",
    }


class TestLegacyStateMigration:
    """model_validate migrates legacy 3-phase state JSON dicts."""

    def test_statuses_shift(self):
        state = PipelineGraphState.model_validate(_legacy_state_dict())

        # Legacy 1 (acquire+parse) maps onto both new phase 1 and 2.
        assert state.phase_1_status.status.value == "completed"
        assert state.phase_2_status.status.value == "completed"
        assert state.phase_1_status.started_at == "2026-06-01T10:00:00"
        assert state.phase_2_status.started_at == "2026-06-01T10:00:00"
        # Legacy 2 → new 3, legacy 3 → new 4.
        assert state.phase_3_status.status.value == "running"
        assert state.phase_4_status.status.value == "pending"

    def test_phase_1_output_splits_into_acquisition_and_parse(self):
        state = PipelineGraphState.model_validate(_legacy_state_dict())

        assert state.phase_1_output is not None
        assert state.phase_1_output.pdf_path == "/tmp/input.pdf"
        assert not hasattr(state.phase_1_output, "md_path")

        assert state.phase_2_output is not None
        assert state.phase_2_output.md_path == "/tmp/output.md"
        assert state.phase_2_output.metadata_path == "/tmp/metadata.json"
        assert state.phase_2_output.output_dir == "/tmp/phase_1"
        assert state.phase_2_output.images_dir == "/tmp/images"

    def test_outputs_shift(self):
        state = PipelineGraphState.model_validate(_legacy_state_dict())

        assert state.phase_3_output is not None
        assert state.phase_3_output.source_language == "zh"
        assert state.phase_3_output.extraction_result_path == "/tmp/phase_2/extraction_result.json"

        assert state.phase_4_output is not None
        assert state.phase_4_output.match_count == 2
        assert state.phase_4_output.standardized_count == 1

    def test_skip_reason_renamed(self):
        state = PipelineGraphState.model_validate(_legacy_state_dict())
        assert state.skip_phase_4_reason is not None
        assert state.skip_phase_4_reason.value == "not_relevant"
        assert not hasattr(state, "skip_phase_3_reason")

    def test_idempotent_round_trip(self):
        """Migrated state dumped and re-validated is unchanged."""
        first = PipelineGraphState.model_validate(_legacy_state_dict())
        second = PipelineGraphState.model_validate(first.model_dump(mode="json"))

        assert second.model_dump(mode="json") == first.model_dump(mode="json")

    def test_new_format_state_passes_through(self):
        """New-format dicts (with phase_4_status) are not migrated."""
        new_state = PipelineGraphState(
            processing_run_id=str(uuid.uuid4()),
            source_document_id=str(uuid.uuid4()),
            mode=PipelineMode.FULL,
            source_type=SourceType.LOCAL,
            pipeline_status=PipelineStatus.RUNNING,
        )
        dumped = new_state.model_dump(mode="json")
        # Force legacy-looking outputs that must NOT be split again.
        dumped["phase_2_output"] = {"md_path": "/tmp/x.md", "metadata_path": "/tmp/x.json", "output_dir": "/tmp/x"}

        loaded = PipelineGraphState.model_validate(dumped)

        assert loaded.phase_1_status == new_state.phase_1_status
        assert loaded.phase_4_status == new_state.phase_4_status
        assert loaded.phase_2_output.md_path == "/tmp/x.md"
        assert loaded.phase_1_output is None  # not re-derived from phase_2


class TestLegacyStateMigrationPersistence:
    """Migrated states keep working with the persistence layer transition guard."""

    @pytest.mark.asyncio
    async def test_migrated_state_round_trips_through_db(self, db_session: AsyncSession):
        """A legacy-loaded state saved to PostgreSQL passes the transition guard."""
        state = PipelineGraphState.model_validate(_legacy_state_dict())
        state.pipeline_status = PipelineStatus.RUNNING

        persistence = DirectStatePersistence(db_session)
        await persistence.save(state)  # Should not raise

        loaded = await persistence.load(state.processing_run_id)
        assert loaded is not None
        assert loaded.phase_1_output is not None
        assert loaded.phase_1_output.pdf_path == "/tmp/input.pdf"
        assert loaded.phase_2_output is not None
        assert loaded.phase_2_output.md_path == "/tmp/output.md"
        assert loaded.phase_3_output is not None
        assert loaded.phase_4_output is not None
        assert loaded.skip_phase_4_reason is not None

    @pytest.mark.asyncio
    async def test_resave_of_loaded_state_passes_guard(self, db_session: AsyncSession):
        """Re-saving an identical migrated state is a legal identity transition."""
        state = PipelineGraphState.model_validate(_legacy_state_dict())
        state.pipeline_status = PipelineStatus.RUNNING

        persistence = DirectStatePersistence(db_session)
        await persistence.save(state)

        reloaded = await persistence.load(state.processing_run_id)
        assert reloaded is not None
        await persistence.save(reloaded)  # Identity transitions must not raise

    def test_migrated_state_passes_transition_guard_against_itself(self):
        """validate_all_phase_transitions accepts a migrated state vs its reload."""
        state = PipelineGraphState.model_validate(_legacy_state_dict())
        revalidated = PipelineGraphState.model_validate(state.model_dump(mode="json"))

        validate_all_phase_transitions(state, revalidated)  # Should not raise
