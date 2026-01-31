"""Evidence Item domain entity.

Represents a single ACMG criterion extracted from a document.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class ACMGCode(str, Enum):
    """ACMG evidence codes."""

    # Pathogenic Strong
    PS1 = "PS1"
    PS2 = "PS2"
    PS3 = "PS3"
    PS4 = "PS4"
    # Pathogenic Moderate
    PM1 = "PM1"
    PM2 = "PM2"
    PM3 = "PM3"
    PM4 = "PM4"
    PM5 = "PM5"
    PM6 = "PM6"
    # Pathogenic Supporting
    PP1 = "PP1"
    PP2 = "PP2"
    PP3 = "PP3"
    PP4 = "PP4"
    PP5 = "PP5"
    # Benign Stand-alone
    BA1 = "BA1"
    # Benign Strong
    BS1 = "BS1"
    BS2 = "BS2"
    BS3 = "BS3"
    BS4 = "BS4"
    # Benign Supporting
    BP1 = "BP1"
    BP2 = "BP2"
    BP3 = "BP3"
    BP4 = "BP4"
    BP5 = "BP5"
    BP6 = "BP6"
    BP7 = "BP7"


@dataclass
class BoundingBox:
    """Source location bounding box."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        """Validate bounding box."""
        if self.x < 0 or self.y < 0:
            raise ValueError("Bounding box coordinates must be non-negative")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Bounding box dimensions must be positive")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class EvidenceItem:
    """Domain entity representing an ACMG evidence criterion.

    Encapsulates business logic for evidence extraction, validation,
    and human review workflows.
    """

    # Required confidence threshold for auto-acceptance
    CONFIDENCE_THRESHOLD: float = field(default=0.85, init=False, repr=False)

    id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    acmg_code: ACMGCode = ACMGCode.PP1
    confidence_score: Decimal = Decimal("0.00")
    source_page: int = 1
    bounding_box: BoundingBox = field(default_factory=lambda: BoundingBox(0, 0, 1, 1))
    source_hash: str = ""
    supporting_text: str = ""
    review_required: bool = False
    human_reviewed: bool = False
    human_notes: Optional[str] = None
    variant_id: Optional[UUID] = None
    extracted_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate evidence item after initialization."""
        self._validate()
        self._set_review_flag()

    def _validate(self) -> None:
        """Validate evidence item invariants."""
        if not (Decimal("0.00") <= self.confidence_score <= Decimal("1.00")):
            raise ValueError(
                f"Confidence score {self.confidence_score} must be between 0.00 and 1.00"
            )

        if self.source_page < 1:
            raise ValueError(f"Source page {self.source_page} must be positive")

        if len(self.source_hash) != 64:
            raise ValueError("Source hash must be SHA256 (64 characters)")

        if not self.supporting_text:
            raise ValueError("Supporting text is required")

    def _set_review_flag(self) -> None:
        """Automatically set review_required flag based on confidence score."""
        self.review_required = float(self.confidence_score) < self.CONFIDENCE_THRESHOLD

    def needs_review(self) -> bool:
        """Check if evidence item requires human review."""
        return self.review_required and not self.human_reviewed

    def is_high_confidence(self) -> bool:
        """Check if evidence has high confidence (≥ threshold)."""
        return float(self.confidence_score) >= self.CONFIDENCE_THRESHOLD

    def approve(self, reviewer_notes: Optional[str] = None) -> None:
        """Mark evidence as human-reviewed and approved."""
        if self.human_reviewed:
            raise ValueError("Evidence item already reviewed")

        self.human_reviewed = True
        self.review_required = False
        if reviewer_notes:
            self.human_notes = reviewer_notes
        self.updated_at = datetime.utcnow()

    def reject(self, reason: str) -> None:
        """Reject evidence item with reason."""
        if not reason:
            raise ValueError("Rejection reason is required")

        self.human_reviewed = True
        self.review_required = False
        self.human_notes = f"REJECTED: {reason}"
        self.updated_at = datetime.utcnow()

    def update_confidence(self, new_score: Decimal) -> None:
        """Update confidence score and review flag."""
        if not (Decimal("0.00") <= new_score <= Decimal("1.00")):
            raise ValueError(
                f"Confidence score {new_score} must be between 0.00 and 1.00"
            )

        self.confidence_score = new_score
        self._set_review_flag()
        self.updated_at = datetime.utcnow()

    def link_variant(self, variant_id: UUID) -> None:
        """Link evidence to a genetic variant."""
        self.variant_id = variant_id
        self.updated_at = datetime.utcnow()

    def unlink_variant(self) -> None:
        """Remove variant linkage."""
        self.variant_id = None
        self.updated_at = datetime.utcnow()

    def is_pathogenic(self) -> bool:
        """Check if evidence code indicates pathogenicity."""
        return self.acmg_code.value.startswith(("PS", "PM", "PP"))

    def is_benign(self) -> bool:
        """Check if evidence code indicates benign variant."""
        return self.acmg_code.value.startswith(("BA", "BS", "BP"))

    def get_strength(self) -> str:
        """Get evidence strength level."""
        code = self.acmg_code.value
        if code.startswith("PS") or code.startswith("BS") or code == "BA1":
            return "STRONG"
        elif code.startswith("PM"):
            return "MODERATE"
        elif code.startswith("PP") or code.startswith("BP"):
            return "SUPPORTING"
        return "UNKNOWN"

    def __repr__(self) -> str:
        """String representation of evidence item."""
        return (
            f"EvidenceItem(id={self.id}, code={self.acmg_code}, "
            f"confidence={self.confidence_score}, needs_review={self.needs_review()})"
        )
