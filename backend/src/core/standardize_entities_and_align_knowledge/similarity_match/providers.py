"""Model-server providers for semantic standardization matching."""
from __future__ import annotations

from collections.abc import Sequence

import httpx
from loguru import logger

from src.core.standardize_entities_and_align_knowledge.similarity_match.contracts import (
    EmbeddingBatchResult,
    RerankBatchResult,
    RerankItem,
)


class ModelServerEmbeddingProvider:
    """Client for model-server OpenAI-compatible embeddings."""
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client
        self._timeout = timeout
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def embed_texts(self, texts: str | Sequence[str]) -> EmbeddingBatchResult:
        """Embed texts through model-server `/v1/embeddings`."""
        if isinstance(texts, str):
            texts = (texts,)
        payload = {"input": list(texts), "model": self._model}
        if self._client is not None:
            return await self._post_embeddings(self._client, payload)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await self._post_embeddings(client, payload)

    async def _post_embeddings(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, object],
    ) -> EmbeddingBatchResult:
        response = await client.post(f"{self._api_root()}/embeddings", json=payload, headers=self._headers)
        response.raise_for_status()
        body = response.json()
        data = sorted(body.get("data", []), key=lambda item: item.get("index", 0))
        vectors = tuple(tuple(float(value) for value in item["embedding"]) for item in data)
        return EmbeddingBatchResult(model=str(body.get("model") or self._model), vectors=vectors)

    def _api_root(self) -> str:
        """Normalize provider base URLs so callers may pass either host root or `/v1` root."""
        return self._base_url if self._base_url.endswith("/v1") else f"{self._base_url}/v1"


class ModelServerRerankProvider:
    """Client for model-server rerank scoring."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client
        self._timeout = timeout
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def rerank(
        self,
        query: str,
        documents: str | Sequence[str],
        *,
        top_k: int | None,
    ) -> RerankBatchResult:
        """Rerank documents through model-server `/v1/rerank`."""
        if isinstance(documents, str):
            documents = (documents,)
        doc_list = list(documents)
        payload = {"query": query, "documents": doc_list, "model": self._model, "top_k": top_k}
        if self._client is not None:
            return await self._post_rerank(self._client, payload, doc_list)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await self._post_rerank(client, payload, doc_list)

    async def _post_rerank(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, object],
        doc_list: list[str],
    ) -> RerankBatchResult:
        response = await client.post(f"{self._api_root()}/rerank", json=payload, headers=self._headers)
        response.raise_for_status()
        body = response.json()
        results = tuple(
            RerankItem(
                index=int(item["index"]),
                document=str(item["document"]) if item.get("document") is not None else doc_list[int(item["index"])],
                relevance_score=float(item["relevance_score"]),
            )
            for item in body.get("results", [])
        )
        return RerankBatchResult(model=str(body.get("model") or self._model), results=results)

    def _api_root(self) -> str:
        """Normalize provider base URLs so callers may pass either host root or `/v1` root."""
        return self._base_url if self._base_url.endswith("/v1") else f"{self._base_url}/v1"


class FallbackEmbeddingProvider:
    """Embedding provider with local-first, remote-fallback strategy.

    Warning: the remote model should match the local model. Persisted pgvector
    embeddings are model-specific — query-time vectors from a different model
    produce meaningless cosine similarity scores against stored vectors.
    """

    def __init__(
        self,
        local: ModelServerEmbeddingProvider,
        remote: ModelServerEmbeddingProvider | None = None,
    ) -> None:
        self._local = local
        self._remote = remote
        if remote is not None and local._model != remote._model:
            logger.warning(
                "Embedding model mismatch: local={} remote={}. "
                "Persisted pgvector embeddings require the same model for query-time vectors.",
                local._model,
                remote._model,
            )

    async def embed_texts(self, texts: str | Sequence[str]) -> EmbeddingBatchResult:
        try:
            return await self._local.embed_texts(texts)
        except Exception as e:
            if self._remote is None:
                raise
            logger.warning("Local embedding failed ({}), falling back to remote", e)
            result = await self._remote.embed_texts(texts)
            if self._local._model != self._remote._model:
                logger.error(
                    "CRITICAL: remote embedding used a different model ({}). "
                    "Cosine similarity against persisted vectors will be unreliable.",
                    self._remote._model,
                )
            return result


class FallbackRerankProvider:
    """Rerank provider with local-first, remote-fallback strategy."""

    def __init__(
        self,
        local: ModelServerRerankProvider,
        remote: ModelServerRerankProvider | None = None,
    ) -> None:
        self._local = local
        self._remote = remote

    async def rerank(
        self,
        query: str,
        documents: str | Sequence[str],
        *,
        top_k: int | None,
    ) -> RerankBatchResult:
        try:
            return await self._local.rerank(query, documents, top_k=top_k)
        except Exception as e:
            if self._remote is None:
                raise
            logger.warning("Local rerank failed ({}), falling back to remote", e)
            return await self._remote.rerank(query, documents, top_k=top_k)
