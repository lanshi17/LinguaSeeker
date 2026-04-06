from __future__ import annotations

import argparse
from typing import Sequence

from loguru import logger

from src.services.kg_consumer import process_kg_event
from src.services.kg_events import get_kg_event_service


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay one KG event or a batch of pending KG events.",
    )
    parser.add_argument(
        "--event-id",
        required=False,
        help="Replay a single KG event by event_id.",
    )
    parser.add_argument(
        "--pending-limit",
        type=int,
        default=0,
        help="Process up to N pending events when --event-id is omitted.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.event_id:
        result = process_kg_event(args.event_id)
        logger.info("Processed KG event {} -> {}", args.event_id, result["status"])
        return 0

    limit = max(int(args.pending_limit or 0), 0) or 10
    pending_events = get_kg_event_service().list_pending_kg_events(limit=limit)
    for event in pending_events:
        process_kg_event(str(event.event_id))
    logger.info("Processed {} pending KG event(s)", len(pending_events))
    return 0
