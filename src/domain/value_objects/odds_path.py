"""OddsPath value object for evidence strength calculation."""

from enum import Enum


class EvidenceStrength(str, Enum):
    """Evidence strength levels based on OddsPath thresholds."""

    INDETERMINATE = "indeterminate"
    SUPPORTING = "supporting"  # OddsPath >= 2
    MODERATE = "moderate"  # OddsPath >= 4.3
    STRONG = "strong"  # OddsPath >= 18
    VERY_STRONG = "very-strong"  # OddsPath >= 350


class OddsPath:
    """OddsPath value object for evidence strength calculation.

    Per ACMG/SVI guidance:
    OddsPath = [P2 * (1 - P1)] / [(1 - P2) * P1]
    where P1 = prior probability, P2 = posterior probability
    """

    SUPPORTING_THRESHOLD = 2.0
    MODERATE_THRESHOLD = 4.3
    STRONG_THRESHOLD = 18.0
    VERY_STRONG_THRESHOLD = 350.0

    def __init__(self, p1: float, p2: float):
        """Initialize OddsPath with prior and posterior probabilities.

        Args:
            p1: Prior probability (0 < p1 < 1)
            p2: Posterior probability (0 < p2 < 1)

        Raises:
            ValueError: If probabilities are not in valid range
        """
        if not (0 < p1 < 1):
            raise ValueError(f"P1 must be in (0, 1), got {p1}")
        if not (0 < p2 < 1):
            raise ValueError(f"P2 must be in (0, 1), got {p2}")

        self.p1 = p1
        self.p2 = p2
        self._value = self._compute()

    def _compute(self) -> float:
        """Compute OddsPath value."""
        return (self.p2 * (1 - self.p1)) / ((1 - self.p2) * self.p1)

    @property
    def value(self) -> float:
        """Get computed OddsPath value."""
        return self._value

    @property
    def strength(self) -> EvidenceStrength:
        """Classify evidence strength based on OddsPath value."""
        if self._value >= self.VERY_STRONG_THRESHOLD:
            return EvidenceStrength.VERY_STRONG
        if self._value >= self.STRONG_THRESHOLD:
            return EvidenceStrength.STRONG
        if self._value >= self.MODERATE_THRESHOLD:
            return EvidenceStrength.MODERATE
        if self._value >= self.SUPPORTING_THRESHOLD:
            return EvidenceStrength.SUPPORTING
        return EvidenceStrength.INDETERMINATE

    def __str__(self) -> str:
        return f"OddsPath({self._value:.4f})"

    def __repr__(self) -> str:
        return f"OddsPath(p1={self.p1}, p2={self.p2}, value={self._value:.4f})"
