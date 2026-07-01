"""Tests for pipeline state persistence layer."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.contracts import (
    Phase2Output,
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    PipelineStatus,
    PhaseStatusDetail,
    PhaseErrorDetail,
)
from src.agents.state_persistence import DirectStatePersistence, SessionBoundStatePersistence


def _make_session_factory(session: AsyncSession):
    """Wrap a single session as an async_sessionmaker-compatible factory."""

    @asynccontextmanager
    async def _factory():
        yield session

    return _factory


@pytest.fixture
def sample_state() -> PipelineGraphState:
    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    state.phase_1_status = PhaseStatusDetail(
        status=PhaseStatus.COMPLETED,
        started_at="2026-05-29T10:00:00",
    )
    state.phase_2_status = PhaseStatusDetail(
        status=PhaseStatus.RUNNING,
    )
    return state


@pytest.mark.asyncio
async def test_save_state(db_session: AsyncSession, sample_state: PipelineGraphState):
    """DirectStatePersistence can save state to database."""
    service = DirectStatePersistence(db_session)
    await service.save(sample_state)

    loaded = await service.load(sample_state.processing_run_id)
    assert loaded is not None
    assert loaded.processing_run_id == sample_state.processing_run_id
    assert loaded.phase_1_status.status == PhaseStatus.COMPLETED
    assert loaded.phase_2_status.status == PhaseStatus.RUNNING


@pytest.mark.asyncio
async def test_load_nonexistent_state(db_session: AsyncSession):
    """Loading nonexistent state returns None."""
    service = DirectStatePersistence(db_session)
    loaded = await service.load(str(uuid.uuid4()))
    assert loaded is None


@pytest.mark.asyncio
async def test_save_state_idempotent(db_session: AsyncSession, sample_state: PipelineGraphState):
    """Saving state multiple times updates the record (checkpoint semantics)."""
    service = DirectStatePersistence(db_session)
    await service.save(sample_state)

    sample_state.phase_2_status = PhaseStatusDetail(
        status=PhaseStatus.COMPLETED,
        duration_seconds=120.0,
    )
    await service.save(sample_state)

    loaded = await service.load(sample_state.processing_run_id)
    assert loaded.phase_2_status.status == PhaseStatus.COMPLETED
    assert loaded.phase_2_status.duration_seconds == 120.0


@pytest.mark.asyncio
async def test_save_preserves_structured_errors(db_session: AsyncSession, sample_state: PipelineGraphState):
    """Structured error details survive round-trip through database."""
    sample_state.phase_1_status = PhaseStatusDetail(
        status=PhaseStatus.FAILED,
        error=PhaseErrorDetail(
            message="API timeout",
            retryable=True,
            attempt=2,
            max_retries=2,
        ),
    )

    service = DirectStatePersistence(db_session)
    await service.save(sample_state)

    loaded = await service.load(sample_state.processing_run_id)
    assert loaded.phase_1_status.error is not None
    assert loaded.phase_1_status.error.retryable is True
    assert loaded.phase_1_status.error.attempt == 2


@pytest.mark.asyncio
async def test_session_bound_save_uses_upsert():
    """SessionBoundStatePersistence.save() uses INSERT ON CONFLICT for writes.

    Note: save() now reads the existing state first for the state transition
    guard (one extra SELECT), but the write path still uses upsert for atomicity.
    """
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    # Transition guard reads existing state — return None (new run)
    mock_session.get = AsyncMock(return_value=None)

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    persistence = SessionBoundStatePersistence(mock_factory)

    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
    )

    await persistence.save(state)

    # Verify execute was called (INSERT ... ON CONFLICT upsert)
    mock_session.execute.assert_awaited()
    # session.get is called for the state transition guard
    mock_session.get.assert_awaited()
    # session.add is NOT used — writes go through upsert
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_session_bound_save_does_not_mutate_inline_phase2_payload():
    """Persisting state must trim JSONB via a copy, not mutate live state."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    persistence = SessionBoundStatePersistence(mock_factory)
    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
        phase_2_status=PhaseStatusDetail(status=PhaseStatus.COMPLETED),
        phase_2_output=Phase2Output(
            output_dir="/tmp/phase_2",
            original_json_path="/tmp/phase_2/original.json",
            translated_json_path="/tmp/phase_2/translated.json",
            source_language="zh",
            extraction_result_path="/tmp/phase_2/extraction_result.json",
            original_text="original text",
            translated_text="translated text",
            original_blocks=[{"type": "text", "text": "original"}],
            translated_blocks=[{"type": "text", "text": "translated"}],
        ),
    )

    await persistence.save(state)

    assert state.phase_2_output is not None
    assert state.phase_2_output.original_text == "original text"
    assert state.phase_2_output.translated_text == "translated text"
    assert state.phase_2_output.original_blocks == [{"type": "text", "text": "original"}]
    assert state.phase_2_output.translated_blocks == [{"type": "text", "text": "translated"}]


