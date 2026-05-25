"""Import local terminology database files into PostgreSQL reference tables."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from src.core.config import get_config


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for terminology import."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminology-root", default="database/terminology_database")
    parser.add_argument("--version", required=True)
    parser.add_argument("--sources", nargs="+", default=["hgnc", "omim", "hpo", "clingen", "clinvar"])
    return parser.parse_args()


async def main() -> None:
    """Run the terminology import facade."""
    from src.core.standardize_entities_and_align_knowledge.api import import_terminology

    args = parse_args()
    await import_terminology(
        cfg=get_config(),
        terminology_root=Path(args.terminology_root),
        version=args.version,
        sources=args.sources,
    )


if __name__ == "__main__":
    asyncio.run(main())
