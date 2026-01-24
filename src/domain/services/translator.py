"""Translation domain service."""

from abc import ABC, abstractmethod

from ..value_objects import Language


class TranslatorService(ABC):
    """Domain service for document translation."""

    @abstractmethod
    def translate_to_english(self, text: str, source_lang: Language) -> str:
        """Translate text to English.

        Args:
            text: Text to translate
            source_lang: Source language

        Returns:
            English translation
        """
