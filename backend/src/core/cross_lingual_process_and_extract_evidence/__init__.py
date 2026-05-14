"""Cross-lingual processing and evidence extraction module."""
from .contracts import CrossLingualOutput, PipelineState, TranslationResult
from .persistence import DocumentPersistenceService
from .workflow import TranslationService

__all__ = [
    "CrossLingualOutput",
    "DocumentPersistenceService",
    "PipelineState",
    "TranslationResult",
    "TranslationService",
]
