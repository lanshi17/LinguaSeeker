from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LiteratureGatewayAdapter(ABC):
    provider: str

    @abstractmethod
    async def execute(self, request: Any) -> Any:
        raise NotImplementedError
