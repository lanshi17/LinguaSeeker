from unittest.mock import MagicMock, patch


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

        mock_llm.score.assert_called_once()
        assert len(scores) == 1
        assert scores[0] == 0.85
