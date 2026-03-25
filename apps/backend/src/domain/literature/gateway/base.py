from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.literature.gateway.contracts import (
        ApiGatewayRequest,
        ApiGatewayResult,
    )


class ProviderAdapter(ABC):
    provider: str

    @abstractmethod
    async def execute(self, request: ApiGatewayRequest) -> ApiGatewayResult:
        raise NotImplementedError
