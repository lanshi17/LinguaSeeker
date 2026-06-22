"""Tests for per-service entry points — verify each boots a single-service FastAPI app."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_config(**overrides):
    """Create a mock config object with sensible defaults."""
    defaults = {
        "host": "127.0.0.1",
        "port": 8001,
        "log_level": "info",
        "api_key": "",
        "embedding_model_id": "test-embedding-model",
        "embedding_gpu_memory_utilization": 0.9,
        "embedding_max_model_len": 4096,
        "rerank_model_id": "test-rerank-model",
        "rerank_gpu_memory_utilization": 0.9,
        "doc_parse_model_id": "",
        "doc_parse_backend": "vlm",
        "doc_parse_gpu_memory_utilization": 0.9,
        "doc_parse_model_path": "test-model-path",
        "doc_parse_image_analysis": False,
    }
    defaults.update(overrides)
    return type("MockConfig", (), defaults)()


class TestEmbeddingEntryPoint:
    def test_app_has_only_embedding_and_health_routers(self):
        with patch("app.config.get_config", return_value=_make_config()):
            mod = importlib.import_module("main_embedding")
            routes = {r.path for r in mod.app.routes if hasattr(r, "path")}
            assert "/v1/embeddings" in routes
            assert "/health" in routes
            assert "/v1/rerank" not in routes
            assert "/file_parse" not in routes
            assert "/v1/chat/completions" not in routes

    def test_app_title(self):
        with patch("app.config.get_config", return_value=_make_config()):
            mod = importlib.import_module("main_embedding")
            assert "Embedding" in mod.app.title


class TestRerankEntryPoint:
    def test_app_has_only_rerank_and_health_routers(self):
        with patch("app.config.get_config", return_value=_make_config()):
            mod = importlib.import_module("main_rerank")
            routes = {r.path for r in mod.app.routes if hasattr(r, "path")}
            assert "/v1/rerank" in routes
            assert "/health" in routes
            assert "/v1/embeddings" not in routes
            assert "/file_parse" not in routes

    def test_app_title(self):
        with patch("app.config.get_config", return_value=_make_config()):
            mod = importlib.import_module("main_rerank")
            assert "Rerank" in mod.app.title


class TestDocParseEntryPoint:
    def test_app_has_only_file_parse_and_health_routers(self):
        with patch("app.config.get_config", return_value=_make_config()):
            mod = importlib.import_module("main_doc_parse")
            routes = {r.path for r in mod.app.routes if hasattr(r, "path")}
            assert "/file_parse" in routes
            assert "/health" in routes
            assert "/v1/embeddings" not in routes
            assert "/v1/rerank" not in routes

    def test_app_title(self):
        with patch("app.config.get_config", return_value=_make_config()):
            mod = importlib.import_module("main_doc_parse")
            assert "Doc Parse" in mod.app.title


class TestVLMEntryPoint:
    def test_exits_when_doc_parse_model_id_empty(self):
        """VLM server requires DOC_PARSE_MODEL_ID — should sys.exit(1) if empty."""
        with patch("app.config.get_config", return_value=_make_config(doc_parse_model_id="")):
            with pytest.raises(SystemExit) as exc_info:
                importlib.import_module("main_vlm")
            assert exc_info.value.code == 1
