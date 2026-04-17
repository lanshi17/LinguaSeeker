from __future__ import annotations

import argparse
from typing import Sequence

from loguru import logger

from src.services.neo4j_document_backfill import run_document_metadata_backfill


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Backfill Neo4j Document node metadata from PostgreSQL documents.',
    )
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--offset', type=int, default=0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_document_metadata_backfill(limit=args.limit, offset=args.offset)
    logger.info('Neo4j document metadata backfill processed {} document(s)', report['processed'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
