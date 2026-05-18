"""Interface for document formatters — Clean Architecture boundary."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ...contracts import FormattedDocument


class BaseFormatter(ABC):
    """Abstract formatter interface. Swappable for testing or alternative strategies."""

    @abstractmethod
    def format(
        self,
        pages: List[Dict[str, Any]],
        content_blocks: List[Dict[str, Any]] | None = None,
    ) -> FormattedDocument:
        ...
