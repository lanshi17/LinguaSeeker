"""Build pgvector embeddings for imported terminology entries."""
from __future__ import annotations

import asyncio

from src.core.config import get_config
from src.core.standardize_entities_and_align_knowledge.api import build_terminology_embeddings


async def main() -> None:
    """Run terminology embedding index build."""
    count = await build_terminology_embeddings(cfg=get_config())
    print(f"Built {count} terminology embeddings")


if __name__ == "__main__":
    asyncio.run(main())
