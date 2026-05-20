from unittest.mock import MagicMock, patch


def test_embedding_service_load_vllm():
    """Verify EmbeddingService._load() creates vllm.LLM with correct params."""
    with patch("app.domain.embedding.vllm.LLM") as mock_llm_cls:
        mock_llm_cls.return_value = MagicMock()
        from app.domain.embedding import EmbeddingService
        svc = EmbeddingService(
            model_id="Qwen/Qwen3-Embedding-0.6B",
            gpu_memory_utilization=0.5,
        )
        assert svc.model_id == "Qwen/Qwen3-Embedding-0.6B"
        assert svc.ready is False
        svc.ensure_loaded()
        mock_llm_cls.assert_called_once_with(
            model="Qwen/Qwen3-Embedding-0.6B",
            runner="pooling",
            convert="embed",
            gpu_memory_utilization=0.5,
            trust_remote_code=True,
        )


def test_embedding_service_infer():
    """Verify infer() calls vllm embed and returns tensors."""
    mock_output = MagicMock()
    mock_output.outputs.embedding = [0.1, 0.2, 0.3]

    with patch("app.domain.embedding.vllm.LLM") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm.embed.return_value = [mock_output]
        mock_llm_cls.return_value = mock_llm

        from app.domain.embedding import EmbeddingService
        svc = EmbeddingService(model_id="Qwen/Qwen3-Embedding-0.6B")
        result = svc.infer(["hello world"])

        mock_llm.embed.assert_called_once_with(["hello world"], use_tqdm=False)
        assert result.shape == (1, 3)


def test_embedding_service_unload_shuts_down_engine():
    """Verify unload() releases vllm engine resources."""
    with patch("app.domain.embedding.vllm.LLM") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm

        from app.domain.embedding import EmbeddingService

        svc = EmbeddingService(model_id="Qwen/Qwen3-Embedding-0.6B")
        svc.ensure_loaded()
        assert svc.ready is True

        svc.unload()

        mock_llm.llm_engine.engine_core.shutdown.assert_called_once_with(timeout=0)
        assert svc.ready is False
