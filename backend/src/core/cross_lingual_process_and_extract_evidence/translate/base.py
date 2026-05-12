"""Interface for translators — Clean Architecture boundary."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple

from ..contracts import FormattedDocument, TranslationResult


class BaseTranslator(ABC):
    """Abstract translator interface.

    Implementations translate a ``FormattedDocument`` into a ``TranslationResult``.
    Swappable for testing or alternative translation strategies (e.g. NMT vs LLM).
    """

    @abstractmethod
    def _translate(self, formatted: FormattedDocument) -> Tuple[str, str, str, str, List[str], List[str]]:
        """Run the full translation pipeline.

        Returns (terminology, structure_plan, draft, translated, source_segments, warnings).
        """
        ...

    @abstractmethod
    def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult:
        """Run the full pipeline and return a ``TranslationResult``."""
        ...