@pytest.mark.asyncio
async def test_recover_orphaned_runs_ignores_fresh_heartbeat(db_session: AsyncSession):
    """Recovery must not fail runs with a recent heartbeat."""
    persistence = SessionBoundStatePersistence(_make_session_factory(db_session))

    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
    )
    await persistence.save(
        state,
        owner_worker_id="worker-a",
        heartbeat_at=datetime.now(timezone.utc),
    )

    recovered = await persistence.recover_orphaned_runs(heartbeat_timeout_seconds=120)

    assert recovered == 0
    loaded = await persistence.load(state.processing_run_id)
    assert loaded is not None
    assert loaded.pipeline_status == PipelineStatus.RUNNING


@pytest.mark.asyncio
async def test_recover_orphaned_runs_fails_stale_heartbeat(db_session: AsyncSession):
    """Recovery must fail runs whose heartbeat is older than the timeout."""
    persistence = SessionBoundStatePersistence(_make_session_factory(db_session))

    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
    )
    await persistence.save(
        state,
        owner_worker_id="worker-a",
        heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )

    recovered = await persistence.recover_orphaned_runs(heartbeat_timeout_seconds=120)

    assert recovered == 1
    loaded = await persistence.load(state.processing_run_id)
    assert loaded is not None
    assert loaded.pipeline_status == PipelineStatus.FAILED
    assert loaded.error_message == "Pipeline heartbeat expired"


@pytest.mark.asyncio
async def test_build_raw_metadata_extracts_title(tmp_path):
    """_build_raw_metadata reads title/authors/journal from Phase 1 metadata.json."""
    import json
    from src.agents.contracts import Phase1Output
    from src.agents.state_persistence import _build_raw_metadata

    meta_path = tmp_path / "metadata.json"
    meta_path.write_text(
        json.dumps({"title": "Rett Syndrome Study", "authors": ["Doe J"], "journal": "Nature"}),
        encoding="utf-8",
    )

    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    state.phase_1_output = Phase1Output(
        pdf_path="",
        md_path=str(tmp_path / "output.md"),
        metadata_path=str(meta_path),
        output_dir=str(tmp_path),
    )

    raw_meta = await _build_raw_metadata(state)
    assert raw_meta["title"] == "Rett Syndrome Study"
    assert raw_meta["authors"] == ["Doe J"]
    assert raw_meta["journal"] == "Nature"


@pytest.mark.asyncio
async def test_build_raw_metadata_handles_missing_file(tmp_path):
    """Missing metadata file is handled gracefully — returns empty dict."""
    from src.agents.contracts import Phase1Output
    from src.agents.state_persistence import _build_raw_metadata

    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    state.phase_1_output = Phase1Output(
        pdf_path="",
        md_path="",
        metadata_path=str(tmp_path / "nonexistent.json"),
        output_dir=str(tmp_path),
    )

    assert await _build_raw_metadata(state) == {}


@pytest.mark.asyncio
async def test_build_raw_metadata_no_phase_1_output():
    """When Phase 1 has not run, raw_metadata is empty (no crash)."""
    from src.agents.state_persistence import _build_raw_metadata

    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    assert await _build_raw_metadata(state) == {}


