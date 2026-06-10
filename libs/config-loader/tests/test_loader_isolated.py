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
