from app.models import (
    VLMExtractRequest,
    VLMExtractResponse,
    VLMPageContent,
    VLMDocumentMetadata,
)


def test_vlm_extract_request_text_only():
    req = VLMExtractRequest(
        model="opendatalab/MinerU2.5-Pro-2604-1.2B",
        messages=[{"role": "user", "content": "Extract this document."}],
    )
    assert req.model == "opendatalab/MinerU2.5-Pro-2604-1.2B"


def test_vlm_extract_request_with_image():
    req = VLMExtractRequest(
        model="opendatalab/MinerU2.5-Pro-2604-1.2B",
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": "Extract this document."},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR..."}},
            ]},
        ],
    )
    content = req.messages[0]["content"]
    assert isinstance(content, list)
    assert content[1]["type"] == "image_url"


def test_vlm_page_content():
    page = VLMPageContent(
        page_number=1,
        markdown="# Title\n\nContent here.",
        figures=[],
        tables=[],
    )
    assert page.page_number == 1


def test_vlm_extract_response():
    resp = VLMExtractResponse(
        id="vlm-abc123",
        model="opendatalab/MinerU2.5-Pro-2604-1.2B",
        metadata=VLMDocumentMetadata(total_pages=1),
        pages=[VLMPageContent(page_number=1, markdown="test")],
        full_markdown="test",
        choices=[],
    )
    assert resp.object == "vlm.extraction"
