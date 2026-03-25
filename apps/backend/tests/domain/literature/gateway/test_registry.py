import pytest
from typing import final, override

from src.domain.literature.gateway.api_gateway import (
    ApiGatewayRequest,
    ApiGatewayResult,
)
from src.domain.literature.gateway.base import ProviderAdapter
from src.domain.literature.gateway.registry import ProviderAdapterRegistry


@final
class DummyAdapter(ProviderAdapter):
    provider: str = "dummy"

    @override
    async def execute(self, request: ApiGatewayRequest) -> ApiGatewayResult:
        return ApiGatewayResult(
            provider=self.provider,
            success=True,
            items=[{"query": request.query}],
            warnings=[],
        )


def test_registry_registers_and_resolves_adapter() -> None:
    registry = ProviderAdapterRegistry()
    adapter = DummyAdapter()

    registry.register(adapter)

    assert registry.supports("dummy") is True
    assert registry.get("dummy") is adapter
    assert registry.available_providers() == ("dummy",)


def test_registry_rejects_duplicate_provider_registration() -> None:
    registry = ProviderAdapterRegistry([DummyAdapter()])

    with pytest.raises(ValueError, match="dummy"):
        registry.register(DummyAdapter())


def test_registry_raises_for_unknown_provider() -> None:
    registry = ProviderAdapterRegistry()

    with pytest.raises(KeyError, match="missing"):
        _ = registry.get("missing")
