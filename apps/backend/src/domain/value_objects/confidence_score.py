"""Confidence Score value object.

Immutable value object representing evidence confidence score with validation.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Union


@dataclass(frozen=True)
class ConfidenceScore:
    """Immutable confidence score value object.

    Represents a confidence score between 0.00 and 1.00 with two decimal places.
    Enforces validation rules and provides domain-specific operations.
    """

    value: Decimal

    # Threshold for high confidence (auto-acceptance)
    HIGH_CONFIDENCE_THRESHOLD: Decimal = Decimal("0.85")

    def __post_init__(self) -> None:
        """Validate confidence score value."""
        # Ensure value is Decimal
        if not isinstance(self.value, Decimal):
            object.__setattr__(
                self, "value", Decimal(str(self.value)).quantize(Decimal("0.01"))
            )

        # Validate range
        if not (Decimal("0.00") <= self.value <= Decimal("1.00")):
            raise ValueError(
                f"Confidence score {self.value} must be between 0.00 and 1.00"
            )

        # Ensure two decimal places
        quantized = self.value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        object.__setattr__(self, "value", quantized)

    @classmethod
    def from_float(cls, value: float) -> "ConfidenceScore":
        """Create confidence score from float."""
        return cls(Decimal(str(value)))

    @classmethod
    def from_percentage(cls, percentage: Union[int, float]) -> "ConfidenceScore":
        """Create confidence score from percentage (0-100)."""
        if not (0 <= percentage <= 100):
            raise ValueError(f"Percentage {percentage} must be between 0 and 100")
        return cls(Decimal(str(percentage / 100)))

    def is_high_confidence(self) -> bool:
        """Check if score meets high confidence threshold."""
        return self.value >= self.HIGH_CONFIDENCE_THRESHOLD

    def requires_review(self) -> bool:
        """Check if score requires human review."""
        return self.value < self.HIGH_CONFIDENCE_THRESHOLD

    def to_float(self) -> float:
        """Convert to float."""
        return float(self.value)

    def to_percentage(self) -> int:
        """Convert to percentage (0-100)."""
        return int(self.value * 100)

    def __str__(self) -> str:
        """String representation."""
        return str(self.value)

    def __repr__(self) -> str:
        """Developer representation."""
        return f"ConfidenceScore({self.value})"

    def __float__(self) -> float:
        """Float conversion."""
        return self.to_float()

    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if isinstance(other, ConfidenceScore):
            return self.value == other.value
        if isinstance(other, (Decimal, float, int)):
            return self.value == Decimal(str(other))
        return NotImplemented

    def __lt__(self, other: Union["ConfidenceScore", Decimal, float]) -> bool:
        """Less than comparison."""
        if isinstance(other, ConfidenceScore):
            return self.value < other.value
        return self.value < Decimal(str(other))

    def __le__(self, other: Union["ConfidenceScore", Decimal, float]) -> bool:
        """Less than or equal comparison."""
        if isinstance(other, ConfidenceScore):
            return self.value <= other.value
        return self.value <= Decimal(str(other))

    def __gt__(self, other: Union["ConfidenceScore", Decimal, float]) -> bool:
        """Greater than comparison."""
        if isinstance(other, ConfidenceScore):
            return self.value > other.value
        return self.value > Decimal(str(other))

    def __ge__(self, other: Union["ConfidenceScore", Decimal, float]) -> bool:
        """Greater than or equal comparison."""
        if isinstance(other, ConfidenceScore):
            return self.value >= other.value
        return self.value >= Decimal(str(other))

    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash(self.value)
