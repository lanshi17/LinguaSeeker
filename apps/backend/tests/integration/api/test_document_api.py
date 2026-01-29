"""
Integration tests for document API workflow.

Tests the complete flow:
1. UploadController receives PDF upload -> creates DocumentUploadDTO
2. DocumentService processes the DTO -> calls PDFParser
3. PDFParser submits file -> MinerU adapter processes it
4. MinIO stores the extracted files
"""

import pytest
import os
import io
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi import UploadFile
import tempfile
import uuid

# Import application components
from presentation.upload_controller import UploadController
from application.services.document_service import DocumentService
from application.dtos.document_dto import DocumentUploadDTO
from domain.impl.pdf_parser import PDFParser
from infrastructure.adapters.mineru import MinerUImpl
from infrastructure.store.minio_store import MinIOStore
from config.app_config import AppConfig
from config.database_config import DatabaseConfig


@pytest.fixture
def test_pdf_file():
    """Fixture providing a test PDF file"""
    test_pdf_path = Path(__file__).parent.parent.parent / "fixtures" / "test_zh.pdf"
    if not test_pdf_path.exists():
        pytest.skip(f"Test PDF file not found: {test_pdf_path}")
    return test_pdf_path


@pytest.fixture
def mock_app_config():
    """Mock AppConfig for testing"""
    config = Mock(spec=AppConfig)
    config.max_upload_size = 50 * 1024 * 1024  # 50 MB
    return config


@pytest.fixture
def mock_db_config():
    """Mock DatabaseConfig for testing"""
    config = Mock(spec=DatabaseConfig)
    mock_minio_config = Mock()
    mock_minio_config.endpoint = "localhost:9000"
    mock_minio_config.access_key = "minioadmin"
    mock_minio_config.secret_key = "minioadmin"
    mock_minio_config.secure = False
    mock_minio_config.bucket_name = "test-bucket"
    config.minio = mock_minio_config
    return config


@pytest.fixture
def mock_mineru_adapter():
    """Mock MinerU adapter for testing"""
    adapter = Mock(spec=MinerUImpl)

    # Mock the apply_upload_urls response
    adapter.apply_upload_urls.return_value = {
        "files": [{
            "file_id": "test-file-id-12345",
            "upload_url": "https://mock-upload-url.com/upload"
        }]
    }

    # Mock upload_to_urls to succeed
    adapter.upload_to_urls.return_value = None

    # Mock get_processing_status to return completed status
    adapter.get_processing_status.return_value = {
        "extract_result": {
            "state": "completed",
            "extract_progress": {
                "extracted_pages": 10,
                "total_pages": 10
            }
        }
    }

    # Mock retrieve_results to return download URL
    adapter.retrieve_results.return_value = {
        "extract_result": {
            "state": "completed",
            "file_id": "test-file-id-12345",
            "file_name": "test_zh.pdf",
            "full_zip_url": "https://mock-download-url.com/result.zip"
        }
    }

    return adapter


@pytest.fixture
def mock_minio_store():
    """Mock MinIO store for testing"""
    store = Mock(spec=MinIOStore)

    # Mock download_and_extract_zip to return list of uploaded files
    store.download_and_extract_zip.return_value = [
        "documents/test_zh/test-doc-id/content.html",
        "documents/test_zh/test-doc-id/images/page_1.png",
        "documents/test_zh/test-doc-id/images/page_2.png",
        "documents/test_zh/test-doc-id/metadata.json"
    ]

    return store


