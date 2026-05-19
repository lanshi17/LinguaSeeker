from unittest.mock import patch


def test_main_imports():
    """Verify main.py can be imported without errors (mocking heavy deps)."""
    with patch("app.domain.embedding.vllm.LLM"):
        with patch("app.domain.rerank.vllm.LLM"):
            with patch("app.domain.vlm.vllm.LLM"):
                with patch("app.domain.vlm.MinerUClient"):
                    import app.api.vlm as vlm_mod
                    assert hasattr(vlm_mod, "router")


def test_main_does_not_register_vlm_route_without_model(monkeypatch):
    """VLM route should not be exposed unless VLM_MODEL_ID is configured."""
    monkeypatch.delenv("VLM_MODEL_ID", raising=False)

    from app.config import get_config
    get_config.cache_clear()

    with patch("app.domain.embedding.vllm.LLM"):
        with patch("app.domain.rerank.vllm.LLM"):
            with patch("app.domain.vlm.vllm.LLM"):
                with patch("app.domain.vlm.MinerUClient"):
                    import importlib
                    import main

                    main = importlib.reload(main)
                    paths = main.app.openapi()["paths"]

    assert "/v1/chat/completions" not in paths
