from unittest.mock import MagicMock, patch


def test_rerank_service_load_vllm():
    """Verify RerankService._load() creates vllm.LLM with correct params."""
    with patch("app.domain.rerank.vllm.LLM") as mock_llm_cls:
        mock_llm_cls.return_value = MagicMock()

        from app.domain.rerank import RerankService

        svc = RerankService(
            model_id="BAAI/bge-reranker-v2-m3",
            gpu_memory_utilization=0.5,
        )
        assert svc.model_id == "BAAI/bge-reranker-v2-m3"
        assert svc.ready is False
        svc.ensure_loaded()
        mock_llm_cls.assert_called_once_with(
            model="BAAI/bge-reranker-v2-m3",
            runner="pooling",
            gpu_memory_utilization=0.5,
            trust_remote_code=True,
        )


def test_rerank_service_infer():
    """Verify infer() calls vllm score and returns scores."""
    mock_output = MagicMock()
    mock_output.outputs.score = 0.85

    with patch("app.domain.rerank.vllm.LLM") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm.score.return_value = [mock_output]
        mock_llm_cls.return_value = mock_llm

        from app.domain.rerank import RerankService
        svc = RerankService(model_id="BAAI/bge-reranker-v2-m3")
        scores = svc.infer("query", ["doc1"])

        mock_llm.score.assert_called_once_with("query", ["doc1"], use_tqdm=False)
        assert len(scores) == 1
        assert scores[0] == 0.85


def test_rerank_service_unload_shuts_down_engine():
    """Verify unload() releases vllm engine resources."""
    with patch("app.domain.rerank.vllm.LLM") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm

        from app.domain.rerank import RerankService

        svc = RerankService(model_id="BAAI/bge-reranker-v2-m3")
        svc.ensure_loaded()
        assert svc.ready is True

        svc.unload()

        mock_llm.llm_engine.engine_core.shutdown.assert_called_once_with(timeout=0)
        assert svc.ready is False
