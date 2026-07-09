"""HTTP providers for semantic standardization matching."""

from __future__ import annotations

from collections.abc import Sequence

import httpx
from loguru import logger

from src.core.standardize_entities_and_align_knowledge.similarity_match.contracts import (
    EmbeddingBatchResult,
    RerankBatchResult,
    RerankItem,
)


class EmbeddingHttpProvider:
    """HTTP client for embedding services.

    Supports two API styles:
      - "openai": OpenAI-compatible, POST /v1/embeddings, auth header.
      - "simple":  POST /embed with {"texts": […]}, no auth.

    Multiple API keys are rotated round-robin across calls.
    """

    _SIMPLE = "simple"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
        api_key: str | None = None,
        api_keys: list[str] | None = None,
        api_style: str = "openai",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client
        self._timeout = timeout
        self._api_style = api_style
        # Merge api_keys + api_key (deduplicated, preserving order).
        seen: set[str] = set()
        merged: list[str] = []
        for k in [*(api_keys or []), api_key or ""]:
            k = k.strip()
            if k and k not in seen:
                seen.add(k)
                merged.append(k)
        self._api_keys = merged
        self._key_idx = 0

    def _current_headers(self) -> dict[str, str]:
        """Return auth headers using the current round-robin key."""
        if not self._api_keys:
            return {}
        key = self._api_keys[self._key_idx % len(self._api_keys)]
        return {"Authorization": f"Bearer {key}"}

    def _rotate_key(self) -> None:
        """Advance to the next API key."""
        if len(self._api_keys) > 1:
            self._key_idx = (self._key_idx + 1) % len(self._api_keys)

    async def embed_texts(self, texts: str | Sequence[str]) -> EmbeddingBatchResult:
        """Embed texts through the service."""
        if isinstance(texts, str):
            texts = (texts,)
        text_list = list(texts)
        if self._api_style == self._SIMPLE:
            payload: dict[str, object] = {"texts": text_list}
        else:
            payload = {"input": text_list, "model": self._model}
        if self._client is not None:
            result = (
                await self._post_simple_embeddings(self._client, text_list)
                if self._api_style == self._SIMPLE
                else await self._post_embeddings(self._client, payload, len(text_list))
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                result = (
                    await self._post_simple_embeddings(client, text_list)
                    if self._api_style == self._SIMPLE
                    else await self._post_embeddings(client, payload, len(text_list))
                )
        self._rotate_key()
        return result

    async def _post_simple_embeddings(
        self,
        client: httpx.AsyncClient,
        texts: list[str],
    ) -> EmbeddingBatchResult:
        payloads: tuple[dict[str, object], ...] = (
            {"texts": texts},
            {"inputs": texts},
            {"input": texts},
            {"sentences": texts},
        )
        last_exc: httpx.HTTPStatusError | None = None
        for payload in payloads:
            try:
                return await self._post_embeddings(client, payload, len(texts))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 422:
                    raise
                last_exc = exc
                logger.debug(
                    "Simple embedding payload rejected with 422; retrying alternate schema: keys={}",
                    list(payload.keys()),
                )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No simple embedding payloads configured")

    async def _post_embeddings(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, object],
        expected_count: int,
    ) -> EmbeddingBatchResult:
        response = await client.post(self._endpoint_url(), json=payload, headers=self._current_headers())
        response.raise_for_status()
        body = response.json()
        if self._api_style == self._SIMPLE:
            vectors = _parse_simple_embedding_vectors(body)
        else:
            data = sorted(body.get("data", []), key=lambda item: item.get("index", 0))
            vectors = tuple(tuple(float(value) for value in item["embedding"]) for item in data)
        if len(vectors) != expected_count:
            raise ValueError(f"Embedding service returned {len(vectors)} vectors for {expected_count} input texts")
        return EmbeddingBatchResult(model=str(body.get("model") or self._model), vectors=vectors)

    def _api_root(self) -> str:
        """Normalize provider base URLs.  In "simple" mode the base URL IS the API root."""
        if self._api_style == self._SIMPLE:
            return self._base_url
        return self._base_url if self._base_url.endswith("/v1") else f"{self._base_url}/v1"

    def _endpoint_url(self) -> str:
        endpoint = "embed" if self._api_style == self._SIMPLE else "embeddings"
        return f"{self._api_root()}/{endpoint}"


