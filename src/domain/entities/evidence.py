"""Evidence entity."""

from typing import Any, Dict, List, Optional

from ..value_objects import OddsPath


class Evidence:
    """Functional assay evidence entity for PS3 classification."""

    def __init__(
        self,
        findings: List[str],
        p1: float,
        p2: float,
        rationale: str,
        experimental_details: str = "",
        p1_source_location: str = "",
        p2_source_location: str = "",
        ps3_criteria_met: bool = False,
        control_variants_count: int = 0,
        odds_path_computable: bool = True,
        reason_if_not_applicable: str = "",
    ):
        """Initialize evidence.

        Args:
            findings: List of extracted evidence spans from paper
            p1: Prior probability of pathogenicity
            p2: Posterior probability based on functional assay
            rationale: Explanation of evidence interpretation
            experimental_details: Description of functional assay
            p1_source_location: Source location text for P1
            p2_source_location: Source location text for P2
            ps3_criteria_met: Whether PS3 conditions are met
        """
        self.findings = findings
        self.odds_path = OddsPath(p1, p2)
        self.rationale = rationale
        self.experimental_details = experimental_details
        self.p1_source_location = p1_source_location
        self.p2_source_location = p2_source_location
        self.ps3_criteria_met = ps3_criteria_met
        self.control_variants_count = control_variants_count
        self.odds_path_computable = odds_path_computable
        self.reason_if_not_applicable = reason_if_not_applicable
        self.arbiter_score: Optional[float] = None

    @property
    def strength(self):
        """Get evidence strength classification."""
        return self.odds_path.strength

    @property
    def p1(self) -> float:
        """Get prior probability."""
        return self.odds_path.p1

    @property
    def p2(self) -> float:
        """Get posterior probability."""
        return self.odds_path.p2

    @property
    def odds_path_value(self) -> float:
        """Get OddsPath numerical value."""
        return self.odds_path.value

    def to_dict(self) -> Dict[str, Any]:
        """Convert evidence to dictionary."""
        return {
            "findings": self.findings,
            "p1": self.p1,
            "p2": self.p2,
            "odds_path": self.odds_path_value,
            "strength": self.strength.value,
            "rationale": self.rationale,
            "experimental_details": self.experimental_details,
            "p1_source_location": self.p1_source_location,
            "p2_source_location": self.p2_source_location,
            "ps3_criteria_met": self.ps3_criteria_met,
            "control_variants_count": self.control_variants_count,
            "odds_path_computable": self.odds_path_computable,
            "reason_if_not_applicable": self.reason_if_not_applicable,
            "arbiter_score": self.arbiter_score,
        }
