import json

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import _build_track_document_from_json
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import Track


def test_build_track_document_preserves_blocks(tmp_path):
    path = tmp_path / "original.json"
    path.write_text(
        json.dumps({
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
        }),
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
