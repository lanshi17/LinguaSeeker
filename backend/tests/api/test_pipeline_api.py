"""Tests for pipeline API routes."""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.contracts import (
    PipelineGraphState,
    Phase1Output,
    Phase2Output,
    Phase3Output,
    PhaseErrorDetail,
    PhaseStatus,
    PipelineMode,
    SourceType,
    PipelineStatus,
    PhaseStatusDetail,
    SkipPhase3Reason,
)


@pytest.mark.asyncio
async def test_pipeline_run_injects_content_to_state(async_client):
    """POST /api/v1/pipeline/run injects base64 content into state via temp file."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.start = AsyncMock(return_value=MagicMock())
        mock_runner.is_running_for_source = AsyncMock(return_value=False)
        mock_runner.compute_initial_content_hash = AsyncMock(return_value=None)
        mock_runner.check_processing_cache = AsyncMock(return_value=None)
        mock_get_runner.return_value = mock_runner

        # Patch aiofiles.open to avoid writing real files to disk
        mock_file = AsyncMock()
        mock_file.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file.__aexit__ = AsyncMock(return_value=False)
        mock_file.write = AsyncMock()
        with patch("src.api.v1.pipeline.aiofiles.open", return_value=mock_file):
            await async_client.post(
                "/api/v1/pipeline/run",
                json={
                    "source_type": "local",
                    "filename": "test.pdf",
                    "content_base64": "dGVzdA==",  # "test"
                    "mode": "full",
                },
            )

        # Verify start() was called with state containing upload_file_path
        call_args = mock_runner.start.call_args
        initial_state = call_args[0][0]
        assert initial_state.upload_file_path is not None
        assert initial_state.upload_file_path.endswith("test.pdf")


@pytest.mark.asyncio
async def test_post_pipeline_run(async_client: AsyncClient):
    """POST /api/v1/pipeline/run accepts request and returns run ID."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.start = AsyncMock(return_value=MagicMock())
        mock_runner.is_running_for_source = AsyncMock(return_value=False)
        mock_runner.compute_initial_content_hash = AsyncMock(return_value=None)
        mock_runner.check_processing_cache = AsyncMock(return_value=None)
        mock_get_runner.return_value = mock_runner

        # Mock aiofiles.open to avoid writing real files
        mock_file = AsyncMock()
        mock_file.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file.__aexit__ = AsyncMock(return_value=False)
        mock_file.write = AsyncMock()
        with patch("src.api.v1.pipeline.aiofiles.open", return_value=mock_file):
            response = await async_client.post(
                "/api/v1/pipeline/run",
                json={
                    "source_type": "local",
                    "filename": "test.pdf",
                    "content_base64": "dGVzdA==",
                    "mode": "full",
                },
            )

        assert response.status_code == 202
        data = response.json()
        assert "processing_run_id" in data
        assert "status_url" in data
        assert data["status"] == "accepted"


@pytest.mark.asyncio
async def test_get_pipeline_status(async_client: AsyncClient):
    """GET /api/v1/pipeline/runs/{id}/status returns per-phase details."""
    mock_state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
        phase_1_status=PhaseStatusDetail(
            status=PhaseStatus.COMPLETED,
            started_at="2026-05-29T10:00:00",
            completed_at="2026-05-29T10:01:00",
            duration_seconds=60.0,
        ),
        phase_2_status=PhaseStatusDetail(
            status=PhaseStatus.RUNNING,
            started_at="2026-05-29T10:01:01",
        ),
    )

    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.get_last_state = AsyncMock(return_value=mock_state)
        mock_get_runner.return_value = mock_runner

        response = await async_client.get("/api/v1/pipeline/runs/run-123/status")

        assert response.status_code == 200
        data = response.json()
        assert data["processing_run_id"] == "run-123"
        assert data["pipeline_status"] == "running"
        assert data["phases"]["phase_1"]["status"] == "completed"
        assert data["phases"]["phase_1"]["duration_seconds"] == 60.0
        assert data["phases"]["phase_2"]["status"] == "running"
        assert data["current_phase"] == "phase_2"


@pytest.mark.asyncio
async def test_get_pipeline_status_shows_skip_reason(async_client: AsyncClient):
    """Status response includes skip_phase_3_reason when set."""
    mock_state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.COMPLETED,
        phase_1_status=PhaseStatusDetail(status=PhaseStatus.COMPLETED),
        phase_2_status=PhaseStatusDetail(status=PhaseStatus.COMPLETED),
        phase_3_status=PhaseStatusDetail(
            status=PhaseStatus.SKIPPED,
            summary={"reason": "not_relevant"},
        ),
        skip_phase_3_reason=SkipPhase3Reason.NOT_RELEVANT,
    )

    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.get_last_state = AsyncMock(return_value=mock_state)
        mock_get_runner.return_value = mock_runner

        response = await async_client.get("/api/v1/pipeline/runs/run-123/status")

        assert response.status_code == 200
        data = response.json()
        assert data["skip_phase_3_reason"] == "not_relevant"
        assert data["phases"]["phase_3"]["status"] == "skipped"
        assert data["phases"]["phase_3"]["summary"]["reason"] == "not_relevant"


