from __future__ import annotations

import main


def test_build_loguru_options_disable_diagnostics_in_production() -> None:
    options = main._build_loguru_runtime_options(environment="production", debug=True)
    assert options["diagnose"] is False
    assert options["backtrace"] is False
    assert options["enqueue"] is True


def test_build_cors_options_disables_credentials_for_wildcard() -> None:
    options = main._build_cors_options(["*"])
    assert options["allow_origins"] == ["*"]
    assert options["allow_credentials"] is False


def test_parse_cors_origins_accepts_json_array_string() -> None:
    origins = main._parse_cors_origins('["http://localhost:3000", "http://localhost:8080"]')
    assert origins == ["http://localhost:3000", "http://localhost:8080"]


def test_main_uses_available_settings_cors_field() -> None:
    assert main._cors_options["allow_origins"] == main._parse_cors_origins(main.settings.cors_origins)


