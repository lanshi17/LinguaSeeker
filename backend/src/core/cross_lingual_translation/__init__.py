"""Cross-lingual translation feature slice.

Provides document formatting, language detection, multi-stage LLM translation,
and persistence for the Phase 2 cross-lingual pipeline.
"""

from .api import TranslationService
from .contracts import (
    CrossLingualOutput,
    PipelineState,
    TranslationAlignmentChunk,
    TranslationResult,
)
from .persistence import DocumentPersistenceService

__all__ = [
    "CrossLingualOutput",
    "DocumentPersistenceService",
    "PipelineState",
    "TranslationAlignmentChunk",
    "TranslationResult",
    "TranslationService",
]
