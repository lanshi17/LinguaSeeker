def test_model_server_allows_per_model_gpu_memory_overrides(monkeypatch):
    monkeypatch.setenv("EMBEDDING_GPU_MEMORY_UTILIZATION", "0.35")
    monkeypatch.setenv("EMBEDDING_MAX_MODEL_LEN", "4096")
    monkeypatch.setenv("RERANK_GPU_MEMORY_UTILIZATION", "0.2")
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings()
    assert cfg.embedding_gpu_memory_utilization == 0.35
    assert cfg.embedding_max_model_len == 4096
    assert cfg.rerank_gpu_memory_utilization == 0.2


def test_no_env_files_configured():
    """Settings no longer uses env_file; config comes from backend/config."""
    from app.config import Settings

    env_file = Settings.model_config.get("env_file")
    # env_file should not be configured — YAML is the source of truth
    assert env_file is None


def test_model_server_uses_shared_config_loader():
    """Model-server uses the shared acmg-config-loader package (no local copy)."""
    import app.config as model_server_config
    from acmg_config_loader import load_backend_config_into_env

    assert model_server_config.load_backend_config_into_env is load_backend_config_into_env
