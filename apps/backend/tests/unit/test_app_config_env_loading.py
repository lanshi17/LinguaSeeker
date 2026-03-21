from src.config import AppConfig


def test_from_env_loads_env_local_from_project_root(tmp_path, monkeypatch) -> None:
    project_root = tmp_path / "backend"
    project_root.mkdir(parents=True, exist_ok=True)
    env_local = project_root / ".env.local"
    env_local.write_text(
        "REDIS_HOST=127.0.0.1\nREDIS_PASSWORD=local_secret\n", encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        AppConfig,
        "_project_root",
        staticmethod(lambda: project_root),
    )
    monkeypatch.delenv("ENV_FILE", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)

    cfg = AppConfig.from_env()

    assert cfg.redis.host == "127.0.0.1"
    assert cfg.redis.password == "local_secret"
