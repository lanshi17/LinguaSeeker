"""Tests for /file_parse endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def test_file_parse_returns_result():
    """POST /file_parse with a PDF returns parsed results."""
    from main import app
    from app.api import file_parse
    from app.domain.doc_parse import DocParseResult

    mock_service = MagicMock()
    mock_service.is_available.return_value = True
    mock_service.backend = "vlm"
    mock_service.parse.return_value = DocParseResult(
        md_content="# Hello\n\nWorld",
        content_list=[{"type": "text", "text": "Hello", "page_idx": 0}],
        images={},
    )
    file_parse.bind(mock_service)

    client = TestClient(app)

    response = client.post(
        "/file_parse",
        files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"return_content_list": "true", "return_images": "true", "return_md": "true"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["backend"] == "vlm"
    assert "test.pdf" in data["results"]
    assert data["results"]["test.pdf"]["md_content"] == "# Hello\n\nWorld"


def test_file_parse_service_unavailable():
    """POST /file_parse returns 503 when MinerU is not installed."""
    from main import app
    from app.api import file_parse

    mock_service = MagicMock()
    mock_service.is_available.return_value = False
    mock_service.backend = "vlm"
    file_parse.bind(mock_service)

    client = TestClient(app)

    response = client.post(
        "/file_parse",
        files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 503


def test_file_parse_includes_images():
    """POST /file_parse with return_images=true includes base64 images."""
    from main import app
    from app.api import file_parse
    from app.domain.doc_parse import DocParseResult

    mock_service = MagicMock()
    mock_service.is_available.return_value = True
    mock_service.backend = "vlm"
    mock_service.parse.return_value = DocParseResult(
        md_content="content",
        content_list=[],
        images={"fig1.jpg": b"\xff\xd8\xff\xe0fake_jpeg"},
    )
    file_parse.bind(mock_service)

    client = TestClient(app)

    response = client.post(
        "/file_parse",
        files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"return_images": "true"},
    )

    assert response.status_code == 200
    images = response.json()["results"]["test.pdf"]["images"]
    assert "fig1.jpg" in images
    assert images["fig1.jpg"].startswith("data:image/jpeg;base64,")
