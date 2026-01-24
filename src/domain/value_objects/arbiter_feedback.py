"""Arbiter feedback value object for structured PS3 evaluation."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DimensionScore:
    """Score for a single PS3 evaluation dimension (immutable)."""

    name: str
    score: float
    max_score: float
    status: str  # "pass", "fail", "partial", "na"
    reason: str
    suggestions: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "max_score": self.max_score,
            "status": self.status,
            "reason": self.reason,
            "suggestions": list(self.suggestions),
        }


@dataclass(frozen=True)
class ArbiterFeedback:
    """Structured feedback from arbiter evaluation (immutable)."""

    overall_score: float
    max_score: float = 100.0
    dimensions: tuple[DimensionScore, ...] = field(default_factory=tuple)
    key_issues: tuple[str, ...] = field(default_factory=tuple)
    recommendations: tuple[str, ...] = field(default_factory=tuple)
    should_iterate: bool = False

    def get_dimension(self, name: str) -> Optional[DimensionScore]:
        """Get dimension score by name."""
        for dim in self.dimensions:
            if dim.name == name:
                return dim
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "max_score": self.max_score,
            "normalized_score": (self.overall_score / self.max_score * 100) if self.max_score > 0 else 0,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "key_issues": list(self.key_issues),
            "recommendations": list(self.recommendations),
            "should_iterate": self.should_iterate,
        }
