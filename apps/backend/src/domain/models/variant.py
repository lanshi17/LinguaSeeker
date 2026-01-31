"""Variant domain entity.

Represents a genetic variant with pathogenicity classification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class PathogenicityClassification(str, Enum):
    """Variant pathogenicity classification per ACMG guidelines."""

    BENIGN = "BENIGN"
    LIKELY_BENIGN = "LIKELY_BENIGN"
    VUS = "VUS"  # Variant of Uncertain Significance
    LIKELY_PATHOGENIC = "LIKELY_PATHOGENIC"
    PATHOGENIC = "PATHOGENIC"
    CONFLICTING = "CONFLICTING"


@dataclass
class Variant:
    """Domain entity representing a genetic variant.

    Aggregates evidence from multiple documents to determine
    pathogenicity classification.
    """

    id: UUID = field(default_factory=uuid4)
    hgvs_notation: str = ""
    gene: str = ""
    chromosome: str = ""
    position: int = 0
    reference_allele: str = ""
    alternate_allele: str = ""
    pathogenicity_classification: PathogenicityClassification = (
        PathogenicityClassification.VUS
    )
    aggregated_confidence: Decimal = Decimal("0.00")
    evidence_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate variant after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate variant invariants."""
        if not self.hgvs_notation:
            raise ValueError("HGVS notation is required")

        if not self.gene:
            raise ValueError("Gene symbol is required")

        if not self.chromosome:
            raise ValueError("Chromosome is required")

        if self.position < 0:
            raise ValueError("Position must be non-negative")

        if not (Decimal("0.00") <= self.aggregated_confidence <= Decimal("1.00")):
            raise ValueError(
                f"Aggregated confidence {self.aggregated_confidence} must be between 0.00 and 1.00"
            )

        if self.evidence_count < 0:
            raise ValueError("Evidence count must be non-negative")

    def add_evidence(self) -> None:
        """Increment evidence count."""
        self.evidence_count += 1
        self.updated_at = datetime.utcnow()

    def remove_evidence(self) -> None:
        """Decrement evidence count."""
        if self.evidence_count > 0:
            self.evidence_count -= 1
            self.updated_at = datetime.utcnow()

    def update_classification(
        self,
        classification: PathogenicityClassification,
        confidence: Decimal,
    ) -> None:
        """Update pathogenicity classification and confidence."""
        if not (Decimal("0.00") <= confidence <= Decimal("1.00")):
            raise ValueError(
                f"Confidence {confidence} must be between 0.00 and 1.00"
            )

        self.pathogenicity_classification = classification
        self.aggregated_confidence = confidence
        self.updated_at = datetime.utcnow()

    def is_pathogenic(self) -> bool:
        """Check if variant is classified as pathogenic."""
        return self.pathogenicity_classification in [
            PathogenicityClassification.PATHOGENIC,
            PathogenicityClassification.LIKELY_PATHOGENIC,
        ]

    def is_benign(self) -> bool:
        """Check if variant is classified as benign."""
        return self.pathogenicity_classification in [
            PathogenicityClassification.BENIGN,
            PathogenicityClassification.LIKELY_BENIGN,
        ]

    def is_vus(self) -> bool:
        """Check if variant is of uncertain significance."""
        return self.pathogenicity_classification == PathogenicityClassification.VUS

    def has_conflicting_evidence(self) -> bool:
        """Check if variant has conflicting evidence."""
        return self.pathogenicity_classification == PathogenicityClassification.CONFLICTING

    def has_sufficient_evidence(self, min_evidence: int = 2) -> bool:
        """Check if variant has sufficient supporting evidence."""
        return self.evidence_count >= min_evidence

    def get_location_string(self) -> str:
        """Get human-readable location string."""
        return f"{self.chromosome}:{self.position}"

    def get_change_string(self) -> str:
        """Get allele change string."""
        return f"{self.reference_allele}>{self.alternate_allele}"

    def __repr__(self) -> str:
        """String representation of variant."""
        return (
            f"Variant(id={self.id}, hgvs='{self.hgvs_notation}', "
            f"gene={self.gene}, classification={self.pathogenicity_classification})"
        )
