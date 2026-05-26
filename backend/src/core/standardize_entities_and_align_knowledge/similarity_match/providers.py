"""Model-server providers for semantic standardization matching."""
from __future__ import annotations

from collections.abc import Sequence

import httpx

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
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client
        self._timeout = timeout

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
        response = await client.post(f"{self._api_root()}/embeddings", json=payload)
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
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client
        self._timeout = timeout

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
        payload = {"query": query, "documents": list(documents), "model": self._model, "top_k": top_k}
        if self._client is not None:
            return await self._post_rerank(self._client, payload)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await self._post_rerank(client, payload)

    async def _post_rerank(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, object],
    ) -> RerankBatchResult:
        response = await client.post(f"{self._api_root()}/rerank", json=payload)
        response.raise_for_status()
        body = response.json()
        results = tuple(
            RerankItem(
                index=int(item["index"]),
                document=str(item["document"]),
                relevance_score=float(item["relevance_score"]),
            )
            for item in body.get("results", [])
        )
        return RerankBatchResult(model=str(body.get("model") or self._model), results=results)

    def _api_root(self) -> str:
        """Normalize provider base URLs so callers may pass either host root or `/v1` root."""
        return self._base_url if self._base_url.endswith("/v1") else f"{self._base_url}/v1"