class TestDocumentAPIIntegration:
    """Integration tests for document API workflow"""

    @pytest.mark.asyncio
    async def test_upload_pdf_success_flow(
        self,
        test_pdf_file,
        mock_app_config,
        mock_mineru_adapter,
        mock_minio_store
    ):
        """Test complete PDF upload workflow with mocked external dependencies"""

        # Step 1: Prepare upload file
        with open(test_pdf_file, "rb") as f:
            file_content = f.read()

        upload_file = UploadFile(
            filename="test_zh.pdf",
            file=io.BytesIO(file_content)
        )

        # Step 2: Create UploadController with mocked dependencies
        with patch('presentation.upload_controller.DocumentService') as MockDocumentService:
            # Setup mock document service
            mock_doc_service = MockDocumentService.return_value
            mock_doc_service.process_pdf_document.return_value = {
                "document_id": "test-uuid-12345",
                "file_name": "test_zh.pdf",
                "minio_prefix": "documents/test_zh/test-uuid-12345",
                "minio_files": [
                    "documents/test_zh/test-uuid-12345/content.html",
                    "documents/test_zh/test-uuid-12345/images/page_1.png"
                ],
                "file_count": 2,
                "processed_at": "2024-01-01T00:00:00Z",
                "mineru_file_id": "test-file-id-12345"
            }

            controller = UploadController(config=mock_app_config)

            # Step 3: Call upload endpoint
            result = await controller._upload_pdf(file=upload_file)

            # Step 4: Verify result
            assert result["message"] == "File uploaded and processed successfully"
            assert result["filename"] == "test_zh.pdf"
            assert result["document_id"] == "test-uuid-12345"
            assert result["minio_prefix"] == "documents/test_zh/test-uuid-12345"
            assert result["file_count"] == 2
            assert len(result["minio_files"]) == 2

            # Verify DocumentService was called with DocumentUploadDTO
            mock_doc_service.process_pdf_document.assert_called_once()
            call_args = mock_doc_service.process_pdf_document.call_args[0][0]
            assert isinstance(call_args, DocumentUploadDTO)
            assert call_args.filename == "test_zh.pdf"
            assert call_args.size == len(file_content)


    @pytest.mark.asyncio
    async def test_upload_pdf_invalid_file_type(self, mock_app_config):
        """Test upload with non-PDF file"""

        upload_file = UploadFile(
            filename="test.txt",
            file=io.BytesIO(b"Not a PDF file")
        )

        controller = UploadController(config=mock_app_config)

        with pytest.raises(Exception) as exc_info:
            await controller._upload_pdf(file=upload_file)

        assert "Unsupported file type" in str(exc_info.value)


    @pytest.mark.asyncio
    async def test_upload_pdf_file_too_large(self, mock_app_config):
        """Test upload with file exceeding size limit"""

        # Create a file larger than max_upload_size
        large_content = b"x" * (mock_app_config.max_upload_size + 1)

        upload_file = UploadFile(
            filename="large_file.pdf",
            file=io.BytesIO(large_content)
        )

        controller = UploadController(config=mock_app_config)

        with pytest.raises(Exception) as exc_info:
            await controller._upload_pdf(file=upload_file)

        assert "File size exceeds the maximum limit" in str(exc_info.value)


    def test_document_service_process_pdf_document(
        self,
        test_pdf_file,
        mock_mineru_adapter,
        mock_minio_store,
        mock_db_config
    ):
        """Test DocumentService.process_pdf_document with mocked dependencies"""

        # Create DocumentUploadDTO
        with open(test_pdf_file, "rb") as f:
            file_content = f.read()

        document = DocumentUploadDTO(
            filename="test_zh.pdf",
            content=file_content,
            size=len(file_content),
            content_type="application/pdf"
        )

        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        document.temp_file_path = temp_file_path

        try:
            # Create DocumentService with mocked dependencies
            with patch('application.services.document_service.MinerUImpl', return_value=mock_mineru_adapter), \
                 patch('application.services.document_service.MinIOStore', return_value=mock_minio_store):

                service = DocumentService(db_config=mock_db_config)
                service.mineru_adapter = mock_mineru_adapter
                service.minio_store = mock_minio_store

                # Process document
                result = service.process_pdf_document(document)

                # Verify result structure
                assert "document_id" in result
                assert "file_name" in result
                assert result["file_name"] == "test_zh.pdf"
                assert "minio_prefix" in result
                assert "minio_files" in result
                assert "file_count" in result
                assert result["file_count"] > 0
                assert "processed_at" in result

        finally:
            # Cleanup temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)


    def test_pdf_parser_without_language_configuration(
        self,
        test_pdf_file,
        mock_mineru_adapter
    ):
        """Test PDFParser.parse_with_mineru without language pre-processing"""

        parser = PDFParser(mineru_adapter=mock_mineru_adapter)

        result = parser.parse_with_mineru(
            file_path=str(test_pdf_file),
            document_id="test-doc-id-123"
        )

        # Verify result
        assert result["file_id"] == "test-file-id-12345"
        assert result["full_zip_url"] == "https://mock-download-url.com/result.zip"
        assert result["state"] == "completed"
        assert result["document_id"] == "test-doc-id-123"
        assert "detected_languages" not in result

        # Verify MinerU adapter was called without language config
        mock_mineru_adapter.apply_upload_urls.assert_called_once_with([str(test_pdf_file)])


    def test_minio_store_download_and_extract_zip(self, mock_db_config):
        """Test MinIO store download and extract ZIP functionality"""

        mock_zip_url = "https://mock-download-url.com/result.zip"
        mock_prefix = "documents/test/test-uuid"

        with patch('infrastructure.store.minio_store.Minio') as MockMinio, \
             patch('infrastructure.store.minio_store.requests') as mock_requests, \
             patch('infrastructure.store.minio_store.zipfile.ZipFile') as MockZipFile:

            # Setup mocks
            mock_client = MockMinio.return_value
            mock_client.bucket_exists.return_value = True

            mock_response = Mock()
            mock_response.iter_content.return_value = [b"mock zip content"]
            mock_response.raise_for_status.return_value = None
            mock_requests.get.return_value = mock_response

            mock_zip = MockZipFile.return_value.__enter__.return_value
            mock_zip.extractall.return_value = None

            store = MinIOStore(db_config=mock_db_config)

            # Mock the extract_and_upload_zip to return expected files
            with patch.object(store, 'extract_and_upload_zip') as mock_extract:
                mock_extract.return_value = [
                    f"{mock_prefix}/content.html",
                    f"{mock_prefix}/images/page_1.png"
                ]

                result = store.download_and_extract_zip(mock_zip_url, mock_prefix)

                # Verify result
                assert len(result) == 2
                assert f"{mock_prefix}/content.html" in result
                assert f"{mock_prefix}/images/page_1.png" in result


    @pytest.mark.asyncio
    async def test_end_to_end_integration_with_mocks(
        self,
        test_pdf_file,
        mock_app_config,
        mock_db_config,
        mock_mineru_adapter,
        mock_minio_store
    ):
        """
        End-to-end integration test simulating the complete workflow:
        Upload -> DTO creation -> Service processing -> Parser -> MinerU -> MinIO
        """

        # Step 1: Read test PDF
        with open(test_pdf_file, "rb") as f:
            file_content = f.read()

        # Step 2: Create upload file
        upload_file = UploadFile(
            filename="test_zh.pdf",
            file=io.BytesIO(file_content)
        )

        # Step 3: Setup complete mock chain
        with patch('presentation.upload_controller.DocumentService') as MockDocService, \
             patch.object(uuid, 'uuid4', return_value=uuid.UUID('12345678-1234-5678-1234-567812345678')):

            # Configure document service mock
            mock_service_instance = MockDocService.return_value

            def mock_process_pdf_document(document_dto):
                """Simulate the complete processing flow"""
                assert isinstance(document_dto, DocumentUploadDTO)
                assert document_dto.filename == "test_zh.pdf"
                assert document_dto.temp_file_path is not None

                document_id = "12345678-1234-5678-1234-567812345678"
                minio_prefix = f"documents/test_zh/{document_id}"

                return {
                    "document_id": document_id,
                    "file_name": document_dto.filename,
                    "minio_prefix": minio_prefix,
                    "minio_files": [
                        f"{minio_prefix}/content.html",
                        f"{minio_prefix}/images/page_1.png",
                        f"{minio_prefix}/images/page_2.png",
                        f"{minio_prefix}/metadata.json"
                    ],
                    "file_count": 4,
                    "processed_at": "2024-01-01T00:00:00+00:00",
                    "mineru_file_id": "test-file-id-12345"
                }

            mock_service_instance.process_pdf_document.side_effect = mock_process_pdf_document

            # Step 4: Execute upload
            controller = UploadController(config=mock_app_config)
            result = await controller._upload_pdf(file=upload_file)

            # Step 5: Verify end-to-end result
            assert result["message"] == "File uploaded and processed successfully"
            assert result["filename"] == "test_zh.pdf"
            assert result["size"] == len(file_content)
            assert result["document_id"] == "12345678-1234-5678-1234-567812345678"
            assert "documents/test_zh/12345678-1234-5678-1234-567812345678" in result["minio_prefix"]
            assert result["file_count"] == 4
            assert len(result["minio_files"]) == 4

            # Verify the flow was executed
            mock_service_instance.process_pdf_document.assert_called_once()

            # Verify DocumentUploadDTO was created correctly
            call_args = mock_service_instance.process_pdf_document.call_args[0][0]
            assert call_args.filename == "test_zh.pdf"
            assert call_args.content_type == "application/pdf"
            assert call_args.size == len(file_content)


