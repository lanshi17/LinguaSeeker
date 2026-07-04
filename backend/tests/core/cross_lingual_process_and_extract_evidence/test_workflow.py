import pytest
from unittest.mock import MagicMock

from src.core.cross_lingual_process_and_extract_evidence.config_context import TranslationConfigContext
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.llm.api_key = "test-key"
    cfg.llm.all_api_keys = ["test-key"]
    cfg.llm.base_url = "http://localhost:8001/v1"
    cfg.llm.model = "test-model"
    cfg.llm.temperature = 0.0
    cfg.llm.max_tokens = 1024
    cfg.llm.timeout = 1
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
    mock_config.translation.model = "translation-model"
    mock_config.translation.api_key = "translation-key"
    mock_config.translation.all_api_keys = ["translation-key"]
    mock_config.translation.base_url = "https://remote.example/v1"
    mock_config.translation.local_base_url = "http://localhost:59062/api"
    mock_config.translation.local_target_lang = "en"
    mock_config.translation.local_timeout = 30
    mock_config.translation.remote_base_url = ""
    mock_config.translation.remote_model = ""
    mock_config.translation.remote_api_key = ""
    mock_config.translation.remote_all_api_keys = []
    mock_config.translation.temperature = 0.0
    mock_config.translation.max_tokens = 1024
    mock_config.translation.timeout = 1

    ctx = TranslationConfigContext.from_config(mock_config)
    assert ctx.model == "translation-model"
    assert ctx.api_key == "translation-key"
    assert ctx.base_url == "https://remote.example/v1"
    assert ctx.local_base_url == "http://localhost:59062/api"
    assert ctx.temperature == 0.0


def test_config_context_prefers_remote_override_for_fallback():
    cfg = MagicMock()
    cfg.translation.model = "local-default-model"
    cfg.translation.api_key = "default-key"
    cfg.translation.all_api_keys = ["default-key"]
    cfg.translation.base_url = "https://default.example/v1"
    cfg.translation.local_base_url = "http://localhost:59062/api"
    cfg.translation.local_target_lang = "en"
    cfg.translation.local_timeout = 30
    cfg.translation.remote_base_url = "https://remote.example/v1"
    cfg.translation.remote_model = "remote-model"
    cfg.translation.remote_api_key = "remote-key"
    cfg.translation.remote_all_api_keys = ["remote-key"]
    cfg.translation.temperature = 0.0
    cfg.translation.max_tokens = 1024
    cfg.translation.timeout = 1

    ctx = TranslationConfigContext.from_config(cfg)

    assert ctx.model == "remote-model"
    assert ctx.api_key == "remote-key"
    assert ctx.api_keys == ["remote-key"]
    assert ctx.base_url == "https://remote.example/v1"
    assert ctx.local_base_url == "http://localhost:59062/api"


def test_config_context_from_config_default_temperature():
    cfg = MagicMock()
    cfg.llm.api_key = "key"
    cfg.llm.all_api_keys = ["key"]
    cfg.llm.base_url = "http://localhost"
    cfg.llm.model = "model"
    cfg.llm.max_tokens = 1024
    cfg.llm.timeout = 1
    del cfg.llm.temperature  # getattr will return default
    ctx = TranslationConfigContext.from_config(cfg)
    assert ctx.temperature == 0.0


# ── TranslationService.save() tests ───────────────────────────────────


def test_translation_service_save(tmp_path):
    """TranslationService.save() persists result and returns output."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import TranslationResult

    cfg = MagicMock()
    cfg.llm.model = "test-model"
    cfg.llm.api_key = "test-key"
    cfg.llm.all_api_keys = ["test-key"]
    cfg.llm.base_url = "http://localhost:8001"
    cfg.llm.max_tokens = 1024
    cfg.llm.timeout = 1

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
    cfg.llm.model = "test-model"
    cfg.llm.api_key = "test-key"
    cfg.llm.all_api_keys = ["test-key"]
    cfg.llm.base_url = "http://localhost:8001"
    cfg.llm.max_tokens = 1024
    cfg.llm.timeout = 1

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
