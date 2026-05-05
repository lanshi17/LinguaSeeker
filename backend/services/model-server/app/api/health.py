"""Health check route."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.models import HealthResponse

if TYPE_CHECKING:
    from app.domain.base import BaseModelService

router = APIRouter(tags=["health"])

# Populated by main.py at startup
_services: dict[str, BaseModelService] = {}


def register_services(services: dict[str, BaseModelService]) -> None:
    _services.update(services)


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        models={name: svc.ready for name, svc in _services.items()},
    )
