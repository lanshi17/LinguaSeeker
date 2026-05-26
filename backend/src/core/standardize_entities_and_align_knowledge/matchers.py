"""Matcher facade exports for Phase 3 standardization."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.precise_match.core import (
    ALIAS_TYPE_PRIORITY,
    PreciseTerminologyMatcher,
)

TerminologyMatcher = PreciseTerminologyMatcher

__all__ = ["ALIAS_TYPE_PRIORITY", "PreciseTerminologyMatcher", "TerminologyMatcher"]
