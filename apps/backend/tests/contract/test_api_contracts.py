"""
API contract tests for upload endpoints.

These tests verify that the API endpoints conform to the OpenAPI specification
and handle various input scenarios correctly.
"""

import pytest
import json
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from src.presentation.controllers.pdf_parse_controller import PDFParseController
from src.config.app_config import AppConfig


@pytest.fixture
def test_client():
    """Create a test client for the PDF parse controller."""
    config = AppConfig()
    controller = PDFParseController(config)
    app = controller.get_router()
    return TestClient(app)


@pytest.fixture
def valid_pdf_upload_request():
    """Create a valid PDF upload request."""
    # Create a minimal base64 encoded PDF
    import base64
    minimal_pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
    pdf_base64 = base64.b64encode(minimal_pdf).decode()

    return {
        "file_content": pdf_base64,
        "filename": "test_document.pdf",
        "source": "file",
        "priority": 5
    }


def test_pdf_upload_endpoint_contract(test_client, valid_pdf_upload_request):
    """
    Test PDF upload endpoint contract compliance.

    Verifies:
    - Endpoint accepts valid PDF upload requests
    - Returns proper response structure
    - Handles required fields correctly
    """
    with patch('src.application.services.pdf_parse_service.PDFParseService.process_document_async',
               new_callable=AsyncMock) as mock_process:

        # Mock successful processing
        mock_process.return_value = None

        response = test_client.post(
            "/pdf/upload",
            json=valid_pdf_upload_request
        )

        # Verify response status
        assert response.status_code == 200

        # Verify response structure
        response_data = response.json()
        assert "task_id" in response_data
        assert "document_id" in response_data
        assert "status" in response_data
        assert "message" in response_data
        assert "websocket_url" in response_data

        # Verify task ID format
        assert isinstance(response_data["task_id"], str)
        assert len(response_data["task_id"]) > 0

        # Verify status is pending
        assert response_data["status"] == "pending"


def test_pdf_upload_missing_file_content(test_client):
    """
    Test PDF upload endpoint handles missing file content.
    """
    invalid_request = {
        "filename": "test.pdf",
        "source": "file"
        # Missing file_content
    }

    response = test_client.post("/pdf/upload", json=invalid_request)
    assert response.status_code == 422  # Validation error


def test_pdf_upload_invalid_base64(test_client):
    """
    Test PDF upload endpoint handles invalid base64 content.
    """
    invalid_request = {
        "file_content": "invalid_base64!!!",
        "filename": "test.pdf",
        "source": "file"
    }

    response = test_client.post("/pdf/upload", json=invalid_request)
    assert response.status_code == 400  # Bad request


def test_pdf_upload_large_file(test_client):
    """
    Test PDF upload endpoint handles files larger than limit.
    """
    # Create large base64 content (exceeds typical limits)
    large_content = "A" * 10000000  # 10MB
    import base64
    large_base64 = base64.b64encode(large_content.encode()).decode()

    large_request = {
        "file_content": large_base64,
        "filename": "large_document.pdf",
        "source": "file"
    }

    response = test_client.post("/pdf/upload", json=large_request)
    assert response.status_code == 400  # File too large


def test_pmid_fetch_endpoint_contract(test_client):
    """
    Test PMID fetch endpoint contract compliance.
    """
    with patch('src.application.services.pdf_parse_service.PDFParseService.process_document_async',
               new_callable=AsyncMock) as mock_process:

        mock_process.return_value = None

        response = test_client.post(
            "/pdf/fetch-by-pmid",
            params={"pmid": "12345678", "priority": 5}
        )

        assert response.status_code == 200
        response_data = response.json()
        assert "task_id" in response_data
        assert response_data["status"] == "pending"


def test_pmid_fetch_invalid_format(test_client):
    """
    Test PMID fetch endpoint handles invalid PMID formats.
    """
    response = test_client.post(
        "/pdf/fetch-by-pmid",
        params={"pmid": "invalid_pmid", "priority": 5}
    )
    assert response.status_code == 400  # Invalid PMID format


def test_doi_fetch_endpoint_contract(test_client):
    """
    Test DOI fetch endpoint contract compliance.
    """
    with patch('src.application.services.pdf_parse_service.PDFParseService.process_document_async',
               new_callable=AsyncMock) as mock_process:

        mock_process.return_value = None

        response = test_client.post(
            "/pdf/fetch-by-doi",
            params={"doi": "10.1038/s41586-023-06221-2", "priority": 5}
        )

        assert response.status_code == 200
        response_data = response.json()
        assert "task_id" in response_data
        assert response_data["status"] == "pending"


