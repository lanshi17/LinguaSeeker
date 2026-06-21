"""Tests for DocumentAcquisitionService."""

import tempfile
import os
from unittest.mock import AsyncMock, patch

import pytest

from src.core.ingest_and_digitize_data.document_acquisition.service import DocumentAcquisitionService
from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
    AcquisitionSource,
    DocumentAcquisitionRequest,
)


class TestDocumentAcquisitionService:
    """Tests for DocumentAcquisitionService.acquire method."""

    @pytest.mark.asyncio
    async def test_acquire_local_upload_success(self):
        """Test successful local upload via acquire method."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.LOCAL,
            filename="test.pdf",
            content=b"%PDF-1.4 test content",
            content_type="application/pdf",
        )
        result = await service.acquire(request)
        assert result.success is True
        assert result.source == AcquisitionSource.LOCAL
        assert result.stored_file is not None
        assert result.stored_file.original_filename == "test.pdf"
        assert os.path.exists(result.stored_file.file_path)
        os.unlink(result.stored_file.file_path)

    @pytest.mark.asyncio
    async def test_acquire_local_upload_validation_failure(self):
        """Test local upload validation failure."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.LOCAL,
            filename="test.exe",
            content=b"MZ executable",
        )
        result = await service.acquire(request)
        assert result.success is False
        assert result.source == AcquisitionSource.LOCAL
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_acquire_local_upload_missing_filename(self):
        """Test local upload missing filename."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.LOCAL,
            content=b"test content",
        )
        result = await service.acquire(request)
        assert result.success is False
        assert "filename is required" in result.error

    @pytest.mark.asyncio
    async def test_acquire_local_upload_missing_content(self):
        """Test local upload missing content."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.LOCAL,
            filename="test.pdf",
        )
        result = await service.acquire(request)
        assert result.success is False
        assert "content is required" in result.error

    @pytest.mark.asyncio
    async def test_acquire_online_search_routes_to_multilingual(self):
        """Free-text query with language='auto' routes to the multilingual workflow."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.ONLINE,
            action="search",
            query="test query",
        )
        mock_result = {
            "success": True,
            "items": [{"title": "Test Paper"}],
            "downloads": [],
            "warnings": [],
            "route": None,
        }
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.multilingual_acquisition_workflow",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_ml, patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.online_acquisition_workflow",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_single:
            result = await service.acquire(request)
            mock_ml.assert_awaited_once()
            mock_single.assert_not_awaited()
            assert result.source == AcquisitionSource.ONLINE
            assert result.success is True

    @pytest.mark.asyncio
    async def test_service_forwards_relevance_gate_and_literature_types(self):
        """relevance_gate + literature_types on the request reach the workflow payload."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.ONLINE,
            action="download",
            query="MECP2 Rett syndrome",
            relevance_gate=True,
            literature_types=["case_report", "sequencing"],
        )
        mock_result = {
            "success": True,
            "items": [],
            "downloads": [],
            "warnings": [],
            "route": None,
        }
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.multilingual_acquisition_workflow",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_ml:
            await service.acquire(request)
            mock_ml.assert_awaited_once()
            payload = mock_ml.await_args.args[0]
            assert payload["relevance_gate"] is True
            assert payload["literature_types"] == ["case_report", "sequencing"]

    @pytest.mark.asyncio
    async def test_service_forwards_relevance_gate_disabled(self):
        """relevance_gate=False is passed through; literature_types omitted when None."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.ONLINE,
            action="download",
            query="some topic",
            relevance_gate=False,
        )
        mock_result = {
            "success": True, "items": [], "downloads": [], "warnings": [], "route": None,
        }
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.multilingual_acquisition_workflow",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_ml:
            await service.acquire(request)
            payload = mock_ml.await_args.args[0]
            assert payload["relevance_gate"] is False
            assert "literature_types" not in payload

    @pytest.mark.asyncio
    async def test_acquire_online_search_with_explicit_language_uses_single(self):
        """Explicit language pins to the single-language workflow (no translation)."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.ONLINE,
            action="search",
            query="test query",
            language="en",
        )
        mock_result = {
            "success": True,
            "items": [],
            "downloads": [],
            "warnings": [],
            "route": None,
        }
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.multilingual_acquisition_workflow",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_ml, patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.online_acquisition_workflow",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_single:
            await service.acquire(request)
            mock_single.assert_awaited_once()
            mock_ml.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_acquire_online_identifier_only_uses_single(self):
        """Identifier-only download (no query) stays on the single-language workflow."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.ONLINE,
            action="download",
            identifiers=["10.1234/abcd"],
        )
        mock_result = {
            "success": True,
            "items": [],
            "downloads": [],
            "warnings": [],
            "route": None,
        }
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.multilingual_acquisition_workflow",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_ml, patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.online_acquisition_workflow",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_single:
            await service.acquire(request)
            mock_single.assert_awaited_once()
            mock_ml.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_acquire_online_missing_action(self):
        """Test online acquisition missing action."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.ONLINE,
            query="test query",
        )
        result = await service.acquire(request)
        assert result.success is False
        assert "action is required" in result.error

    @pytest.mark.asyncio
    async def test_acquire_online_search_missing_query(self):
        """Test online search missing query."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.ONLINE,
            action="search",
        )
        result = await service.acquire(request)
        assert result.success is False
        assert "query is required" in result.error

    @pytest.mark.asyncio
    async def test_acquire_invalid_source(self):
        """Test invalid source raises error."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(source="invalid")
        with pytest.raises(AttributeError):
            await service.acquire(request)

    @pytest.mark.asyncio
    async def test_acquire_local_upload_to_specific_dir(self):
        """Test local upload to specific directory."""
        service = DocumentAcquisitionService()
        with tempfile.TemporaryDirectory() as tmpdir:
            request = DocumentAcquisitionRequest(
                source=AcquisitionSource.LOCAL,
                filename="test.pdf",
                content=b"%PDF-1.4 test content",
                content_type="application/pdf",
                upload_dir=tmpdir,
            )
            result = await service.acquire(request)
            assert result.success is True
            assert result.stored_file.file_path.startswith(tmpdir)

    @pytest.mark.asyncio
    async def test_acquire_local_upload_deduplication(self):
        """Test file deduplication with upload_dir."""
        service = DocumentAcquisitionService()
        with tempfile.TemporaryDirectory() as tmpdir:
            request = DocumentAcquisitionRequest(
                source=AcquisitionSource.LOCAL,
                filename="test.pdf",
                content=b"%PDF-1.4 test content",
                content_type="application/pdf",
                upload_dir=tmpdir,
                deduplicate=True,
            )
            result1 = await service.acquire(request)
            assert result1.success is True
            assert result1.deduplicated is False

            result2 = await service.acquire(request)
            assert result2.success is True
            assert result2.deduplicated is True
            assert result2.stored_file.file_path == result1.stored_file.file_path

    @pytest.mark.asyncio
    async def test_acquire_local_upload_dedup_no_upload_dir(self):
        """Test dedup without upload_dir is skipped (no dedup possible)."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.LOCAL,
            filename="test.pdf",
            content=b"%PDF-1.4 test content",
            content_type="application/pdf",
            deduplicate=True,
        )
        result1 = await service.acquire(request)
        result2 = await service.acquire(request)
        assert result1.success is True
        assert result2.success is True
        assert result2.deduplicated is False
        # Cleanup
        os.unlink(result1.stored_file.file_path)
        os.unlink(result2.stored_file.file_path)

    @pytest.mark.asyncio
    async def test_acquire_elapsed_time(self):
        """Test elapsed time is recorded."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.LOCAL,
            filename="test.pdf",
            content=b"%PDF-1.4 test content",
            content_type="application/pdf",
        )
        result = await service.acquire(request)
        assert result.elapsed_time > 0
        os.unlink(result.stored_file.file_path)


    @pytest.mark.asyncio
    async def test_acquire_online_failure_surfaces_warnings_as_error(self):
        """Online workflow returns success=False with warnings but no ``error``
        field (OnlineAcquisitionResponse has none). The service must surface a
        concrete error so the Phase 1 adapter doesn't raise 'Acquisition
        failed: None'.
        """
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.ONLINE,
            action="search",
            query="MECP2 Rett syndrome",
        )
        mock_result = {
            "success": False,
            "items": [],
            "downloads": [],
            "warnings": [
                "FETCH_NO_RESULT: no candidates from any source",
                "firecrawl acquisition failed: timeout",
            ],
            "route": None,
        }
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.multilingual_acquisition_workflow",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await service.acquire(request)

        assert result.success is False
        # error must NOT be None — it carries the actual failure reason
        assert result.error is not None
        assert "FETCH_NO_RESULT" in result.error
        assert "firecrawl acquisition failed" in result.error

    @pytest.mark.asyncio
    async def test_acquire_online_failure_no_warnings_uses_default_error(self):
        """Online failure with no warnings still yields a non-None error."""
        service = DocumentAcquisitionService()
        request = DocumentAcquisitionRequest(
            source=AcquisitionSource.ONLINE,
            action="search",
            query="test query",
        )
        mock_result = {
            "success": False,
            "items": [],
            "downloads": [],
            "warnings": [],
            "route": None,
        }
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.multilingual_acquisition_workflow",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await service.acquire(request)

        assert result.success is False
        assert result.error is not None
        assert result.error  # non-empty string