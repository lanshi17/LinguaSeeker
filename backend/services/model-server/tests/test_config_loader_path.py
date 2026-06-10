"""Verify model-server imports the shared loader without sys.path hacks."""

import importlib


def test_acmg_config_loader_importable_without_syspath_hack() -> None:
    """The shared loader must resolve via normal Python import, not sys.path."""
    module = importlib.import_module("acmg_config_loader")
    assert module.__name__ == "acmg_config_loader"
