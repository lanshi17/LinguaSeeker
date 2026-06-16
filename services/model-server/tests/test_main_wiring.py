from types import SimpleNamespace


def test_main_wires_per_model_gpu_memory_utilization(monkeypatch):
    captured = {}

    class FakeEmbeddingService:
        def __init__(self, model_id, gpu_memory_utilization, max_model_len):
            captured["embedding"] = (model_id, gpu_memory_utilization, max_model_len)

    class FakeRerankService:
        def __init__(self, model_id, gpu_memory_utilization):
            captured["rerank"] = (model_id, gpu_memory_utilization)

    class FakeDocParseService:
        def __init__(self, backend, gpu_memory_utilization, model_path=""):
            captured["doc_parse"] = (backend, gpu_memory_utilization, model_path)

    fake_cfg = SimpleNamespace(
        embedding_model_id="embed-model",
        embedding_gpu_memory_utilization=0.35,
        embedding_max_model_len=4096,
        rerank_model_id="rerank-model",
        rerank_gpu_memory_utilization=0.2,
        doc_parse_backend="vlm",
        doc_parse_gpu_memory_utilization=0.85,
        doc_parse_model_path="opendatalab/MinerU2.5-Pro-2604-1.2B",
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )

    monkeypatch.setattr("app.config.get_config", lambda: fake_cfg)
    monkeypatch.setattr("app.domain.embedding.EmbeddingService", FakeEmbeddingService)
    monkeypatch.setattr("app.domain.rerank.RerankService", FakeRerankService)
    monkeypatch.setattr("app.domain.doc_parse.DocParseService", FakeDocParseService)
    monkeypatch.setattr("app.api.embedding.bind", lambda service: None)
    monkeypatch.setattr("app.api.rerank.bind", lambda service: None)
    monkeypatch.setattr("app.api.file_parse.bind", lambda service: None)
    monkeypatch.setattr("app.api.health.register_services", lambda services: None)
    monkeypatch.setattr("app.utils.logger.setup_logging", lambda: None)

    import importlib
    import main as main_module

    importlib.reload(main_module)

    assert captured["embedding"] == ("embed-model", 0.35, 4096)
    assert captured["rerank"] == ("rerank-model", 0.2)
    assert captured["doc_parse"] == ("vlm", 0.85, "opendatalab/MinerU2.5-Pro-2604-1.2B")
