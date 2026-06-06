"""Tests for the shared backend/config loader."""

import os
from pathlib import Path


def test_loader_reads_layered_backend_config_and_ignores_legacy_file(tmp_path: Path, monkeypatch) -> None:
    """Layered backend/config YAML is the only file-based config source."""
    from src.core.config_loader import load_backend_config_into_env

    config_root = tmp_path / "config"
    (config_root / "defaults").mkdir(parents=True)
    (config_root / "environments").mkdir()
    (config_root / "vault").mkdir()
    (config_root / "defaults" / "main.yaml").write_text(
        """
single_source:
  marker: defaults
  keep: from-defaults
""",
        encoding="utf-8",
    )
    (config_root / "environments" / "testing.yaml").write_text(
        """
single_source:
  marker: environment
""",
        encoding="utf-8",
    )
    (config_root / "vault" / "testing.yaml").write_text(
        """
single_source:
  secret: vault-secret
""",
        encoding="utf-8",
    )
    (tmp_path / "config-dev.yaml").write_text(
        """
single_source:
  marker: legacy
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.delenv("SINGLE_SOURCE_MARKER", raising=False)
    monkeypatch.delenv("SINGLE_SOURCE_KEEP", raising=False)
    monkeypatch.delenv("SINGLE_SOURCE_SECRET", raising=False)

    load_backend_config_into_env(tmp_path)

    assert os.environ["SINGLE_SOURCE_MARKER"] == "environment"
    assert os.environ["SINGLE_SOURCE_KEEP"] == "from-defaults"
    assert os.environ["SINGLE_SOURCE_SECRET"] == "vault-secret"


def test_loader_preserves_existing_environment_variables(tmp_path: Path, monkeypatch) -> None:
    """Environment variables keep precedence over backend/config YAML."""
    from src.core.config_loader import load_backend_config_into_env

    config_root = tmp_path / "config" / "defaults"
    config_root.mkdir(parents=True)
    (config_root / "main.yaml").write_text(
        """
single_source:
  marker: yaml-value
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SINGLE_SOURCE_MARKER", "env-value")

    load_backend_config_into_env(tmp_path)

    assert os.environ["SINGLE_SOURCE_MARKER"] == "env-value"
