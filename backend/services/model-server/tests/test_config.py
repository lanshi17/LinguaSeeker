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

    cfg = Settings(_env_file=None)
    assert cfg.vlm_model_id == ""


def test_env_files_are_resolved_from_project_roots():
    from pathlib import Path

    from app.config import Settings

    env_files = tuple(Path(path) for path in Settings.model_config["env_file"])
    backend_root = Path(__file__).resolve().parents[3]
    service_root = Path(__file__).resolve().parents[1]

    assert all(path.is_absolute() for path in env_files)
    assert backend_root / ".env.local" in env_files
    assert backend_root / ".env" in env_files
    assert service_root / ".env.local" in env_files
    assert service_root / ".env" in env_files
