from datetime import datetime, timezone

from src.application.dtos.document_dto import DocumentUploadDTO
from src.application.services.document_service import DocumentService
from src.domain.models import DocumentParsingArtifact, DocumentParsingResult


def test_process_pdf_document_returns_current_parsing_contract(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.7 synthetic")

    class FakeParsingAgent:
        def parse_documents(self, file_paths):
            assert file_paths == [str(pdf_path)]
            return DocumentParsingResult(
                markdown_content="# Parsed content",
                image_paths=[str(tmp_path / "page-1.jpg")],
                mineru_folder="mineru-output",
                parser_backend="mineru",
                parser_task_id="mineru-task-1",
                image_count=1,
                artifacts=DocumentParsingArtifact(
                    markdown_object_key="doc-1/parsing/parsed_markdown.md",
                    markdown_url="/api/v1/results/doc-1/parsing/parsed_markdown.md",
                    image_object_keys=["doc-1/parsing/images/page-1.jpg"],
                    image_urls=["/api/v1/results/doc-1/parsing/images/page-1.jpg"],
                ),
            )

    service = DocumentService(parser=FakeParsingAgent(), storage=None)
    result = service.process_pdf_document(
        DocumentUploadDTO(
            filename="paper.pdf",
            content=b"%PDF-1.7 synthetic",
            temp_file_path=str(pdf_path),
            upload_time=datetime.now(timezone.utc),
        )
    )

    assert result.parser_backend == "mineru"
    assert result.markdown_object_key == "doc-1/parsing/parsed_markdown.md"
    assert result.image_object_keys == ["doc-1/parsing/images/page-1.jpg"]
    assert result.image_urls == ["/api/v1/results/doc-1/parsing/images/page-1.jpg"]
