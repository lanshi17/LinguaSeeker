"""Evidence extraction domain service."""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..entities import Evidence


class EvidenceExtractorService(ABC):
    """Domain service for PS3 evidence extraction."""

    @abstractmethod
    def extract_evidence(
        self,
        english_text: str,
        ps3_context: List[str],
        feedback: Optional[str] = None,
    ) -> Evidence:
        """Extract PS3 evidence from text.

        Args:
            english_text: English document text
            ps3_context: Retrieved PS3 knowledge context
            feedback: Optional feedback from previous iteration for improvement

        Returns:
            Extracted evidence with OddsPath computation and PS3 metadata
        """
