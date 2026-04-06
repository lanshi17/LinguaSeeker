# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportMissingImports=false, reportRedeclaration=false, reportFunctionMemberAccess=false, reportPossiblyUnboundVariable=false, reportReturnType=false

from src.utils.timer import Timer
from src.config import settings
from src.infrastructure.qdrant import QdrantManager
from langchain_openai.embeddings import OpenAIEmbeddings
from typing import List, Dict, Any, Optional
from pydantic import SecretStr
from src.domain.models import (
    RAGQueryRequest, RAGQueryResponse, EmbeddingRequest, EmbeddingResponse,
    RerankRequest, RerankResponse
)

import httpx

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
        """获取 Embedding 客户端实例"""
        if self._embedding_client is None:
            provider = getattr(cfg, "embedding_provider", "openai").lower()
            check_embedding_ctx_length = provider == "openai"
            dimensions = getattr(cfg, "embedding_dimension", None)
            self._embedding_client = OpenAIEmbeddings(
                model=cfg.embedding_model,
                api_key=SecretStr(cfg.embedding_api_key),
                base_url=cfg.embedding_base_url,
                tiktoken_enabled=(provider == "openai"),
                check_embedding_ctx_length=check_embedding_ctx_length,
                dimensions=dimensions,
            )
        return self._embedding_client

    def embed_texts(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """将文本列表转换为向量"""
        client = self.get_embedding_client()
        embeddings = client.embed_documents(request.texts)
        return EmbeddingResponse(embeddings=embeddings)

    async def search_qdrant(self, query: str, top_k: int, score_threshold: float) -> RAGQueryResponse:
        """在 Qdrant 中检索 Top-K 文档"""
        qdrant_manager = self.get_qdrant_manager()
        embedding_client = self.get_embedding_client()

        query_vector = embedding_client.embed_query(query)
        search_response = await qdrant_manager.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
        )

        response_items = []
        for item in search_response.results:
            payload = item.payload or {}
            response_items.append({
                "document_id": str(item.point_id),
                "content": payload.get("content", ""),
                "score": float(item.score),
            })

        return RAGQueryResponse(results=response_items)
    def rerank(self, request: RerankRequest) -> RerankResponse:
        """重排序检索结果--HTTP调用精排服务"""
        
        api_key = cfg.rerank_api_key
        url = cfg.rerank_base_url
        payload = {
            "model": "qwen3-rerank",
            "query": request.query,
            "documents": request.documents,
            "top_n": len(request.documents),
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()
        
        data = response.json()
        results = [
            {
                "document": item["document"],
                "score": float(item["score"]),
            }
            for item in data.get("results", [])
        ]
        
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

    @Timer("RAG pipeline completed in {elapsed:.2f} seconds.")
    async def rag_pipeline(
        self,
        request: RAGQueryRequest
    ) -> Dict[str, Any]:
        """完整 RAG 流程：Embedding → 检索 → 可选精排 → 拼接上下文"""
        if not request.query.strip():
            raise ValueError("query is empty")

        resolved_top_k = int(request.top_k or getattr(cfg, "qdrant_top_k", 5))
        resolved_score_threshold = float(
            request.score_threshold if request.score_threshold is not None else getattr(cfg, "qdrant_score_threshold", 0.7)
        )

        response = await self.search_qdrant(
            request.query,
            top_k=resolved_top_k,
            score_threshold=resolved_score_threshold,
        )

        results: List[Dict[str, Any]] = [item.model_dump() for item in response.results]

        if request.enable_rerank and results:
            rerank_request = RerankRequest(
                query=request.query,
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

        context = self.build_context(results, max_chars=request.max_context_chars or 4000)
        return {
            "results": results,
            "context": context,
        }
    