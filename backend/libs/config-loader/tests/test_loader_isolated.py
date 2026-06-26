"""Verify the package can be installed in isolation and exposes the expected API."""

import importlib


def test_package_imports() -> None:
    """The package must be importable after editable install."""
    module = importlib.import_module("acmg_config_loader")
    assert module is not None


def test_loader_symbol_exposed() -> None:
    """The package must re-export load_backend_config_into_env."""
    from acmg_config_loader import load_backend_config_into_env

    assert callable(load_backend_config_into_env)


def test_loader_signature_unchanged() -> None:
    """The function signature must match the original backend/src/core/config_loader.py."""
    import inspect

    from acmg_config_loader import load_backend_config_into_env

    sig = inspect.signature(load_backend_config_into_env)
    params = list(sig.parameters)
    assert params == ["backend_root", "environ"]


def test_loader_runs_with_synthetic_config(tmp_path) -> None:
    """Loader reads layered YAML in order: defaults → environments → vault."""
    from acmg_config_loader import load_backend_config_into_env

    root = tmp_path
    (root / "config" / "defaults").mkdir(parents=True)
    (root / "config" / "environments").mkdir(parents=True)
    (root / "config" / "vault").mkdir(parents=True)

    (root / "config" / "defaults" / "main.yaml").write_text(
        "service:\n  port: 8000\n  name: default\n", encoding="utf-8"
    )
    (root / "config" / "environments" / "development.yaml").write_text(
        "service:\n  port: 9000\n", encoding="utf-8"
    )
    (root / "config" / "vault" / "development.yaml").write_text(
        "service:\n  secret: top\n", encoding="utf-8"
    )

    environ: dict[str, str] = {}
    load_backend_config_into_env(root, environ=environ)

    assert environ["SERVICE_NAME"] == "default"
    assert environ["SERVICE_PORT"] == "9000"
    assert environ["SERVICE_SECRET"] == "top"

    # existing env var wins
    environ2: dict[str, str] = {"SERVICE_PORT": "12345"}
    load_backend_config_into_env(root, environ=environ2)
    assert environ2["SERVICE_PORT"] == "12345"
