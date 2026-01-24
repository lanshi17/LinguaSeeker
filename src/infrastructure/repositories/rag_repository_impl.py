"""RAG repository implementation with persistent vector store."""

from pathlib import Path
from typing import List, Optional, Tuple

import httpx
from langchain_openai import OpenAIEmbeddings

# Using absolute imports from src root
from src.domain.repositories import RAGRepository
from src.infrastructure.utils.exceptions import ParsingException
from src.infrastructure.utils.config import RerankConfig
from src.infrastructure.utils.logger import Logger
from src.infrastructure.vector_store import VectorStoreManager


class RAGRepositoryImpl(RAGRepository):
    """Concrete RAG repository using persistent VectorStoreManager.
    
    Features:
    - Persistent vector storage (cached across runs)
    - Automatic PDF change detection
    - Fallback to temporary vectorization
    - Optional document reranking
    """

    def __init__(
        self,
        embeddings: OpenAIEmbeddings,
        rerank_config: Optional[RerankConfig] = None,
        cache_dir: Optional[str] = None,
    ):
        """Initialize RAG repository.
        
        Args:
            embeddings: OpenAI embeddings instance
            rerank_config: Optional reranking configuration
            cache_dir: Directory for persistent vector store
        """
        self.embeddings = embeddings
        self.rerank_config = rerank_config
        self.logger = Logger.get_logger(__name__)
        
        # Use persistent vector store manager
        self.vector_store = VectorStoreManager(
            embeddings=embeddings,
            cache_dir=cache_dir,
        )
        
        self._kb_built = False

    def build_knowledge_base_index(self, kb_pdf_paths: List[str]) -> None:
        """Build or update persistent knowledge base index.
        
        Uses automatic change detection - PDFs are only re-indexed if modified.
        
        Args:
            kb_pdf_paths: List of paths to knowledge base PDFs
        """
        total_chunks = self.vector_store.build_knowledge_base(kb_pdf_paths)
        self._kb_built = total_chunks > 0
        
        if self._kb_built:
            self.logger.info(f"Knowledge base ready with {total_chunks} chunks")
            stats = self.vector_store.get_statistics()
            self.logger.debug(f"Vector store stats: {stats}")
        else:
            self.logger.warning("Failed to build knowledge base")

    def retrieve_from_knowledge_base(
        self,
        query: str,
        k: int = 4,
        similarity_threshold: float = 0.65,
    ) -> Tuple[List[str], float]:
        """Retrieve from persistent knowledge base.
        
        Returns:
            (retrieved_texts, max_similarity_score)
        """
        if not self._kb_built:
            self.logger.warning("Knowledge base not built")
            return [], 0.0
        
        documents, max_score = self.vector_store.retrieve_from_knowledge_base(
            query=query,
            k=k,
            similarity_threshold=similarity_threshold,
        )
        
        # Apply reranking if enabled
        if self.rerank_config and self.rerank_config.enabled and documents:
            documents = self._rerank_documents(query, documents, k)
        
        return documents[:k], max_score

    def fallback_load_and_vectorize(self, pdf_path: str) -> None:
        """Fallback: Temporarily vectorize a static PDF.
        
        Args:
            pdf_path: Path to PDF file to vectorize temporarily
        """
        from langchain_community.document_loaders import PyPDFLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            self.logger.warning(f"Fallback PDF not found: {pdf_path}")
            return
        
        self.logger.info(f"Fallback: Loading and vectorizing {pdf_path}")
        try:
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=800,
                chunk_overlap=100,
            )
            splits = splitter.split_documents(docs)
            texts = [doc.page_content for doc in splits]
            
            self.vector_store.add_temporary_documents(texts, metadata={"source": pdf_path})
            self.logger.info(f"Fallback: Vectorized {len(texts)} chunks")
            
        except Exception as e:
            self.logger.error(f"Fallback vectorization failed: {e}")

    def retrieve(self, query: str, k: int = 4) -> List[str]:
        """Generic retrieve (backward compatibility).
        
        Attempts retrieval from persistent knowledge base.
        
        Args:
            query: Search query
            k: Number of results
            
        Returns:
            List of relevant documents
        """
        docs, _ = self.retrieve_from_knowledge_base(query, k, similarity_threshold=0.0)
        return docs

    def _rerank_documents(self, query: str, documents: List[str], top_k: int) -> List[str]:
        """Rerank documents using OpenAI-compatible rerank API."""
        try:
            self.logger.info(f"Reranking {len(documents)} documents with model {self.rerank_config.model}")

            payload = {
                "model": self.rerank_config.model,
                "query": query,
                "documents": documents,
                "top_n": min(top_k, len(documents)),
                "instruct": self.rerank_config.instruct,
            }

            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.rerank_config.endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.rerank_config.api_key}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    if "results" in result:
                        reranked_docs = []
                        for item in result["results"]:
                            if "index" in item:
                                idx = item["index"]
                                if 0 <= idx < len(documents):
                                    reranked_docs.append(documents[idx])
                            elif "document" in item:
                                reranked_docs.append(item["document"]["text"])

                        if reranked_docs:
                            self.logger.info(f"Successfully reranked to {len(reranked_docs)} documents")
                            return reranked_docs

                self.logger.warning(f"Rerank failed with status {response.status_code}")
                return documents

        except Exception as e:
            self.logger.error(f"Rerank error: {e}")
            return documents
