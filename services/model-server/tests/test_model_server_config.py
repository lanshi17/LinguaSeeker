

def test_settings_defaults(monkeypatch):
    """Settings provides sensible defaults with no env vars set."""
    # Clear any env vars that could interfere
    for key in (
        "HOST", "PORT", "API_KEY", "LOG_LEVEL",
        "EMBEDDING_MODEL_ID", "EMBEDDING_GPU_MEMORY_UTILIZATION",
        "RERANK_MODEL_ID", "RERANK_GPU_MEMORY_UTILIZATION",
        "DOC_PARSE_MODEL_ID", "DOC_PARSE_GPU_MEMORY_UTILIZATION",
    ):
        monkeypatch.delenv(key, raising=False)

    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings(_env_file=None)
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8001
    assert cfg.api_key == ""
    assert cfg.embedding_model_id == "Qwen/Qwen3-Embedding-0.6B"
    assert cfg.rerank_model_id == "BAAI/bge-reranker-v2-m3"
    assert cfg.doc_parse_model_id == ""
    assert cfg.embedding_gpu_memory_utilization == 0.9
    assert cfg.rerank_gpu_memory_utilization == 0.9
    assert cfg.doc_parse_gpu_memory_utilization == 0.9


def test_doc_parse_model_id_can_be_set(monkeypatch):
    monkeypatch.delenv("DOC_PARSE_MODEL_ID", raising=False)
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings(_env_file=None, doc_parse_model_id="opendatalab/MinerU2.5-Pro-2604-1.2B")
    assert cfg.doc_parse_model_id == "opendatalab/MinerU2.5-Pro-2604-1.2B"


def test_model_server_allows_per_model_gpu_memory_overrides(monkeypatch):
    monkeypatch.setenv("EMBEDDING_GPU_MEMORY_UTILIZATION", "0.35")
    monkeypatch.setenv("EMBEDDING_MAX_MODEL_LEN", "4096")
    monkeypatch.setenv("RERANK_GPU_MEMORY_UTILIZATION", "0.2")
    monkeypatch.setenv("DOC_PARSE_GPU_MEMORY_UTILIZATION", "0.5")
    from app.config import Settings, get_config
    get_config.cache_clear()

    cfg = Settings(_env_file=None)
    assert cfg.embedding_gpu_memory_utilization == 0.35
    assert cfg.embedding_max_model_len == 4096
    assert cfg.rerank_gpu_memory_utilization == 0.2
    assert cfg.doc_parse_gpu_memory_utilization == 0.5


def test_settings_reads_env_file():
    """Settings is configured to read a .env file for standalone deployment."""
    from app.config import Settings

    env_file = Settings.model_config.get("env_file")
    assert env_file == ".env"


def test_no_acmg_config_loader_dependency():
    """Model-server no longer depends on acmg-config-loader."""
    import app.config as cfg_module

    assert not hasattr(cfg_module, "load_backend_config_into_env")
    assert not hasattr(cfg_module, "_BACKEND_ROOT")
