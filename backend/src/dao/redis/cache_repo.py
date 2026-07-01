"""Redis cache repository for DAO read-model acceleration.

Stores JSON payloads under namespaced keys. Invalidation uses transactional Redis
pipelines so partial network failures cannot leave stale cache behind.
"""

from __future__ import annotations

import json

from typing_extensions import TypedDict

import redis.asyncio as aioredis


class CachePrefixes(TypedDict):
    """Key namespace prefixes for the read-model cache."""

    document: str
    canonical: str
    entity: str
    search: str


CACHE_PREFIX: CachePrefixes = {
    "document": "doc",
    "canonical": "canonical",
    "entity": "entity",
    "search": "search",
}


class CacheRepository:
    """Redis-backed read cache with transactional invalidation."""

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    # ── Key builder ───────────────────────────────────────────────────

    @staticmethod
    def _key(namespace: str, entry_id: str) -> str:
        """Build a namespaced cache key."""
        return f"{namespace}:{entry_id}"

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _encode(value: dict[str, object]) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _decode(raw: bytes | None) -> dict[str, object] | None:  # noqa  # dict-return: unstructured cache JSON.
        """Decode unstructured Redis JSON payloads; cache values have no fixed schema."""
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    # ── Generic get/set ───────────────────────────────────────────────

    async def _get(self, namespace: str, entry_id: str) -> dict[str, object] | None:  # noqa  # dict-return: unstructured cache JSON.
        raw = await self._client.get(self._key(namespace, entry_id))
        return self._decode(raw)

    async def _set(
        self,
        namespace: str,
        entry_id: str,
        value: dict[str, object],
        ttl: int = 3600,
    ) -> None:
        await self._client.set(self._key(namespace, entry_id), self._encode(value), ex=ttl)

    # ── Document cache ────────────────────────────────────────────────

    async def get_document(self, document_id: str) -> dict[str, object] | None:  # noqa  # dict-return: unstructured cache JSON.
        """Return an unstructured cached document payload."""
        return await self._get(CACHE_PREFIX["document"], document_id)

    async def set_document(
        self,
        document_id: str,
        value: dict[str, object],
        ttl: int = 3600,
    ) -> None:
        await self._set(CACHE_PREFIX["document"], document_id, value, ttl)

    # ── Canonical evidence cache ──────────────────────────────────────

    async def get_canonical_evidence(
        self,
        canonical_evidence_id: str,
    ) -> dict[str, object] | None:  # noqa  # dict-return: unstructured cache JSON.
        """Return an unstructured cached canonical evidence payload."""
        return await self._get(CACHE_PREFIX["canonical"], canonical_evidence_id)

    async def set_canonical_evidence(
        self,
        canonical_evidence_id: str,
        value: dict[str, object],
        ttl: int = 3600,
    ) -> None:
        await self._set(CACHE_PREFIX["canonical"], canonical_evidence_id, value, ttl)

    # ── Entity cache ──────────────────────────────────────────────────

    async def get_entity(
        self,
        entity_id: str,
    ) -> dict[str, object] | None:  # noqa  # dict-return: unstructured cache JSON.
        """Return an unstructured cached entity payload."""
        return await self._get(CACHE_PREFIX["entity"], entity_id)

    async def set_entity(
        self,
        entity_id: str,
        value: dict[str, object],
        ttl: int = 3600,
    ) -> None:
        await self._set(CACHE_PREFIX["entity"], entity_id, value, ttl)

    # ── Invalidation ──────────────────────────────────────────────────

    async def invalidate_document(self, document_id: str) -> None:
        """Remove cached document by ID."""
        await self._client.delete(self._key(CACHE_PREFIX["document"], document_id))

    async def invalidate_canonical_evidence(self, canonical_evidence_id: str) -> None:
        """Remove cached canonical evidence by ID."""
        await self._client.delete(self._key(CACHE_PREFIX["canonical"], canonical_evidence_id))

    async def invalidate_entity(self, entity_id: str) -> None:
        """Remove cached entity by ID."""
        await self._client.delete(self._key(CACHE_PREFIX["entity"], entity_id))

    async def invalidate_all(
        self,
        *,
        document_ids: list[str] | None = None,
        canonical_evidence_ids: list[str] | None = None,
        entity_ids: list[str] | None = None,
    ) -> None:
        """Invalidate multiple cache entries across namespaces in ONE pipeline.

        All deletes MUST go through a single pipeline with transaction=True
        so a partial network failure cannot leave stale cache behind.

        Passing no IDs is a no-op.
        """
        keys: list[str] = []
        for doc_id in document_ids or ():
            keys.append(self._key(CACHE_PREFIX["document"], doc_id))
        for ce_id in canonical_evidence_ids or ():
            keys.append(self._key(CACHE_PREFIX["canonical"], ce_id))
        for ent_id in entity_ids or ():
            keys.append(self._key(CACHE_PREFIX["entity"], ent_id))

        if not keys:
            return

        async with self._client.pipeline(transaction=True) as pipe:
            for key in keys:
                pipe.delete(key)
            await pipe.execute()
