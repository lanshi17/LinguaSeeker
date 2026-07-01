"""Translation pipeline exceptions."""

from __future__ import annotations


class TranslationError(RuntimeError):
    """Raised when translation critically fails (e.g. LLM returns unchanged text)."""
