def test_vlm_config_defaults(monkeypatch):
    monkeypatch.delenv("EMBEDDING_GPU_MEMORY_UTILIZATION", raising=False)
    monkeypatch.delenv("EMBEDDING_MAX_MODEL_LEN", raising=False)
    monkeypatch.delenv("RERANK_GPU_MEMORY_UTILIZATION", raising=False)
    monkeypatch.delenv("VLM_GPU_MEMORY_UTILIZATION", raising=False)
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings(_env_file=None, vlm_model_id="opendatalab/MinerU2.5-Pro-2604-1.2B")
    assert cfg.vlm_model_id == "opendatalab/MinerU2.5-Pro-2604-1.2B"
    assert cfg.vlm_image_analysis is False
    assert cfg.vllm_gpu_memory_utilization == 0.9
    assert cfg.embedding_gpu_memory_utilization == 0.9
    assert cfg.embedding_max_model_len == 32768
    assert cfg.rerank_gpu_memory_utilization == 0.9
    assert cfg.vlm_gpu_memory_utilization == 0.9


def test_model_server_allows_per_model_gpu_memory_overrides(monkeypatch):
    monkeypatch.setenv("EMBEDDING_GPU_MEMORY_UTILIZATION", "0.35")
    monkeypatch.setenv("EMBEDDING_MAX_MODEL_LEN", "4096")
    monkeypatch.setenv("RERANK_GPU_MEMORY_UTILIZATION", "0.2")
    monkeypatch.setenv("VLM_GPU_MEMORY_UTILIZATION", "0.5")
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings()
    assert cfg.embedding_gpu_memory_utilization == 0.35
    assert cfg.embedding_max_model_len == 4096
    assert cfg.rerank_gpu_memory_utilization == 0.2
    assert cfg.vlm_gpu_memory_utilization == 0.5


def test_vlm_config_empty_by_default(monkeypatch):
    monkeypatch.delenv("VLM_MODEL_ID", raising=False)
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings(_env_file=None)
    assert cfg.vlm_model_id == ""


def test_no_env_files_configured():
    """Settings no longer uses env_file; config comes from config-dev.yaml."""
    from app.config import Settings

    env_file = Settings.model_config.get("env_file")
    # env_file should not be configured — YAML is the source of truth
    assert env_file is None
