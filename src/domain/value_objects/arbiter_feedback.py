"""Arbiter feedback value object for structured PS3 evaluation."""

from typing import Any, Dict, List, Optional


class DimensionScore:
    """Score for a single PS3 evaluation dimension."""

    def __init__(
        self,
        name: str,
        score: float,
        max_score: float,
        status: str,  # "pass", "fail", "partial", "na"
        reason: str,
        suggestions: Optional[List[str]] = None,
    ):
        """Initialize dimension score.
        
        Args:
            name: Dimension name (e.g., "disease_mechanism", "method_suitability")
            score: Current score for this dimension
            max_score: Maximum possible score for this dimension
            status: Pass/Fail/Partial/Not Applicable
            reason: Explanation of the score
            suggestions: List of improvement suggestions
        """
        self.name = name
        self.score = score
        self.max_score = max_score
        self.status = status
        self.reason = reason
        self.suggestions = suggestions or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "max_score": self.max_score,
            "status": self.status,
            "reason": self.reason,
            "suggestions": self.suggestions,
        }


class ArbiterFeedback:
    """Structured feedback from arbiter evaluation."""

    def __init__(
        self,
        overall_score: float,
        max_score: float = 100.0,
        dimensions: Optional[List[DimensionScore]] = None,
        key_issues: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
        should_iterate: bool = False,
    ):
        """Initialize arbiter feedback.
        
        Args:
            overall_score: Overall quality score (0-100)
            max_score: Maximum possible score
            dimensions: List of dimension scores (disease_mechanism, method_suitability, etc.)
            key_issues: Top issues found in evidence extraction
            recommendations: Specific recommendations for improvement
            should_iterate: Whether extraction should be re-attempted
        """
        self.overall_score = overall_score
        self.max_score = max_score
        self.dimensions = dimensions or []
        self.key_issues = key_issues or []
        self.recommendations = recommendations or []
        self.should_iterate = should_iterate

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
            "key_issues": self.key_issues,
            "recommendations": self.recommendations,
            "should_iterate": self.should_iterate,
        }
