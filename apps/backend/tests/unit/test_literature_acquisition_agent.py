from __future__ import annotations

from src.domain.literature.acquisition_agent import fingerprint_web_url, normalize_web_url


def test_normalize_web_url_removes_tracking_params_and_sorts_query() -> None:
    left = normalize_web_url(
        "https://Example.org/path/?b=2&utm_source=google&a=1&utm_medium=cpc#frag"
    )
    right = normalize_web_url("https://example.org/path?a=1&b=2")

    assert left == "https://example.org/path?a=1&b=2"
    assert left == right


def test_fingerprint_web_url_ignores_default_port_and_query_order() -> None:
    left = fingerprint_web_url("http://example.org:80/path?b=2&a=1")
    right = fingerprint_web_url("http://example.org/path?a=1&b=2")

    assert left == right
