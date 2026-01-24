"""Evidence strength value object."""

from enum import Enum


class EvidenceStrength(str, Enum):
    """Evidence strength levels based on OddsPath thresholds."""

    INDETERMINATE = "indeterminate"
    SUPPORTING = "supporting"  # OddsPath >= 2
    MODERATE = "moderate"  # OddsPath >= 4.3
    STRONG = "strong"  # OddsPath >= 18
    VERY_STRONG = "very-strong"  # OddsPath >= 350
