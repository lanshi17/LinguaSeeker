"""RAG repository interface."""

from abc import ABC, abstractmethod
from typing import List, Optional


class RAGRepository(ABC):
    """Abstract repository for RAG (Retrieval Augmented Generation)."""

    @abstractmethod
    def build_knowledge_base_index(self, kb_pdf_paths: List[str]) -> None:
        """Build vector index from knowledge base PDFs.

        Args:
            kb_pdf_paths: List of knowledge base PDF paths (e.g., ACMG guideline, etc.)
        """

    @abstractmethod
    def retrieve_from_knowledge_base(
        self,
        query: str,
        k: int = 4,
        similarity_threshold: float = 0.65,
    ) -> tuple[List[str], float]:
        """Retrieve from knowledge base with fallback mechanism.

        Args:
            query: Search query
            k: Number of results to return
            similarity_threshold: Min similarity score (0-1); if all results below, trigger fallback

        Returns:
            Tuple of (retrieved_texts, max_similarity_score). If max_similarity < threshold,
            caller should trigger fallback to static PDF loading.
        """

    @abstractmethod
    def fallback_load_and_vectorize(self, pdf_path: str) -> None:
        """Fallback: Load static PDF and temporarily vectorize on demand.

        Args:
            pdf_path: Path to PDF to load and vectorize
        """

    @abstractmethod
    def retrieve(
        self,
        query: str,
        k: int = 4,
    ) -> List[str]:
        """Generic retrieve method (kept for backward compatibility).

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of relevant document texts
        """
