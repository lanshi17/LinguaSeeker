from __future__ import annotations

from collections import OrderedDict

from .base import LiteratureGatewayAdapter


class UnknownGatewayProviderError(KeyError):
    pass


class DuplicateGatewayProviderError(ValueError):
    pass


class GatewayAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: OrderedDict[str, LiteratureGatewayAdapter] = OrderedDict()

    def register(self, adapter: LiteratureGatewayAdapter) -> None:
        provider = adapter.provider
        if provider in self._adapters:
            raise DuplicateGatewayProviderError(provider)
        self._adapters[provider] = adapter

    def get(self, provider: str) -> LiteratureGatewayAdapter:
        try:
            return self._adapters[provider]
        except KeyError as exc:
            raise UnknownGatewayProviderError(provider) from exc

    def providers(self) -> list[str]:
        return list(self._adapters.keys())
