from unittest.mock import patch


def test_main_imports():
    """Verify main.py can be imported without errors (mocking heavy deps)."""
    with patch("app.domain.embedding.vllm.LLM"):
        with patch("app.domain.rerank.vllm.LLM"):
            with patch("app.domain.llm.vllm.LLM"):
                with patch("app.domain.llm.MinerUClient"):
                    import app.api.vlm as vlm_mod
                    assert hasattr(vlm_mod, "router")
