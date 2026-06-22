"""E2E API tests — validates actual model inference through the per-service entry points.

These tests require a GPU and real model weights. They test the full path:
HTTP request → FastAPI route → domain service → vLLM inference → response.

Run with: pytest tests/test_e2e_api.py -v --run-e2e
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Undo conftest stubs — load real vllm and mineru_vl_utils ────────
# The tests/conftest.py installs CPU-only stubs for vllm and mineru_vl_utils.
# E2E tests need the real GPU libraries, so we remove the stubs and reload.
_STUB_MODULES = ["vllm", "mineru_vl_utils"]
for _mod_name in _STUB_MODULES:
    _mod = sys.modules.get(_mod_name)
    if _mod is not None and hasattr(_mod, "__file__") is False:
        # It's a stub (ModuleType with no __file__), remove it
        del sys.modules[_mod_name]

# Now import real vllm if available
try:
    import vllm as _real_vllm  # noqa: F401
    _HAS_VLLM = True
except ImportError:
    _HAS_VLLM = False

# Reload domain modules so they pick up real vllm
if _HAS_VLLM:
    for _mod_name in ["app.domain.embedding", "app.domain.rerank", "app.domain.base"]:
        if _mod_name in sys.modules:
            importlib.reload(sys.modules[_mod_name])

pytestmark = pytest.mark.skipif(not _HAS_VLLM, reason="vllm not installed — E2E tests require GPU libraries")


@pytest.fixture(scope="module")
def embedding_app():
    """Create embedding FastAPI app with real model."""
    from app.config import get_config
    get_config.cache_clear()
    if "main_embedding" in sys.modules:
        importlib.reload(sys.modules["main_embedding"])
    else:
        importlib.import_module("main_embedding")
    return sys.modules["main_embedding"].app


@pytest.fixture(scope="module")
def rerank_app():
    """Create rerank FastAPI app with real model."""
    from app.config import get_config
    get_config.cache_clear()
    if "main_rerank" in sys.modules:
        importlib.reload(sys.modules["main_rerank"])
    else:
        importlib.import_module("main_rerank")
    return sys.modules["main_rerank"].app


class TestEmbeddingE2E:
    """End-to-end embedding tests with real model."""

    @pytest.mark.integration
    def test_health(self, embedding_app):
        client = TestClient(embedding_app)
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "embedding" in body["models"]

    @pytest.mark.integration
    def test_single_text_embedding(self, embedding_app):
        client = TestClient(embedding_app)
        resp = client.post("/v1/embeddings", json={"input": "hello world"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert len(body["data"][0]["embedding"]) == 1024
        assert body["data"][0]["object"] == "embedding"

    @pytest.mark.integration
    def test_batch_embedding(self, embedding_app):
        client = TestClient(embedding_app)
        resp = client.post("/v1/embeddings", json={"input": ["hello", "world", "test"]})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 3
        # Check ordering preserved
        assert body["data"][0]["index"] == 0
        assert body["data"][1]["index"] == 1
        assert body["data"][2]["index"] == 2

    @pytest.mark.integration
    def test_embedding_normalized(self, embedding_app):
        client = TestClient(embedding_app)
        resp = client.post("/v1/embeddings", json={"input": "normalize me"})
        body = resp.json()
        vec = np.array(body["data"][0]["embedding"])
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 0.01, f"Expected unit norm, got {norm}"


class TestRerankE2E:
    """End-to-end rerank tests with real model."""

    @pytest.mark.integration
    def test_health(self, rerank_app):
        client = TestClient(rerank_app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "rerank" in resp.json()["models"]

    @pytest.mark.integration
    def test_rerank_scoring(self, rerank_app):
        client = TestClient(rerank_app)
        resp = client.post("/v1/rerank", json={
            "query": "machine learning",
            "documents": [
                "Deep learning is a subset of machine learning",
                "The weather is nice today",
                "Neural networks are used in ML",
            ],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["results"]) == 3
        # ML-related docs should score higher than weather
        scores = {r["document"]: r["relevance_score"] for r in body["results"]}
        assert scores["Deep learning is a subset of machine learning"] > scores["The weather is nice today"]

    @pytest.mark.integration
    def test_rerank_top_k(self, rerank_app):
        client = TestClient(rerank_app)
        resp = client.post("/v1/rerank", json={
            "query": "test",
            "documents": ["a", "b", "c", "d"],
            "top_k": 2,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["results"]) == 2


class TestCrossServiceIsolation:
    """Verify each service is truly independent."""

    @pytest.mark.integration
    def test_embedding_has_no_rerank_route(self, embedding_app):
        client = TestClient(embedding_app)
        resp = client.post("/v1/rerank", json={"query": "x", "documents": ["y"]})
        assert resp.status_code == 404

    @pytest.mark.integration
    def test_rerank_has_no_embedding_route(self, rerank_app):
        client = TestClient(rerank_app)
        resp = client.post("/v1/embeddings", json={"input": "test"})
        assert resp.status_code == 404
