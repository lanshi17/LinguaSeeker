import os
from utils.timer import Timer, timer
import utils.exceptions as exc
import utils.file_utils as file_utils
from config import settings
from database.qdrant import QdrantManager
from langchain_openai.embeddings import OpenAIEmbeddings
from loguru import logger
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field,SecretStr
from .models import (
    RAGQueryRequest, RAGQueryResponse, QdrantPoint,
    QdrantSearchResponse, EmbeddingRequest, EmbeddingResponse,
    RerankRequest, RerankResponse
)
from uuid import uuid4
from pathlib import Path
from datetime import datetime

cfg = settings


class RAGComponent:
    """RAG 组件类，负责调用 Qdrant 知识库并构建上下文"""

    def __init__(self):
        self._qdrant_manager: Optional[QdrantManager] = None
        self._embedding_client: Optional[OpenAIEmbeddings] = None

    def get_qdrant_manager(self) -> QdrantManager:
        """获取 Qdrant 管理器实例"""
        if self._qdrant_manager is None:
            self._qdrant_manager = QdrantManager()
        return self._qdrant_manager

    def get_embedding_client(self) -> OpenAIEmbeddings:
        """获取 Embedding 客户端"""
        if self._embedding_client is None:
            self._embedding_client = OpenAIEmbeddings(
                model=cfg.embedding_model,
                api_key=SecretStr(cfg.embedding_api_key),
                base_url=cfg.embedding_base_url,
            )
        return self._embedding_client

    def embed_texts(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """将文本列表转换为向量"""
        client = self.get_embedding_client()
        embeddings = client.embed_documents(request.texts)
        return EmbeddingResponse(embeddings=embeddings)

    def search_qdrant(self, query: str, top_k: int, score_threshold: float) -> RAGQueryResponse:
        """在 Qdrant 中检索 Top-K 文档"""
        qdrant_manager = self.get_qdrant_manager()
        embedding_client = self.get_embedding_client()

        query_vector = embedding_client.embed_query(query)
        results = qdrant_manager.client.search(  # type: ignore[attr-defined]
            collection_name=qdrant_manager.collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
        )

        response_items = []
        for item in results:
            response_items.append({
                "document_id": str(item.id),
                "content": item.payload.get("content", ""),
                "score": float(item.score),
            })

        return RAGQueryResponse(results=response_items)

    def rerank(self, request: RerankRequest) -> RerankResponse:
        """可选的精排步骤（当前为占位实现）"""
        logger.info("Rerank is not configured; returning original order.")
        results = []
        for index, doc in enumerate(request.documents):
            score = 1.0 - (index * 0.01)
            results.append({"document": doc, "score": score})
        return RerankResponse(results=results)

    def build_context(self, results: List[Dict[str, Any]], max_chars: int = 4000) -> str:
        """拼接检索结果为上下文"""
        chunks = []
        total = 0
        for idx, item in enumerate(results, start=1):
            content = item.get("content", "")
            header = f"[Doc {idx}] (score={item.get('score', 0):.3f})\n"
            chunk = f"{header}{content}\n"
            if total + len(chunk) > max_chars:
                break
            chunks.append(chunk)
            total += len(chunk)
        return "\n".join(chunks) if chunks else ""

    def rag_pipeline(
        self,
        query: str,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        enable_rerank: bool = False,
    ) -> Dict[str, Any]:
        """完整 RAG 流程：Embedding → 检索 → 可选精排 → 拼接上下文"""
        if not query.strip():
            raise ValueError("query is empty")

        resolved_top_k = int(top_k or getattr(cfg, "qdrant_top_k", 5))
        resolved_score_threshold = float(
            score_threshold if score_threshold is not None else getattr(cfg, "qdrant_score_threshold", 0.7)
        )

        response = self.search_qdrant(
            query,
            top_k=resolved_top_k,
            score_threshold=resolved_score_threshold,
        )

        results: List[Dict[str, Any]] = [item.model_dump() for item in response.results]

        if enable_rerank and results:
            rerank_request = RerankRequest(
                query=query,
                documents=[item.get("content", "") for item in results],
            )
            rerank_response = self.rerank(rerank_request)
            results = [
                {
                    "document_id": str(index),
                    "content": item.document,
                    "score": item.score,
                }
                for index, item in enumerate(rerank_response.results)
            ]

        context = self.build_context(results)
        return {
            "results": results,
            "context": context,
        }
    