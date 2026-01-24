"""Arbiter domain service."""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..entities import Evidence
from ..value_objects import ArbiterFeedback


class ArbiterService(ABC):
    """Domain service for evidence quality arbitration."""

    @abstractmethod
    def score_evidence(
        self, evidence: Evidence, kb_context: Optional[List[str]] = None
    ) -> ArbiterFeedback:
        """Score evidence quality with structured feedback.

        Args:
            evidence: Evidence to score
            kb_context: Optional knowledge base context for scoring guidance

        Returns:
            ArbiterFeedback with overall score, dimension scores, and recommendations
        """
