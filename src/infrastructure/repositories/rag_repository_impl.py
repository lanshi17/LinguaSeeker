"""RAG repository implementation."""

from pathlib import Path
from typing import List, Optional, Tuple

import httpx
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.models import Distance, VectorParams

# Using absolute imports from src root
from src.domain.repositories import RAGRepository
from src.infrastructure.utils.exceptions import ParsingException
from src.infrastructure.utils.config import RerankConfig
from src.infrastructure.utils.logger import Logger


class RAGRepositoryImpl(RAGRepository):
    """Concrete RAG repository using Qdrant and OpenAI embeddings.
    
    Two-collection design:
    - `knowledge_base_collection`: Pre-built index from ACMG guidelines, etc.
    - `temp_collection`: Temporary vectorization for fallback/static PDF loading
    """

    def __init__(self, embeddings: OpenAIEmbeddings, rerank_config: Optional[RerankConfig] = None):
        self.embeddings = embeddings
        self.client = QdrantClient(":memory:")
        self.kb_collection = "knowledge_base"
        self.temp_collection = "temp_pdf"
        self.rerank_config = rerank_config
        self.logger = Logger.get_logger(__name__)
        self._kb_built = False

    def build_knowledge_base_index(self, kb_pdf_paths: List[str]) -> None:
        """Build permanent knowledge base index from list of KB PDFs.
        
        Args:
            kb_pdf_paths: List of paths to knowledge base PDFs (e.g., ['KnowledgeRetrievalBase/acmg_guide.pdf'])
        """
        all_texts = []
        for pdf_path in kb_pdf_paths:
            self.logger.info(f"Loading knowledge base PDF: {pdf_path}")
            try:
                loader = PyPDFLoader(pdf_path)
                docs = loader.load()
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=800,
                    chunk_overlap=100,
                )
                splits = splitter.split_documents(docs)
                all_texts.extend([doc.page_content for doc in splits])
            except Exception as e:
                self.logger.warning(f"Failed to load KB PDF {pdf_path}: {e}")

        if not all_texts:
            self.logger.warning("No texts loaded from knowledge base PDFs")
            self._kb_built = False
            return

        # Create vector index
        sample_embedding = self.embeddings.embed_query("test")
        embedding_dim = len(sample_embedding)

        self.client.recreate_collection(
            collection_name=self.kb_collection,
            vectors_config=VectorParams(
                size=embedding_dim,
                distance=Distance.COSINE,
            ),
        )

        vectors = self.embeddings.embed_documents(all_texts)
        points = [
            rest.PointStruct(
                id=idx,
                vector=vectors[idx],
                payload={"text": all_texts[idx]},
            )
            for idx in range(len(all_texts))
        ]
        self.client.upsert(collection_name=self.kb_collection, points=points)
        self._kb_built = True
        self.logger.info(f"Knowledge base index built with {len(all_texts)} chunks")

    def retrieve_from_knowledge_base(
        self,
        query: str,
        k: int = 4,
        similarity_threshold: float = 0.65,
    ) -> Tuple[List[str], float]:
        """Retrieve from KB with similarity threshold detection.
        
        Returns:
            (retrieved_texts, max_similarity_score)
            If max_similarity < threshold, caller should trigger fallback.
        """
        if not self._kb_built:
            self.logger.warning("Knowledge base not built; returning empty results")
            return [], 0.0

        vector = self.embeddings.embed_query(query)
        results = self.client.query_points(
            collection_name=self.kb_collection,
            query=vector,
            limit=k * 3 if self.rerank_config and self.rerank_config.enabled else k,
        ).points

        if not results:
            return [], 0.0

        # Extract similarity scores and documents
        documents = []
        scores = []
        for hit in results:
            text = hit.payload.get("text", "")
            score = hit.score
            documents.append(text)
            scores.append(score)

        max_score = max(scores) if scores else 0.0

        # Apply reranking if enabled
        if self.rerank_config and self.rerank_config.enabled and documents:
            documents = self._rerank_documents(query, documents, k)

        return documents[:k], max_score

    def fallback_load_and_vectorize(self, pdf_path: str) -> None:
        """Fallback: Temporarily vectorize a static PDF and add to temp collection."""
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

            # Create temp collection if needed
            if not self.client.collection_exists(self.temp_collection):
                sample_embedding = self.embeddings.embed_query("test")
                embedding_dim = len(sample_embedding)
                self.client.recreate_collection(
                    collection_name=self.temp_collection,
                    vectors_config=VectorParams(
                        size=embedding_dim,
                        distance=Distance.COSINE,
                    ),
                )

            vectors = self.embeddings.embed_documents(texts)
            points = [
                rest.PointStruct(
                    id=idx,
                    vector=vectors[idx],
                    payload={"text": texts[idx]},
                )
                for idx in range(len(texts))
            ]
            self.client.upsert(collection_name=self.temp_collection, points=points)
            self.logger.info(f"Fallback: Temporarily vectorized {len(texts)} chunks")
        except Exception as e:
            self.logger.error(f"Fallback vectorization failed: {e}")

    def retrieve(self, query: str, k: int = 4) -> List[str]:
        """Generic retrieve (backward compatibility).
        
        Prioritizes knowledge base; falls back to temp collection if available.
        """
        docs, max_score = self.retrieve_from_knowledge_base(query, k, similarity_threshold=0.0)
        if docs:
            return docs

        # Try temp collection
        if self.client.collection_exists(self.temp_collection):
            vector = self.embeddings.embed_query(query)
            results = self.client.query_points(
                collection_name=self.temp_collection,
                query=vector,
                limit=k,
            ).points
            return [hit.payload.get("text", "") for hit in results]

        return []

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
