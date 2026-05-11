def test_vlm_config_defaults(monkeypatch):
    monkeypatch.setenv("VLM_MODEL_ID", "opendatalab/MinerU2.5-Pro-2604-1.2B")
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings()
    assert cfg.vlm_model_id == "opendatalab/MinerU2.5-Pro-2604-1.2B"
    assert cfg.vlm_image_analysis is False
    assert cfg.vllm_gpu_memory_utilization == 0.9


def test_vlm_config_empty_by_default(monkeypatch):
    monkeypatch.delenv("VLM_MODEL_ID", raising=False)
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings()
    assert cfg.vlm_model_id == ""
