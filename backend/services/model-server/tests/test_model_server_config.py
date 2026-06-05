def test_vlm_config_defaults(monkeypatch):
    # With layered config, YAML values take precedence over Settings class defaults
    # The layered config loads at module import time, so env vars are already set
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings(_env_file=None)
    assert cfg.doc_parse_model_id == ""
    assert cfg.vlm_image_analysis is False
    assert cfg.vllm_gpu_memory_utilization == 0.9
    # Layered config defaults from config/defaults/main.yaml
    assert cfg.embedding_gpu_memory_utilization == 0.35
    assert cfg.embedding_max_model_len == 4096
    assert cfg.rerank_gpu_memory_utilization == 0.2
    assert cfg.vlm_gpu_memory_utilization == 0.5


def test_doc_parse_model_id_can_be_set(monkeypatch):
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings(_env_file=None, doc_parse_model_id="opendatalab/MinerU2.5-Pro-2604-1.2B")
    assert cfg.doc_parse_model_id == "opendatalab/MinerU2.5-Pro-2604-1.2B"


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


def test_no_env_files_configured():
    """Settings no longer uses env_file; config comes from config-dev.yaml."""
    from app.config import Settings

    env_file = Settings.model_config.get("env_file")
    # env_file should not be configured — YAML is the source of truth
    assert env_file is None
