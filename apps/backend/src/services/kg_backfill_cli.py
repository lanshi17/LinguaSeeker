from __future__ import annotations

import argparse
from typing import Sequence

from loguru import logger

from src.services.kg_backfill import run_kg_backfill


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the resumable KG backfill from PostgreSQL paper/evidence data.",
    )
    parser.add_argument(
        "--checkpoint",
        required=True,
        help="Path to the JSON checkpoint file.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of completed paper tasks to process in this run.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_kg_backfill(
        checkpoint_path=args.checkpoint,
        batch_size=args.batch_size,
    )
    logger.info(
        "KG backfill processed {} paper task(s); checkpoint={}",
        report["processed"],
        report["checkpoint_path"],
    )
    return 0