class RerankHttpProvider:
    """HTTP client for rerank scoring services.

    Supports two API styles:
      - "openai": OpenAI-compatible, POST /v1/rerank with model param, auth header.
      - "simple":  POST /rerank, no model param, no auth.

    Multiple API keys are rotated round-robin across calls.
    """

    _SIMPLE = "simple"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
        api_key: str | None = None,
        api_keys: list[str] | None = None,
        api_style: str = "openai",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client
        self._timeout = timeout
        self._api_style = api_style
        # Merge api_keys + api_key (deduplicated, preserving order).
        seen: set[str] = set()
        merged: list[str] = []
        for k in [*(api_keys or []), api_key or ""]:
            k = k.strip()
            if k and k not in seen:
                seen.add(k)
                merged.append(k)
        self._api_keys = merged
        self._key_idx = 0

    def _current_headers(self) -> dict[str, str]:
        """Return auth headers using the current round-robin key."""
        if not self._api_keys:
            return {}
        key = self._api_keys[self._key_idx % len(self._api_keys)]
        return {"Authorization": f"Bearer {key}"}

    def _rotate_key(self) -> None:
        """Advance to the next API key."""
        if len(self._api_keys) > 1:
            self._key_idx = (self._key_idx + 1) % len(self._api_keys)

    async def rerank(
        self,
        query: str,
        documents: str | Sequence[str],
        *,
        top_k: int | None,
    ) -> RerankBatchResult:
        """Rerank documents through the service."""
        if isinstance(documents, str):
            documents = (documents,)
        doc_list = list(documents)
        if self._api_style == self._SIMPLE:
            payload: dict[str, object] = {"query": query, "documents": doc_list, "top_k": top_k}
        else:
            payload = {"query": query, "documents": doc_list, "model": self._model, "top_k": top_k}
        if self._client is not None:
            result = await self._post_rerank(self._client, payload, doc_list)
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                result = await self._post_rerank(client, payload, doc_list)
        self._rotate_key()
        return result

    async def _post_rerank(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, object],
        doc_list: list[str],
    ) -> RerankBatchResult:
        response = await client.post(self._endpoint_url(), json=payload, headers=self._current_headers())
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
        """Normalize provider base URLs.  In "simple" mode the base URL IS the API root."""
        if self._api_style == self._SIMPLE:
            return self._base_url
        return self._base_url if self._base_url.endswith("/v1") else f"{self._base_url}/v1"

    def _endpoint_url(self) -> str:
        return f"{self._api_root()}/rerank"


class FallbackEmbeddingProvider:
    """Embedding provider with local-first, remote-fallback strategy.

    Warning: the remote model should match the local model. Persisted pgvector
    embeddings are model-specific — query-time vectors from a different model
    produce meaningless cosine similarity scores against stored vectors.
    """

    def __init__(
        self,
        local: EmbeddingHttpProvider,
        remote: EmbeddingHttpProvider | None = None,
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
            logger.warning(
                "Local embedding failed at {} ({}: {!r}), falling back to remote",
                self._local._endpoint_url(),
                type(e).__name__,
                e,
            )
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
        local: RerankHttpProvider,
        remote: RerankHttpProvider | None = None,
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
            logger.warning(
                "Local rerank failed at {} ({}: {!r}), falling back to remote",
                self._local._endpoint_url(),
                type(e).__name__,
                e,
            )
            return await self._remote.rerank(query, documents, top_k=top_k)


def _parse_simple_embedding_vectors(body: object) -> tuple[tuple[float, ...], ...]:
    if not isinstance(body, dict):
        raise ValueError("Embedding service response must be a JSON object")

    results = body.get("results")
    if isinstance(results, list):
        return tuple(_coerce_embedding_vector(item.get("embedding") if isinstance(item, dict) else item) for item in results)

    for key in ("embeddings", "vectors"):
        value = body.get(key)
        if isinstance(value, list):
            return tuple(_coerce_embedding_vector(item) for item in value)

    embedding = body.get("embedding")
    if isinstance(embedding, list):
        return (_coerce_embedding_vector(embedding),)

    data = body.get("data")
    if isinstance(data, list):
        sorted_data = sorted(data, key=lambda item: item.get("index", 0) if isinstance(item, dict) else 0)
        return tuple(
            _coerce_embedding_vector(item.get("embedding") if isinstance(item, dict) else item) for item in sorted_data
        )

    raise ValueError(f"Embedding service response does not contain vectors; keys={list(body.keys())}")


def _coerce_embedding_vector(values: object) -> tuple[float, ...]:
    if not isinstance(values, list):
        raise ValueError("Embedding vector must be a JSON array")
    return tuple(float(value) for value in values)
