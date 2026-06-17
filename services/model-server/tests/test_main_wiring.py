from types import SimpleNamespace


def test_main_wires_per_model_gpu_memory_utilization(monkeypatch):
    captured = {}

    class FakeEmbeddingService:
        def __init__(self, model_id, gpu_memory_utilization, max_model_len):
            captured["embedding"] = (model_id, gpu_memory_utilization, max_model_len)

    class FakeRerankService:
        def __init__(self, model_id, gpu_memory_utilization):
            captured["rerank"] = (model_id, gpu_memory_utilization)

    class FakeVLMService:
        def __init__(self, model_id, gpu_memory_utilization, image_analysis):
            captured["vlm"] = (model_id, gpu_memory_utilization, image_analysis)

    class FakeDocParseService:
        def __init__(self, backend, gpu_memory_utilization, model_path):
            captured["doc_parse"] = (backend, gpu_memory_utilization, model_path)

    fake_cfg = SimpleNamespace(
        embedding_model_id="embed-model",
        embedding_gpu_memory_utilization=0.35,
        embedding_max_model_len=4096,
        rerank_model_id="rerank-model",
        rerank_gpu_memory_utilization=0.2,
        doc_parse_model_id="vlm-model",
        doc_parse_gpu_memory_utilization=0.5,
        doc_parse_image_analysis=False,
        doc_parse_backend="vlm",
        doc_parse_model_path="/models/doc-parse",
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )

    monkeypatch.setattr("app.config.get_config", lambda: fake_cfg)
    monkeypatch.setattr("app.domain.embedding.EmbeddingService", FakeEmbeddingService)
    monkeypatch.setattr("app.domain.rerank.RerankService", FakeRerankService)
    monkeypatch.setattr("app.domain.vlm.VLMService", FakeVLMService)
    monkeypatch.setattr("app.domain.doc_parse.DocParseService", FakeDocParseService)
    monkeypatch.setattr("app.api.embedding.bind", lambda service: None)
    monkeypatch.setattr("app.api.rerank.bind", lambda service: None)
    monkeypatch.setattr("app.api.vlm.bind", lambda service: None)
    monkeypatch.setattr("app.api.file_parse.bind", lambda service: None)
    monkeypatch.setattr("app.api.health.register_services", lambda services: None)
    monkeypatch.setattr("app.utils.logger.setup_logging", lambda: None)

    import importlib
    import main as main_module

    importlib.reload(main_module)

    assert captured["embedding"] == ("embed-model", 0.35, 4096)
    assert captured["rerank"] == ("rerank-model", 0.2)
    assert captured["vlm"] == ("vlm-model", 0.5, False)
    assert captured["doc_parse"] == ("vlm", 0.5, "/models/doc-parse")
