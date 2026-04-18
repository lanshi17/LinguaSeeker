from __future__ import annotations

import argparse
from typing import Sequence

from loguru import logger

from src.services.neo4j_disease_icd10_backfill import run_disease_icd10_backfill


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Backfill Neo4j Disease node ICD10 metadata from PostgreSQL evidence records.',
    )
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--offset', type=int, default=0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_disease_icd10_backfill(limit=args.limit, offset=args.offset)
    logger.info('Neo4j disease ICD10 backfill processed {} disease row(s)', report['processed'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
