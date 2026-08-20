import json

from src.core.evidence_extraction.infrastructure.document_parsing import (
    _block_text,
    _build_track_document_from_json,
)
from src.core.evidence_extraction.contracts import Track


def test_build_track_document_preserves_blocks(tmp_path):
    path = tmp_path / "original.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"doc_id": "doc-1", "source_language": "en"},
                "blocks": [
                    {
                        "type": "table",
                        "page_idx": 0,
                        "bbox": [1, 2, 3, 4],
                        "table_body": "Gene Variant\nBRCA1 c.5266dupC",
                        "table_caption": ["Table 1. Variants"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    doc = _build_track_document_from_json(path, Track.ORIGINAL)

    assert doc.blocks[0].type == "table"
    assert doc.blocks[0].bbox == [1, 2, 3, 4]
    assert "BRCA1 c.5266dupC" in doc.formatted_text


def test_build_track_document_accepts_historical_json_without_blocks(tmp_path):
    path = tmp_path / "original.json"
    path.write_text(
        json.dumps({"metadata": {"doc_id": "doc-1"}, "blocks": []}),
        encoding="utf-8",
    )

    doc = _build_track_document_from_json(path, Track.ORIGINAL)

    assert doc.blocks == []
    assert doc.page_spans[0].span_id == "original-p1"


def test_block_text_preserves_historical_body_only_behavior():
    block = {
        "type": "table",
        "page_idx": 0,
        "table_body": "Gene Variant\nBRCA1 c.5266dupC",
        "table_caption": ["Table 1. Variants"],
    }

    assert _block_text(block) == "Gene Variant\nBRCA1 c.5266dupC"


def test_block_text_unescapes_html_hgvs() -> None:
    block = {"type": "text", "text": "患儿携带c.538C&gt;T变异。"}

    assert _block_text(block) == "患儿携带c.538C>T变异。"


def test_build_track_document_unescapes_html_and_keeps_page_span_length(tmp_path) -> None:
    path = tmp_path / "original.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"doc_id": "rett-html", "source_language": "zh"},
                "blocks": [
                    {
                        "type": "text",
                        "page_idx": 0,
                        "bbox": [1, 2, 3, 4],
                        "text": "Sanger测序显示c.538C&gt;T（p.R180X）。",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    doc = _build_track_document_from_json(path, Track.ORIGINAL)

    assert "c.538C>T" in doc.formatted_text
    assert "&gt;" not in doc.formatted_text
    assert doc.blocks[0].text == "Sanger测序显示c.538C>T（p.R180X）。"
    assert doc.page_spans[0].end_offset == len(doc.formatted_text)

