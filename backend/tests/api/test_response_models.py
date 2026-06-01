"""Tests for API route response_model declarations."""
from __future__ import annotations

STREAMING_ROUTES = {"GET /api/v1/chat/sessions/{session_id}/stream"}


def test_all_v1_routes_declare_response_model():
    """All API v1 routes should declare response_model per project rule 22."""
    from app.main import create_app
    app = create_app()

    routes_without_model = []
    for route in app.routes:
        if not hasattr(route, "path") or not route.path.startswith("/api/v1"):
            continue
        methods = ",".join(route.methods or [])
        route_key = f"{methods} {route.path}"
        if route_key in STREAMING_ROUTES:
            continue
        if getattr(route, "response_model", None) is None:
            routes_without_model.append(route_key)

    assert routes_without_model == [], f"Routes missing response_model: {routes_without_model}"
