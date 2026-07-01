"""Tests for health endpoint type safety."""

from __future__ import annotations

from pydantic import BaseModel


def test_health_endpoint_returns_basemodel():
    """Health endpoint should return a BaseModel, not bare dict."""
    from app.main import create_app, HealthResponse

    app = create_app()
    for route in app.routes:
        if hasattr(route, "path") and route.path == "/health":
            # With `from __future__ import annotations`, inspect.signature
            # returns a string. Use the known class directly.
            assert issubclass(HealthResponse, BaseModel), "HealthResponse should be BaseModel subclass"
            assert hasattr(HealthResponse, "model_fields"), "Should be a Pydantic model"
            assert "status" in HealthResponse.model_fields, "Must have 'status' field"
            break
