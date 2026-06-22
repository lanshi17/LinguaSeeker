"""External service providers for Phase 3 — embedding generation via model-server."""
from __future__ import annotations

from typing import Any

import httpx


class EmbeddingProvider:
    """Calls the model-server /v1/embeddings API to generate text embeddings."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str = "",
        batch_size: int = 10,
        timeout: float = 60.0,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.batch_size = max(1, batch_size)
        self.timeout = timeout
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of text strings via model-server.

        Args:
            texts: Input text strings.

        Returns:
            List of embedding vectors, each a list of floats.

        Raises:
            httpx.HTTPError: On HTTP failure.
        """
        all_embeddings: list[list[float]] = []
        url = f"{self.base_url}/v1/embeddings"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                payload: dict[str, Any] = {"input": batch}
                if self.model:
                    payload["model"] = self.model

                response = await client.post(url, json=payload, headers=self._headers)
                response.raise_for_status()
                data = response.json()

                # Sort by index to maintain order
                items = sorted(data["data"], key=lambda x: x["index"])
                for item in items:
                    all_embeddings.append(item["embedding"])

        return all_embeddings
