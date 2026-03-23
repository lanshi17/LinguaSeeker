from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.domain.literature.gateway.api_gateway import (
    ApiGatewayRequest,
    ApiGatewayResult,
)
from src.domain.literature.gateway.base import LiteratureGatewayAdapter
from src.domain.literature.gateway.registry import (
    DuplicateGatewayProviderError,
    GatewayAdapterRegistry,
    UnknownGatewayProviderError,
)


@dataclass
class DummyAdapter(LiteratureGatewayAdapter):
    provider: str

    async def execute(self, request: ApiGatewayRequest) -> ApiGatewayResult:
        return ApiGatewayResult(
            provider=self.provider,
            success=True,
            items=[],
            warnings=[],
        )


def test_registry_returns_registered_adapter_for_provider() -> None:
    registry = GatewayAdapterRegistry()
    adapter = DummyAdapter(provider="pmc")

    registry.register(adapter)

    resolved = registry.get("pmc")
    assert resolved is adapter


def test_registry_raises_unknown_provider_error_for_missing_provider() -> None:
    registry = GatewayAdapterRegistry()

    with pytest.raises(UnknownGatewayProviderError, match="unknown-provider"):
        registry.get("unknown-provider")


def test_registry_rejects_duplicate_provider_registration() -> None:
    registry = GatewayAdapterRegistry()
    first = DummyAdapter(provider="pmc")
    second = DummyAdapter(provider="pmc")

    registry.register(first)

    with pytest.raises(DuplicateGatewayProviderError, match="pmc"):
        registry.register(second)


def test_registry_lists_registered_providers_in_registration_order() -> None:
    registry = GatewayAdapterRegistry()
    registry.register(DummyAdapter(provider="pmc"))
    registry.register(DummyAdapter(provider="jstage"))

    assert registry.providers() == ["pmc", "jstage"]