@pytest.mark.asyncio
async def test_direct_persistence_persists_title_to_source_document(db_session: AsyncSession, tmp_path):
    """DirectStatePersistence.save() persists the Phase 1 title to SourceDocument.raw_metadata."""
    import json
    from src.agents.contracts import Phase1Output
    from src.dao.postgresql.models import SourceDocument

    meta_path = tmp_path / "metadata.json"
    meta_path.write_text(json.dumps({"title": "Variant Evidence Report"}), encoding="utf-8")

    sd_id = str(uuid.uuid4())
    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=sd_id,
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
    )
    state.phase_1_output = Phase1Output(
        pdf_path="",
        md_path=str(tmp_path / "output.md"),
        metadata_path=str(meta_path),
        output_dir=str(tmp_path),
    )

    await DirectStatePersistence(db_session).save(state)

    sd = await db_session.get(SourceDocument, uuid.UUID(sd_id))
    assert sd is not None
    assert sd.raw_metadata.get("title") == "Variant Evidence Report"


@pytest.mark.asyncio
async def test_direct_persistence_updates_title_on_existing_source_document(db_session: AsyncSession, tmp_path):
    """When SD already exists, a later save with Phase 1 title updates raw_metadata."""
    import json
    from src.agents.contracts import Phase1Output
    from src.dao.postgresql.models import SourceDocument

    sd_id = str(uuid.uuid4())
    # First save: no Phase 1 output yet — creates SD with empty metadata.
    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=sd_id,
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
    )
    await DirectStatePersistence(db_session).save(state)

    sd = await db_session.get(SourceDocument, uuid.UUID(sd_id))
    assert sd is not None
    assert "title" not in sd.raw_metadata

    # Second save: Phase 1 completed — title should now be merged in.
    meta_path = tmp_path / "metadata.json"
    meta_path.write_text(json.dumps({"title": "Late Title"}), encoding="utf-8")
    state.phase_1_output = Phase1Output(
        pdf_path="",
        md_path=str(tmp_path / "output.md"),
        metadata_path=str(meta_path),
        output_dir=str(tmp_path),
    )
    await DirectStatePersistence(db_session).save(state)

    await db_session.refresh(sd)
    assert sd.raw_metadata.get("title") == "Late Title"


@pytest.mark.asyncio
async def test_direct_persistence_phase2_rerun_refreshes_document_text_and_blocks(
    db_session: AsyncSession,
):
    """Phase 2 rerun output should replace stale SourceDocument render payloads."""
    from src.dao.postgresql.models import SourceDocument

    sd_id = str(uuid.uuid4())
    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=sd_id,
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
        phase_2_status=PhaseStatusDetail(status=PhaseStatus.COMPLETED),
        phase_2_output=Phase2Output(
            output_dir="/tmp/phase_2",
            original_json_path="/tmp/phase_2/original.json",
            translated_json_path="/tmp/phase_2/translated.json",
            source_language="zh",
            extraction_result_path="/tmp/phase_2/extraction_result.json",
            original_text="old original",
            translated_text="old translated",
            original_blocks=[{"text": "old original"}],
            translated_blocks=[{"text": "old translated"}],
        ),
    )
    persistence = DirectStatePersistence(db_session)
    await persistence.save(state)

    state.mode = PipelineMode.PHASE
    state.target_phase = 2
    state.pipeline_status = PipelineStatus.RUNNING
    state.phase_2_output = Phase2Output(
        output_dir="/tmp/phase_2",
        original_json_path="/tmp/phase_2/original.json",
        translated_json_path="/tmp/phase_2/translated.json",
        source_language="zh",
        extraction_result_path="/tmp/phase_2/extraction_result.json",
        original_text="new original",
        translated_text="new translated",
        original_blocks=[{"text": "new original"}],
        translated_blocks=[{"text": "new translated"}],
    )
    await persistence.save(state)

    sd = await db_session.get(SourceDocument, uuid.UUID(sd_id))
    assert sd is not None
    assert sd.original_text == "new original"
    assert sd.translated_text == "new translated"
    assert sd.original_blocks == [{"text": "new original"}]
    assert sd.translated_blocks == [{"text": "new translated"}]
