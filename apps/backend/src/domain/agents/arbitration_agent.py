"""Arbitration Agent for confidence scoring.

Evaluates extracted evidence and assigns confidence scores with review flags.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from decimal import Decimal

from src.domain.agents.evidence_agent import ExtractedEvidence
from src.domain.value_objects.confidence_score import ConfidenceScore


@dataclass
class ArbitrationResult:
    """Arbitration result with final confidence."""

    evidence: ExtractedEvidence
    final_confidence: Decimal
    review_required: bool
    arbitration_notes: str


class ArbitrationAgent:
    """Agent for evidence confidence scoring and arbitration.

    Responsibilities:
    - Evaluate evidence quality
    - Assign confidence scores (0.00-1.00)
    - Flag low-confidence items for review (< 0.85)
    - Provide arbitration reasoning
    """

    # Confidence threshold for auto-acceptance
    CONFIDENCE_THRESHOLD = 0.85

    def __init__(self):
        """Initialize arbitration agent."""
        pass

    async def process(
        self, evidence_list: List[ExtractedEvidence]
    ) -> List[ArbitrationResult]:
        """Arbitrate extracted evidence.

        Args:
            evidence_list: List of extracted evidence items

        Returns:
            List of arbitration results with confidence scores
        """
        results = []

        for evidence in evidence_list:
            # Calculate confidence
            confidence = await self._calculate_confidence(evidence)

            # Determine review requirement
            review_required = confidence < Decimal(str(self.CONFIDENCE_THRESHOLD))

            # Generate notes
            notes = self._generate_notes(evidence, confidence, review_required)

            results.append(
                ArbitrationResult(
                    evidence=evidence,
                    final_confidence=confidence,
                    review_required=review_required,
                    arbitration_notes=notes,
                )
            )

        return results

    async def _calculate_confidence(self, evidence: ExtractedEvidence) -> Decimal:
        """Calculate confidence score for evidence.

        Args:
            evidence: Extracted evidence

        Returns:
            Confidence score (0.00-1.00)
        """
        # Start with extraction confidence
        base_score = evidence.confidence

        # Adjust based on supporting text quality
        text_quality = self._assess_text_quality(evidence.supporting_text)

        # Adjust based on ACMG code
        code_factor = self._get_code_confidence_factor(evidence.acmg_code)

        # Combine factors
        final_score = base_score * text_quality * code_factor

        # Clamp to [0, 1]
        final_score = max(0.0, min(1.0, final_score))

        return Decimal(str(round(final_score, 2)))

    def _assess_text_quality(self, text: str) -> float:
        """Assess quality of supporting text.

        Args:
            text: Supporting text

        Returns:
            Quality factor (0.0-1.0)
        """
        # Basic heuristics
        if len(text) < 20:
            return 0.5  # Too short

        if len(text) > 500:
            return 0.9  # Comprehensive

        # Check for key indicators
        has_numbers = any(c.isdigit() for c in text)
        has_references = "et al" in text.lower() or "ref" in text.lower()

        quality = 0.7
        if has_numbers:
            quality += 0.1
        if has_references:
            quality += 0.1

        return min(1.0, quality)

    def _get_code_confidence_factor(self, code: str) -> float:
        """Get confidence adjustment factor for ACMG code.

        Args:
            code: ACMG code

        Returns:
            Confidence factor
        """
        # Strong evidence codes get higher confidence
        if code.startswith("PS") or code.startswith("BS"):
            return 1.0

        # Moderate evidence
        if code.startswith("PM"):
            return 0.95

        # Supporting evidence
        if code.startswith("PP") or code.startswith("BP"):
            return 0.9

        # Unknown/stand-alone
        return 0.85

    def _generate_notes(
        self,
        evidence: ExtractedEvidence,
        confidence: Decimal,
        review_required: bool,
    ) -> str:
        """Generate arbitration notes.

        Args:
            evidence: Evidence item
            confidence: Final confidence score
            review_required: Whether review is required

        Returns:
            Arbitration notes
        """
        notes_parts = [
            f"Confidence: {confidence}",
            f"Code: {evidence.acmg_code}",
        ]

        if review_required:
            notes_parts.append("⚠️ REVIEW REQUIRED (confidence < 0.85)")
        else:
            notes_parts.append("✓ Auto-accepted (high confidence)")

        if evidence.reasoning:
            notes_parts.append(f"Reasoning: {evidence.reasoning}")

        return " | ".join(notes_parts)

    def get_review_queue(
        self, results: List[ArbitrationResult]
    ) -> List[ArbitrationResult]:
        """Get items requiring human review.

        Args:
            results: Arbitration results

        Returns:
            Filtered list of items needing review
        """
        return [r for r in results if r.review_required]

    def get_statistics(self, results: List[ArbitrationResult]) -> Dict[str, Any]:
        """Calculate arbitration statistics.

        Args:
            results: Arbitration results

        Returns:
            Statistics dictionary
        """
        if not results:
            return {
                "total": 0,
                "auto_accepted": 0,
                "review_required": 0,
                "avg_confidence": 0.0,
            }

        review_count = sum(1 for r in results if r.review_required)
        avg_conf = sum(float(r.final_confidence) for r in results) / len(results)

        return {
            "total": len(results),
            "auto_accepted": len(results) - review_count,
            "review_required": review_count,
            "avg_confidence": round(avg_conf, 2),
            "review_rate": round(review_count / len(results) * 100, 1),
        }