@pytest.mark.asyncio
async def test_get_pipeline_status_not_found(async_client: AsyncClient):
    """GET /api/v1/pipeline/runs/{id}/status returns 404 for unknown run."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.get_last_state = AsyncMock(return_value=None)
        mock_get_runner.return_value = mock_runner

        response = await async_client.get("/api/v1/pipeline/runs/unknown-run/status")

        assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_pipeline_run_phase_mode_validation(async_client: AsyncClient):
    """POST /api/v1/pipeline/run with mode=phase requires target_phase."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "mode": "phase",
                # Missing target_phase
            },
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_pipeline_run_phase_rerun_resets_target_phase(async_client: AsyncClient):
    """Phase rerun resets target phase state before handing it to runner."""
    existing_state = PipelineGraphState(
        processing_run_id="7a77bbd1-ce2a-48d5-8d12-251512c6bdaf",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.FAILED,
        phase_1_status=PhaseStatusDetail(status=PhaseStatus.COMPLETED),
        phase_2_status=PhaseStatusDetail(status=PhaseStatus.COMPLETED),
        phase_3_status=PhaseStatusDetail(
            status=PhaseStatus.FAILED,
            started_at="2026-06-23T09:00:00",
            completed_at="2026-06-23T09:01:00",
            duration_seconds=60.0,
            error=PhaseErrorDetail(
                message="Invalid state transition",
                retryable=False,
                attempt=1,
                max_retries=1,
            ),
            summary={"matches": 0},
        ),
        phase_1_output=Phase1Output(
            pdf_path="/tmp/input.pdf",
            md_path="/tmp/output.md",
            metadata_path="/tmp/metadata.json",
            output_dir="/tmp/phase_1",
        ),
        phase_2_output=Phase2Output(
            output_dir="/tmp/phase_2",
            original_json_path="/tmp/original.json",
            translated_json_path="/tmp/translated.json",
            source_language="zh",
            extraction_result_path="/tmp/extraction_result.json",
        ),
        phase_3_output=Phase3Output(
            match_count=1,
            standardized_count=1,
            ambiguous_count=0,
            unmapped_count=0,
        ),
        error_message="Pipeline failed: Invalid state transition",
        error_phase=3,
        completed_at="2026-06-23T09:01:00",
    )

    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.get_last_state = AsyncMock(return_value=existing_state)
        mock_runner.start = AsyncMock(return_value=MagicMock())
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "mode": "phase",
                "target_phase": 3,
                "processing_run_id": existing_state.processing_run_id,
            },
        )

    assert response.status_code == 202
    initial_state = mock_runner.start.call_args[0][0]
    assert initial_state.pipeline_status == PipelineStatus.PENDING
    assert initial_state.phase_1_status.status == PhaseStatus.COMPLETED
    assert initial_state.phase_2_status.status == PhaseStatus.COMPLETED
    assert initial_state.phase_3_status == PhaseStatusDetail()
    assert initial_state.phase_1_output == existing_state.phase_1_output
    assert initial_state.phase_2_output == existing_state.phase_2_output
    assert initial_state.phase_3_output is None
    assert initial_state.error_message is None
    assert initial_state.error_phase is None
    assert initial_state.completed_at is None


@pytest.mark.asyncio
async def test_post_pipeline_run_local_requires_content(async_client: AsyncClient):
    """POST with source_type=local requires content_base64 (N1 fix)."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner

        # Missing content_base64 entirely
        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "mode": "full",
            },
        )
        assert response.status_code == 422

        # filename-only without content_base64 also rejected
        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "filename": "test.pdf",
                "mode": "full",
            },
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_pipeline_run_online_requires_query_or_identifiers(async_client: AsyncClient):
    """POST with source_type=online requires query or identifiers (N1 fix)."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "online",
                "mode": "full",
                # Missing query and identifiers
            },
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_pipeline_run_target_phase_range_validation(async_client: AsyncClient):
    """POST with target_phase outside 1-3 range is rejected (N2 fix)."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "content_base64": "dGVzdA==",
                "mode": "phase",
                "target_phase": 5,  # Invalid: out of range
            },
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_pipeline_run_duplicate_prevention(async_client: AsyncClient):
    """POST with same source_document_id while run is in-progress returns 409 (N3 fix)."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.is_running_for_source = AsyncMock(return_value=True)
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "filename": "test.pdf",
                "content_base64": "dGVzdA==",
                "mode": "full",
            },
        )

        assert response.status_code == 409



@pytest.mark.asyncio
async def test_post_pipeline_run_accepts_extraction_target(async_client: AsyncClient):
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.start = AsyncMock(return_value=MagicMock())
        mock_runner.is_running_for_source = AsyncMock(return_value=False)
        mock_runner.compute_initial_content_hash = AsyncMock(return_value=None)
        mock_runner.check_processing_cache = AsyncMock(return_value=None)
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "filename": "abca3.md",
                "pre_parsed_markdown": "ABCA3 and CFTR are discussed.",
                "target": {
                    "gene_symbol": "ABCA3",
                    "disease_name": "ABCA3 deficiency",
                    "variant_hgvs_p": "p.Q215*",
                    "clingen_entry_id": "CGGV:0001",
                },
                "mode": "full",
            },
        )

    assert response.status_code == 202
    state = mock_runner.start.call_args[0][0]
    assert state.extraction_target.gene_symbol == "ABCA3"
    assert "gene=ABCA3" in state.source_key


@pytest.mark.asyncio
async def test_post_pipeline_run_duplicate_source_key_race_returns_409(async_client: AsyncClient):
    """POST returns 409 when unique source_key constraint catches a race."""
    from sqlalchemy.exc import IntegrityError

    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        runner = MagicMock()
        runner.is_running_for_source = AsyncMock(return_value=False)
        runner.compute_initial_content_hash = AsyncMock(return_value=None)
        runner.check_processing_cache = AsyncMock(return_value=None)
        runner.start = AsyncMock(
            side_effect=IntegrityError("insert", {}, Exception("duplicate source_key"))
        )
        mock_get_runner.return_value = runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "mode": "full",
                "filename": "same.pdf",
                "content_base64": "JVBERi0xLjQK",
            },
        )

    assert response.status_code == 409
