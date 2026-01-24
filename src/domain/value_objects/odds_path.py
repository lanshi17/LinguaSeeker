"""OddsPath value object for evidence strength calculation."""

from enum import Enum
from dataclasses import dataclass


class EvidenceStrength(str, Enum):
    """Evidence strength levels based on OddsPath thresholds."""

    INDETERMINATE = "indeterminate"
    SUPPORTING = "supporting"  # OddsPath >= 2
    MODERATE = "moderate"  # OddsPath >= 4.3
    STRONG = "strong"  # OddsPath >= 18
    VERY_STRONG = "very-strong"  # OddsPath >= 350


@dataclass(frozen=True)
class OddsPath:
    """OddsPath value object for evidence strength calculation (immutable).

    Per ACMG/SVI guidance:
    OddsPath = [P2 * (1 - P1)] / [(1 - P2) * P1]
    where P1 = prior probability, P2 = posterior probability
    """

    p1: float
    p2: float

    SUPPORTING_THRESHOLD = 2.0
    MODERATE_THRESHOLD = 4.3
    STRONG_THRESHOLD = 18.0
    VERY_STRONG_THRESHOLD = 350.0

    def __post_init__(self):
        """Validate probabilities are in valid range.

        Raises:
            ValueError: If probabilities are not in valid range
        """
        if not (0 < self.p1 < 1):
            raise ValueError(f"P1 must be in (0, 1), got {self.p1}")
        if not (0 < self.p2 < 1):
            raise ValueError(f"P2 must be in (0, 1), got {self.p2}")

    @property
    def value(self) -> float:
        """Get computed OddsPath value."""
        return (self.p2 * (1 - self.p1)) / ((1 - self.p2) * self.p1)

    @property
    def strength(self) -> EvidenceStrength:
        """Classify evidence strength based on OddsPath value."""
        val = self.value
        if val >= self.VERY_STRONG_THRESHOLD:
            return EvidenceStrength.VERY_STRONG
        if val >= self.STRONG_THRESHOLD:
            return EvidenceStrength.STRONG
        if val >= self.MODERATE_THRESHOLD:
            return EvidenceStrength.MODERATE
        if val >= self.SUPPORTING_THRESHOLD:
            return EvidenceStrength.SUPPORTING
        return EvidenceStrength.INDETERMINATE

    def __str__(self) -> str:
        return f"OddsPath({self.value:.4f})"

    def __repr__(self) -> str:
        return f"OddsPath(p1={self.p1}, p2={self.p2}, value={self.value:.4f})"
