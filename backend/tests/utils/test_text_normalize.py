"""Tests for HTML-aware mined-text helpers."""

from __future__ import annotations

from src.utils.text_normalize import find_html_aware, unescape_mined_text


def test_unescape_mined_text_decodes_hgvs_gt() -> None:
    assert unescape_mined_text("c.538C&gt;T") == "c.538C>T"


def test_find_html_aware_matches_decoded_needle_to_entity_haystack() -> None:
    haystack = "患儿携带c.538C&gt;T变异。"
    start, end = find_html_aware(haystack, "c.538C>T")

    assert haystack[start:end] == "c.538C&gt;T"


def test_unescape_mined_text_decodes_markdown_tilde() -> None:
    assert unescape_mined_text("病例 1\\~4 诊断为经典型 RTT") == "病例 1~4 诊断为经典型 RTT"


def test_find_html_aware_matches_markdown_tilde() -> None:
    haystack = "病例 1\\~4 诊断为经典型 RTT"
    start, end = find_html_aware(haystack, "病例 1~4 诊断为经典型 RTT")

    assert haystack[start:end] == "病例 1\\~4 诊断为经典型 RTT"
