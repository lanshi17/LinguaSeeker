"""Translation Pair domain entity.

Represents aligned English-Chinese text pairs from document translation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class TranslationPair:
    """Domain entity representing a bilingual translation pair.

    Encapsulates business logic for maintaining paragraph-level alignment
    between source and target languages in biomedical documents.
    """

    id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    source_text: str = ""
    target_text: str = ""
    source_language: str = "EN"  # EN or ZH
    target_language: str = "ZH"  # EN or ZH
    confidence_score: float = 0.0
    paragraph_index: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate translation pair after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate translation pair invariants."""
        if not self.source_text:
            raise ValueError("Source text is required")

        if not self.target_text:
            raise ValueError("Target text is required")

        if self.confidence_score < 0.0 or self.confidence_score > 1.0:
            raise ValueError(
                f"Confidence score {self.confidence_score} must be between 0.0 and 1.0"
            )

        if self.paragraph_index < 0:
            raise ValueError(f"Paragraph index {self.paragraph_index} must be non-negative")

        if self.source_language not in ["EN", "ZH"]:
            raise ValueError(f"Invalid source language: {self.source_language}")

        if self.target_language not in ["EN", "ZH"]:
            raise ValueError(f"Invalid target language: {self.target_language}")

        if self.source_language == self.target_language:
            raise ValueError("Source and target languages must be different")

    def is_high_confidence(self, threshold: float = 0.85) -> bool:
        """Check if translation has high confidence.

        Args:
            threshold: Confidence threshold (default 0.85)

        Returns:
            True if confidence >= threshold
        """
        return self.confidence_score >= threshold

    def swap_languages(self) -> None:
        """Swap source and target languages and texts."""
        self.source_text, self.target_text = self.target_text, self.source_text
        self.source_language, self.target_language = self.target_language, self.source_language
        self.updated_at = datetime.utcnow()

    def update_translation(self, new_target_text: str, new_confidence: float) -> None:
        """Update target text and confidence score.

        Args:
            new_target_text: New target translation
            new_confidence: New confidence score
        """
        if not new_target_text:
            raise ValueError("Target text cannot be empty")

        if new_confidence < 0.0 or new_confidence > 1.0:
            raise ValueError(
                f"Confidence score {new_confidence} must be between 0.0 and 1.0"
            )

        self.target_text = new_target_text
        self.confidence_score = new_confidence
        self.updated_at = datetime.utcnow()

    def get_aligned_pair(self) -> dict:
        """Get aligned translation pair as dictionary.

        Returns:
            Dictionary with source and target texts
        """
        return {
            "source": {
                "text": self.source_text,
                "language": self.source_language
            },
            "target": {
                "text": self.target_text,
                "language": self.target_language
            },
            "confidence": self.confidence_score,
            "paragraph_index": self.paragraph_index
        }

    def __repr__(self) -> str:
        """String representation of translation pair."""
        return (
            f"TranslationPair(id={self.id}, "
            f"source_lang={self.source_language}, "
            f"target_lang={self.target_language}, "
            f"confidence={self.confidence_score:.2f})"
        )