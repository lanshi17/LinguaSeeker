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


def test_build_root_payload_hides_internal_details() -> None:
    payload = main._build_root_payload()
    assert "Environment" not in payload
    assert "Debug Mode" not in payload
    assert "API Prefix" not in payload
    assert set(payload.keys()) == {"name", "version", "status"}