class TestDocumentAPIErrorHandling:
    """Test error handling in document API workflow"""

    @pytest.mark.asyncio
    async def test_mineru_processing_failure(self, test_pdf_file, mock_app_config):
        """Test handling of MinerU processing failure"""

        with open(test_pdf_file, "rb") as f:
            file_content = f.read()

        upload_file = UploadFile(
            filename="test_zh.pdf",
            file=io.BytesIO(file_content)
        )

        with patch('presentation.upload_controller.DocumentService') as MockDocService:
            mock_service = MockDocService.return_value
            mock_service.process_pdf_document.side_effect = Exception("MinerU processing failed")

            controller = UploadController(config=mock_app_config)

            with pytest.raises(Exception) as exc_info:
                await controller._upload_pdf(file=upload_file)

            assert "Internal Server Error" in str(exc_info.value)


    @pytest.mark.asyncio
    async def test_minio_storage_failure(self, test_pdf_file, mock_app_config):
        """Test handling of MinIO storage failure"""

        with open(test_pdf_file, "rb") as f:
            file_content = f.read()

        upload_file = UploadFile(
            filename="test_zh.pdf",
            file=io.BytesIO(file_content)
        )

        with patch('presentation.upload_controller.DocumentService') as MockDocService:
            mock_service = MockDocService.return_value
            mock_service.process_pdf_document.side_effect = Exception("MinIO upload failed")

            controller = UploadController(config=mock_app_config)

            with pytest.raises(Exception) as exc_info:
                await controller._upload_pdf(file=upload_file)

            assert "Internal Server Error" in str(exc_info.value)


# Run tests with: pytest tests/integration/api/test_document_api.py -v
