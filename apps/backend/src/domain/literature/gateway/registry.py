from __future__ import annotations

from collections.abc import Iterable


from src.domain.literature.gateway.base import ProviderAdapter


class ProviderAdapterRegistry:
    def __init__(self, adapters: Iterable[ProviderAdapter] | None = None) -> None:
        self._adapters: dict[str, ProviderAdapter] = {}
        for adapter in adapters or ():
            self.register(adapter)

    def register(self, adapter: ProviderAdapter) -> None:
        provider = str(adapter.provider)
        if provider in self._adapters:
            raise ValueError(f"adapter already registered for provider: {provider}")
        self._adapters[provider] = adapter

    def get(self, provider: str) -> ProviderAdapter:
        if provider not in self._adapters:
            raise KeyError(provider)
        return self._adapters[provider]

    def supports(self, provider: str) -> bool:
        return provider in self._adapters

    def available_providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
