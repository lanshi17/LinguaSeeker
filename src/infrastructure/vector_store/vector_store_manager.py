"""Vector store manager for persistent knowledge base indexing."""

import hashlib
import json
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from qdrant_client.http import models as rest
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader

from src.infrastructure.utils.logger import Logger


class VectorStoreManager:
    """Manages persistent vector storage for knowledge bases.
    
    Features:
    - Persistent Qdrant database (file-based)
    - Automatic PDF change detection via checksums
    - Lazy loading and incremental updates
    - Thread-safe operations
    
    Database structure:
    - path: ~/.cache/acmg_vector_store/ (or configurable)
    - collections: knowledge_base, temp_pdf
    - metadata: checksums.json (tracks PDF versions)
    """

    def __init__(
        self,
        embeddings: OpenAIEmbeddings,
        cache_dir: Optional[str] = None,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
    ):
        """Initialize vector store manager.
        
        Args:
            embeddings: OpenAI embeddings instance
            cache_dir: Directory for vector store persistence
                      Default: ~/.cache/acmg_vector_store
            chunk_size: Text chunk size for splitting
            chunk_overlap: Overlap between chunks
        """
        self.embeddings = embeddings
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.logger = Logger.get_logger(__name__)
        
        # Setup cache directory
        if cache_dir is None:
            cache_dir = str(Path.home() / ".cache" / "acmg_vector_store")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Qdrant client with persistence
        db_path = str(self.cache_dir / "qdrant_storage")
        self.client = QdrantClient(path=db_path)
        
        # Collections
        self.kb_collection = "knowledge_base"
        self.temp_collection = "temp_pdf"
        
        # Metadata for change detection
        self.checksums_file = self.cache_dir / "checksums.json"
        self.checksums: Dict[str, str] = self._load_checksums()
        
        # Ensure collections exist
        self._ensure_collections()

    def _load_checksums(self) -> Dict[str, str]:
        """Load stored checksums for PDF change detection."""
        if self.checksums_file.exists():
            try:
                with open(self.checksums_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load checksums: {e}")
        return {}

    def _save_checksums(self) -> None:
        """Save checksums to disk."""
        try:
            with open(self.checksums_file, "w") as f:
                json.dump(self.checksums, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save checksums: {e}")

    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file content."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _file_changed(self, file_path: str) -> bool:
        """Check if file has changed since last indexing."""
        try:
            current_hash = self._compute_file_hash(file_path)
            stored_hash = self.checksums.get(file_path)
            
            if stored_hash is None or stored_hash != current_hash:
                self.checksums[file_path] = current_hash
                self._save_checksums()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error checking file hash: {e}")
            return True  # Assume changed on error

    def _ensure_collections(self) -> None:
        """Ensure collections exist in database."""
        try:
            collections = self.client.get_collections()
            existing = {c.name for c in collections.collections}
            
            if self.kb_collection not in existing:
                self.logger.info(f"Creating collection: {self.kb_collection}")
                sample_embedding = self.embeddings.embed_query("test")
                embedding_dim = len(sample_embedding)
                
                self.client.create_collection(
                    collection_name=self.kb_collection,
                    vectors_config=VectorParams(
                        size=embedding_dim,
                        distance=Distance.COSINE,
                    ),
                )
            
            if self.temp_collection not in existing:
                self.logger.info(f"Creating collection: {self.temp_collection}")
                sample_embedding = self.embeddings.embed_query("test")
                embedding_dim = len(sample_embedding)
                
                self.client.create_collection(
                    collection_name=self.temp_collection,
                    vectors_config=VectorParams(
                        size=embedding_dim,
                        distance=Distance.COSINE,
                    ),
                )
        except Exception as e:
            self.logger.error(f"Failed to ensure collections: {e}")

    def build_knowledge_base(self, kb_pdf_paths: List[str], force_rebuild: bool = False) -> int:
        """Build or update knowledge base index.
        
        Args:
            kb_pdf_paths: List of PDF paths to index
            force_rebuild: Force rebuild even if unchanged
            
        Returns:
            Total number of chunks indexed
        """
        all_texts: List[str] = []
        total_chunks = 0
        
        for pdf_path in kb_pdf_paths:
            pdf_path = str(pdf_path)
            
            # Check if file changed
            if not force_rebuild and not self._file_changed(pdf_path):
                self.logger.info(f"Knowledge base '{pdf_path}' unchanged, using cached version")
                continue
            
            self.logger.info(f"Indexing knowledge base: {pdf_path}")
            
            try:
                # Load PDF
                loader = PyPDFLoader(pdf_path)
                docs = loader.load()
                
                # Split into chunks
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                )
                splits = splitter.split_documents(docs)
                texts = [doc.page_content for doc in splits]
                all_texts.extend(texts)
                
                self.logger.info(f"Loaded {len(texts)} chunks from {pdf_path}")
                
            except Exception as e:
                self.logger.error(f"Failed to load KB PDF {pdf_path}: {e}")
                continue
        
        # Only upsert if there are new texts
        if all_texts:
            self.logger.info(f"Upserting {len(all_texts)} chunks to knowledge base")
            vectors = self.embeddings.embed_documents(all_texts)
            
            # Get current point count to avoid ID conflicts
            collection_info = self.client.get_collection(self.kb_collection)
            start_id: int = collection_info.points_count or 0
            
            points = [
                rest.PointStruct(
                    id=start_id + idx,
                    vector=vectors[idx],
                    payload={"text": all_texts[idx], "source": "kb"},
                )
                for idx in range(len(all_texts))
            ]
            
            self.client.upsert(
                collection_name=self.kb_collection,
                points=points,
            )
            
            total_chunks = len(all_texts)
            self.logger.info(f"Knowledge base updated with {total_chunks} chunks")
        else:
            # Get existing count
            collection_info = self.client.get_collection(self.kb_collection)
            total_chunks = collection_info.points_count or 0
            self.logger.info(f"Using existing knowledge base with {total_chunks} chunks")
        
        return total_chunks

    def retrieve_from_knowledge_base(
        self,
        query: str,
        k: int = 4,
        similarity_threshold: float = 0.65,
    ) -> Tuple[List[str], float]:
        """Retrieve relevant documents from knowledge base.
        
        Args:
            query: Search query
            k: Number of results to return
            similarity_threshold: Minimum similarity score
            
        Returns:
            (retrieved_texts, max_similarity_score)
        """
        try:
            collection_info = self.client.get_collection(self.kb_collection)
            if collection_info.points_count == 0:
                self.logger.warning("Knowledge base is empty")
                return [], 0.0
            
            # Embed query
            query_vector = self.embeddings.embed_query(query)
            
            # Search
            search_results = self.client.query_points(
                collection_name=self.kb_collection,
                query=query_vector,
                limit=k,
            ).points
            
            if not search_results:
                return [], 0.0
            
            # Extract documents and scores
            documents: List[str] = []
            scores: List[float] = []
            
            for hit in search_results:
                text = hit.payload.get("text", "")
                score = hit.score
                documents.append(text)
                scores.append(score)
            
            max_score = max(scores) if scores else 0.0
            
            if max_score < similarity_threshold:
                self.logger.warning(
                    f"Max similarity ({max_score:.3f}) below threshold ({similarity_threshold}), "
                    "caller should use fallback"
                )
            
            return documents[:k], max_score
            
        except Exception as e:
            self.logger.error(f"Error retrieving from knowledge base: {e}")
            return [], 0.0

    def add_temporary_documents(
        self,
        texts: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add temporary documents for current session.
        
        Args:
            texts: List of text chunks to add
            metadata: Optional metadata for each chunk
        """
        if not texts:
            return
        
        try:
            # Get current point count
            collection_info = self.client.get_collection(self.temp_collection)
            start_id: int = collection_info.points_count or 0
            
            # Embed texts
            vectors = self.embeddings.embed_documents(texts)
            
            # Create points
            points = [
                rest.PointStruct(
                    id=start_id + idx,
                    vector=vectors[idx],
                    payload={"text": texts[idx], "metadata": metadata or {}, "source": "temp"},
                )
                for idx in range(len(texts))
            ]
            
            self.client.upsert(collection_name=self.temp_collection, points=points)
            self.logger.info(f"Added {len(texts)} temporary documents")
            
        except Exception as e:
            self.logger.error(f"Error adding temporary documents: {e}")

    def clear_temporary_documents(self) -> None:
        """Clear all temporary documents from current session."""
        try:
            self.client.delete_collection(self.temp_collection)
            self._ensure_collections()
            self.logger.info("Cleared temporary documents")
        except Exception as e:
            self.logger.error(f"Error clearing temporary documents: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about vector store.
        
        Returns:
            Dictionary with KB and temp collection stats
        """
        try:
            kb_info = self.client.get_collection(self.kb_collection)
            temp_info = self.client.get_collection(self.temp_collection)
            
            return {
                "knowledge_base": {
                    "points_count": kb_info.points_count,
                    "indexed_vectors_count": kb_info.indexed_vectors_count,
                    "status": str(kb_info.status),
                },
                "temp_collection": {
                    "points_count": temp_info.points_count,
                    "indexed_vectors_count": temp_info.indexed_vectors_count,
                    "status": str(temp_info.status),
                },
                "cache_dir": str(self.cache_dir),
            }
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}
