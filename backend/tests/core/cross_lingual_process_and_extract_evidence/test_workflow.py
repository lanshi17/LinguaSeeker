import pytest
from unittest.mock import MagicMock

from src.core.cross_lingual_process_and_extract_evidence.config_context import TranslationConfigContext
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.translation.api_key = "test-key"
    cfg.translation.base_url = "http://localhost:8001/v1"
    cfg.translation.model = "test-model"
    cfg.translation.temperature = 0.0
    return cfg


@pytest.fixture
def sample_pages():
    return [
        {"page_number": 1, "markdown": "The patient carries a novel BRCA1 variant."},
    ]


def test_service_init(mock_config):
    service = TranslationService(cfg=mock_config)
    assert service._ctx.model == "test-model"


def test_service_has_formatter(mock_config):
    service = TranslationService(cfg=mock_config)
    assert service._formatter is not None


def test_service_has_translator(mock_config):
    service = TranslationService(cfg=mock_config)
    assert service._translator is not None


def test_service_has_router(mock_config):
    service = TranslationService(cfg=mock_config)
    assert service._router is not None


# ── TranslationConfigContext tests ────────────────────────────────────


def test_config_context_from_config(mock_config):
    ctx = TranslationConfigContext.from_config(mock_config)
    assert ctx.model == "test-model"
    assert ctx.api_key == "test-key"
    assert ctx.base_url == "http://localhost:8001/v1"
    assert ctx.temperature == 0.0


def test_config_context_from_config_default_temperature():
    cfg = MagicMock()
    cfg.translation.api_key = "key"
    cfg.translation.base_url = "http://localhost"
    cfg.translation.model = "model"
    del cfg.translation.temperature  # getattr will return default
    ctx = TranslationConfigContext.from_config(cfg)
    assert ctx.temperature == 0.0


# ── TranslationService.save() tests ───────────────────────────────────


def test_translation_service_save(tmp_path):
    """TranslationService.save() persists result and returns output."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import TranslationResult

    cfg = MagicMock()
    cfg.translation.model = "test-model"
    cfg.translation.api_key = "test-key"
    cfg.translation.base_url = "http://localhost:8001"

    service = TranslationService(cfg=cfg)

    result = TranslationResult(
        formatted_original="原始文本",
        translated_english="Original text",
        source_language="zh",
        terminology_map={"基因": "gene"},
        translation_warnings=[],
        sentences=[],
        segments=[],
    )

    output = service.save(
        result,
        output_dir=str(tmp_path),
        doc_id="test_doc",
    )

    assert output.formatted_original == "原始文本"
    assert output.translated_english == "Original text"
    assert output.output_dir.startswith(str(tmp_path))
    assert output.original_json_path.endswith("original.json")


def test_translation_service_save_with_images(tmp_path):
    """TranslationService.save() forwards image_paths to persistence."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import TranslationResult

    # Create fake source images
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    img = src_dir / "fig1.png"
    img.write_bytes(b"fake_png")

    cfg = MagicMock()
    cfg.translation.model = "test-model"
    cfg.translation.api_key = "test-key"
    cfg.translation.base_url = "http://localhost:8001"

    service = TranslationService(cfg=cfg)

    result = TranslationResult(
        formatted_original="原始文本",
        translated_english="Original text",
        source_language="zh",
        terminology_map={"基因": "gene"},
        translation_warnings=[],
        sentences=[],
        segments=[],
    )

    output = service.save(
        result,
        output_dir=str(tmp_path / "out"),
        doc_id="test_doc",
        image_paths=[str(img)],
    )

    assert len(output.image_paths) == 1
    assert output.image_paths[0].endswith("fig1.png")
