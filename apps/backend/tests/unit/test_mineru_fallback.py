from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.mineru import component as mineru_component
from src.utils import exceptions as exc


def test_run_paddleocr_fallback_raises_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mineru_component, "_paddleocr_available", False)

    with pytest.raises(exc.ParsingException, match="OCR_FAILED"):
        mineru_component.run_paddleocr_fallback(["paper.pdf"])


def test_run_paddleocr_fallback_returns_parsed_folder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakePaddleOCR:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def ocr(self, _file_path: str, cls: bool = True):
            assert cls is True
            return [
                [
                    [[[0, 0], [1, 0], [1, 1], [0, 1]], ("Line one", 0.98)],
                    [[[0, 0], [1, 0], [1, 1], [0, 1]], ("Line two", 0.95)],
                ]
            ]

    input_file = tmp_path / "paper.pdf"
    input_file.write_bytes(b"%PDF-1.7 test")

    monkeypatch.setattr(mineru_component, "_paddleocr_available", True)
    monkeypatch.setattr(mineru_component, "_PaddleOCR", FakePaddleOCR)
    monkeypatch.setattr(mineru_component.cfg, "mineru_download_dir", str(tmp_path / "downloads"))

    response = mineru_component.run_paddleocr_fallback([str(input_file)])

    assert response.status == "done"
    assert response.folder_path is not None
    output_dir = Path(response.folder_path)
    assert output_dir.exists()

    markdown_path = output_dir / "full.md"
    assert markdown_path.exists()
    markdown_content = markdown_path.read_text(encoding="utf-8")
    assert "Line one" in markdown_content
    assert "Line two" in markdown_content


def test_run_paddleocr_fallback_raises_when_input_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePaddleOCR:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def ocr(self, _file_path: str, cls: bool = True):
            assert cls is True
            return []

    monkeypatch.setattr(mineru_component, "_paddleocr_available", True)
    monkeypatch.setattr(mineru_component, "_PaddleOCR", FakePaddleOCR)

    with pytest.raises(exc.ParsingException, match="OCR_FAILED"):
        mineru_component.run_paddleocr_fallback(["/tmp/does-not-exist.pdf"])


def test_run_paddleocr_fallback_deduplicates_top_level_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakePaddleOCR:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def ocr(self, _file_path: str, cls: bool = True):
            assert cls is True
            return [{"text": "Single line"}]

    input_file = tmp_path / "paper.pdf"
    input_file.write_bytes(b"%PDF-1.7 test")

    monkeypatch.setattr(mineru_component, "_paddleocr_available", True)
    monkeypatch.setattr(mineru_component, "_PaddleOCR", FakePaddleOCR)
    monkeypatch.setattr(mineru_component.cfg, "mineru_download_dir", str(tmp_path / "downloads"))

    response = mineru_component.run_paddleocr_fallback([str(input_file)])
    assert response.folder_path is not None
    full_markdown = (Path(response.folder_path) / "full.md").read_text(encoding="utf-8")
    assert full_markdown.count("Single line") == 1
