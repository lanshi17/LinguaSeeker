from app.models import (
    VLMContentPart,
    VLMExtractRequest,
    VLMExtractResponse,
    VLMImageUrl,
    VLMMessage,
    VLMPageContent,
    VLMDocumentMetadata,
)


def test_vlm_extract_request_text_only():
    req = VLMExtractRequest(
        model="opendatalab/MinerU2.5-Pro-2604-1.2B",
        messages=[VLMMessage(role="user", content="Extract this document.")],
    )
    assert req.model == "opendatalab/MinerU2.5-Pro-2604-1.2B"
    assert isinstance(req.messages[0].content, str)


def test_vlm_extract_request_with_image():
    req = VLMExtractRequest(
        model="opendatalab/MinerU2.5-Pro-2604-1.2B",
        messages=[
            VLMMessage(role="user", content=[
                VLMContentPart(type="text", text="Extract this document."),
                VLMContentPart(type="image_url", image_url=VLMImageUrl(url="data:image/png;base64,iVBOR...")),
            ]),
        ],
    )
    content = req.messages[0].content
    assert isinstance(content, list)
    assert content[1].type == "image_url"
    assert content[1].image_url is not None
    assert content[1].image_url.url.startswith("data:")


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
