"""Tests for lit-acquisition web search adapter constructor contracts.

The orchestrator passes ``timeout=ws.timeout`` to every adapter; each
subclass must accept and forward it to the base class (regression test
for TavilyAdapter/SerpApiAdapter raising TypeError on the kwarg).
"""

from __future__ import annotations

from lit_acquisition.web_search.serpapi_adapter import SerpApiAdapter
from lit_acquisition.web_search.tavily_adapter import TavilyAdapter


def test_tavily_adapter_accepts_timeout():
    adapter = TavilyAdapter(api_key="tvly-test", search_depth="basic", timeout=42, max_results=7)
    assert adapter.timeout == 42
    assert adapter.max_results == 7


def test_serpapi_adapter_accepts_timeout():
    adapter = SerpApiAdapter(api_key="test", engine="google", timeout=33, max_results=5)
    assert adapter.timeout == 33
    assert adapter.max_results == 5