def test_doi_fetch_invalid_format(test_client):
    """
    Test DOI fetch endpoint handles invalid DOI formats.
    """
    response = test_client.post(
        "/pdf/fetch-by-doi",
        params={"doi": "invalid_doi", "priority": 5}
    )
    assert response.status_code == 400  # Invalid DOI format


def test_task_status_endpoint_contract(test_client):
    """
    Test task status endpoint contract compliance.
    """
    with patch('src.application.services.pdf_parse_service.PDFParseService.get_task_status',
               new_callable=AsyncMock) as mock_get_status:

        # Mock task status response
        mock_get_status.return_value = {
            "task_id": "test_task_123",
            "document_id": "test_doc_456",
            "status": "processing",
            "progress_percentage": 50,
            "current_stage": "Evidence Extraction",
            "created_at": "2026-01-31T10:00:00Z",
            "updated_at": "2026-01-31T10:02:30Z",
            "completed_at": None,
            "error_message": None,
            "evidence_items": [],
            "processing_time_seconds": None,
            "file_size_bytes": 1024000
        }

        response = test_client.get("/tasks/test_task_123")

        assert response.status_code == 200
        response_data = response.json()

        # Verify all required fields are present
        required_fields = [
            "task_id", "document_id", "status", "progress_percentage",
            "current_stage", "created_at", "updated_at"
        ]
        for field in required_fields:
            assert field in response_data

        # Verify data types
        assert isinstance(response_data["progress_percentage"], int)
        assert isinstance(response_data["evidence_items"], list)


def test_task_status_not_found(test_client):
    """
    Test task status endpoint handles non-existent tasks.
    """
    with patch('src.application.services.pdf_parse_service.PDFParseService.get_task_status',
               new_callable=AsyncMock) as mock_get_status:

        mock_get_status.return_value = None

        response = test_client.get("/tasks/non_existent_task")
        assert response.status_code == 404


def test_task_retry_endpoint_contract(test_client):
    """
    Test task retry endpoint contract compliance.
    """
    with patch('src.application.services.pdf_parse_service.PDFParseService.retry_task',
               new_callable=AsyncMock) as mock_retry:

        mock_retry.return_value = True

        response = test_client.post("/tasks/test_task_123/retry")

        assert response.status_code == 200
        response_data = response.json()
        assert "message" in response_data
        assert "task_id" in response_data


def test_task_cancel_endpoint_contract(test_client):
    """
    Test task cancel endpoint contract compliance.
    """
    with patch('src.application.services.pdf_parse_service.PDFParseService.cancel_task',
               new_callable=AsyncMock) as mock_cancel:

        mock_cancel.return_value = True

        response = test_client.delete("/tasks/test_task_123")

        assert response.status_code == 200
        response_data = response.json()
        assert "message" in response_data


def test_api_openapi_schema_compliance():
    """
    Test that the API endpoints comply with OpenAPI schema.
    """
    # Get the OpenAPI schema
    client = test_client()
    response = client.get("/openapi.json")

    if response.status_code == 200:
        schema = response.json()

        # Verify required endpoints exist in schema
        paths = schema.get("paths", {})
        required_paths = [
            "/pdf/upload",
            "/pdf/fetch-by-pmid",
            "/pdf/fetch-by-doi",
            "/tasks/{task_id}",
            "/tasks/{task_id}/retry",
            "/tasks/{task_id}"
        ]

        for path in required_paths:
            if path == "/tasks/{task_id}":
                # DELETE and GET should both exist
                assert path in paths
                assert "get" in paths[path]
                assert "delete" in paths[path]
            elif path == "/tasks/{task_id}/retry":
                assert path in paths
                assert "post" in paths[path]
            else:
                assert path in paths
                assert "post" in paths[path]
    else:
        pytest.skip("OpenAPI schema not available")


def test_request_validation_error_handling():
    """
    Test that validation errors return proper error responses.
    """
    client = test_client()

    # Test with completely invalid JSON
    response = client.post("/pdf/upload", content="{invalid json}")
    assert response.status_code == 422  # FastAPI validation error

    # Test with wrong data types
    invalid_request = {
        "file_content": 123,  # Should be string
        "filename": "test.pdf",
        "source": "file"
    }
    response = client.post("/pdf/upload", json=invalid_request)
    assert response.status_code == 422


def test_response_content_type():
    """
    Test that API responses have correct content type.
    """
    client = test_client()

    with patch('src.application.services.pdf_parse_service.PDFParseService.process_document_async',
               new_callable=AsyncMock) as mock_process:

        mock_process.return_value = None

        response = client.post("/pdf/upload", json={
            "file_content": "JVBERi0xLjQKJcfs...",
            "filename": "test.pdf",
            "source": "file"
        })

        assert response.headers["content-type"] == "application/json"


if __name__ == "__main__":
    # Allow running tests individually for debugging
    pytest.main([__file__, "-v"])