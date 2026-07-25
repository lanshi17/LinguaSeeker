"""Tests for GraphRAG API routes."""

from __future__ import annotations

from src.api.v1.graph_rag import router


def test_query_route_is_registered() -> None:
    routes = [r.path for r in router.routes]
    assert "/query" in routes


def test_graph_route_is_registered() -> None:
    routes = [r.path for r in router.routes]
    assert "/graph" in routes


def test_graph_route_has_get_method() -> None:
    graph_route = next(r for r in router.routes if r.path == "/graph")
    assert "GET" in graph_route.methods
