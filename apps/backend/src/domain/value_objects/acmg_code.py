"""ACMG Code value object.

Immutable value object representing ACMG evidence classification codes.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class ACMGCodeEnum(str, Enum):
    """ACMG evidence codes as per ACMG/AMP 2015 guidelines."""

    # Pathogenic Strong (PS)
    PS1 = "PS1"  # Same amino acid change as established pathogenic variant
    PS2 = "PS2"  # De novo in patient with disease and no family history
    PS3 = "PS3"  # Well-established functional studies supportive of damaging effect
    PS4 = "PS4"  # Prevalence in affected significantly increased vs controls

    # Pathogenic Moderate (PM)
    PM1 = "PM1"  # Located in mutational hot spot and/or critical functional domain
    PM2 = "PM2"  # Absent from controls or extremely low frequency
    PM3 = "PM3"  # Detected in trans with pathogenic variant for recessive disorder
    PM4 = "PM4"  # Protein length changes due to in-frame deletions/insertions
    PM5 = "PM5"  # Novel missense change at amino acid residue where different change is pathogenic
    PM6 = "PM6"  # Assumed de novo, but without confirmation of paternity and maternity

    # Pathogenic Supporting (PP)
    PP1 = "PP1"  # Cosegregation with disease in multiple affected family members
    PP2 = "PP2"  # Missense variant in gene with low rate of benign missense variation
    PP3 = "PP3"  # Multiple lines of computational evidence support deleterious effect
    PP4 = "PP4"  # Patient's phenotype or family history highly specific for gene
    PP5 = "PP5"  # Reputable source recently reports variant as pathogenic

    # Benign Stand-alone (BA)
    BA1 = "BA1"  # Allele frequency >5% in population database

    # Benign Strong (BS)
    BS1 = "BS1"  # Allele frequency greater than expected for disorder
    BS2 = "BS2"  # Observed in healthy adult for recessive/dominant disorder
    BS3 = "BS3"  # Well-established functional studies show no damaging effect
    BS4 = "BS4"  # Lack of segregation in affected members of family

    # Benign Supporting (BP)
    BP1 = "BP1"  # Missense variant in gene where primarily truncating cause disease
    BP2 = "BP2"  # Observed in trans with pathogenic variant for dominant disorder
    BP3 = "BP3"  # In-frame deletions/insertions in repetitive region
    BP4 = "BP4"  # Multiple lines of computational evidence suggest no impact
    BP5 = "BP5"  # Variant found in case with alternate molecular basis for disease
    BP6 = "BP6"  # Reputable source recently reports variant as benign
    BP7 = "BP7"  # Silent variant with no predicted impact on splicing


@dataclass(frozen=True)
class ACMGCode:
    """Immutable ACMG evidence code value object.

    Encapsulates ACMG evidence classification with validation
    and domain-specific operations.
    """

    code: ACMGCodeEnum

    # Code descriptions
    DESCRIPTIONS: Dict[ACMGCodeEnum, str] = {
        ACMGCodeEnum.PS1: "Same amino acid change as established pathogenic variant",
        ACMGCodeEnum.PS2: "De novo in patient with disease and no family history",
        ACMGCodeEnum.PS3: "Well-established functional studies supportive of damaging effect",
        ACMGCodeEnum.PS4: "Prevalence in affected significantly increased vs controls",
        ACMGCodeEnum.PM1: "Located in mutational hot spot/critical functional domain",
        ACMGCodeEnum.PM2: "Absent from controls or extremely low frequency",
        ACMGCodeEnum.PM3: "Detected in trans with pathogenic variant",
        ACMGCodeEnum.PM4: "Protein length changes due to in-frame indels",
        ACMGCodeEnum.PM5: "Novel missense at residue where different change is pathogenic",
        ACMGCodeEnum.PM6: "Assumed de novo, but without confirmation",
        ACMGCodeEnum.PP1: "Cosegregation with disease in multiple affected members",
        ACMGCodeEnum.PP2: "Missense in gene with low benign missense variation",
        ACMGCodeEnum.PP3: "Multiple computational evidence support deleterious effect",
        ACMGCodeEnum.PP4: "Phenotype or family history highly specific for gene",
        ACMGCodeEnum.PP5: "Reputable source recently reports as pathogenic",
        ACMGCodeEnum.BA1: "Allele frequency >5% in population database",
        ACMGCodeEnum.BS1: "Allele frequency greater than expected for disorder",
        ACMGCodeEnum.BS2: "Observed in healthy adult",
        ACMGCodeEnum.BS3: "Well-established functional studies show no damaging effect",
        ACMGCodeEnum.BS4: "Lack of segregation in affected family members",
        ACMGCodeEnum.BP1: "Missense in gene where primarily truncating cause disease",
        ACMGCodeEnum.BP2: "Observed in trans with pathogenic variant",
        ACMGCodeEnum.BP3: "In-frame indels in repetitive region",
        ACMGCodeEnum.BP4: "Multiple computational evidence suggest no impact",
        ACMGCodeEnum.BP5: "Variant found in case with alternate molecular basis",
        ACMGCodeEnum.BP6: "Reputable source recently reports as benign",
        ACMGCodeEnum.BP7: "Silent variant with no predicted splicing impact",
    }

    @classmethod
    def from_string(cls, code_str: str) -> "ACMGCode":
        """Create ACMG code from string."""
        try:
            code_enum = ACMGCodeEnum(code_str.upper())
            return cls(code_enum)
        except ValueError:
            raise ValueError(f"Invalid ACMG code: {code_str}")

    def is_pathogenic(self) -> bool:
        """Check if code indicates pathogenicity."""
        return self.code.value.startswith(("PS", "PM", "PP"))

    def is_benign(self) -> bool:
        """Check if code indicates benign variant."""
        return self.code.value.startswith(("BA", "BS", "BP"))

    def get_strength(self) -> str:
        """Get evidence strength level."""
        code_value = self.code.value
        if code_value.startswith("PS") or code_value.startswith("BS") or code_value == "BA1":
            return "STRONG"
        elif code_value.startswith("PM"):
            return "MODERATE"
        elif code_value.startswith("PP") or code_value.startswith("BP"):
            return "SUPPORTING"
        return "UNKNOWN"

    def get_description(self) -> str:
        """Get human-readable description of code."""
        return self.DESCRIPTIONS.get(
            self.code, "No description available"
        )

    def get_category(self) -> str:
        """Get evidence category (Pathogenic or Benign)."""
        return "PATHOGENIC" if self.is_pathogenic() else "BENIGN"

    @staticmethod
    def get_pathogenic_codes() -> List[ACMGCodeEnum]:
        """Get all pathogenic evidence codes."""
        return [code for code in ACMGCodeEnum if code.value.startswith(("PS", "PM", "PP"))]

    @staticmethod
    def get_benign_codes() -> List[ACMGCodeEnum]:
        """Get all benign evidence codes."""
        return [code for code in ACMGCodeEnum if code.value.startswith(("BA", "BS", "BP"))]

    @staticmethod
    def get_strong_codes() -> List[ACMGCodeEnum]:
        """Get all strong evidence codes."""
        return [
            code
            for code in ACMGCodeEnum
            if code.value.startswith(("PS", "BS")) or code.value == "BA1"
        ]

    def __str__(self) -> str:
        """String representation."""
        return self.code.value

    def __repr__(self) -> str:
        """Developer representation."""
        return f"ACMGCode({self.code.value})"

    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if isinstance(other, ACMGCode):
            return self.code == other.code
        if isinstance(other, ACMGCodeEnum):
            return self.code == other
        if isinstance(other, str):
            return self.code.value == other.upper()
        return NotImplemented

    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash(self.code)
