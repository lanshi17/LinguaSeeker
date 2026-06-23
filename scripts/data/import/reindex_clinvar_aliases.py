"""Reindex ClinVar aliases with the widened derivation and clean dead X-form stop aliases.

Phase 1-2 widened the ClinVar protein alias derivation: stop codons are now emitted
as the one-letter ``*`` form (e.g. ``p.R243*``) instead of the legacy ``X`` form
(e.g. ``p.R243X``), and coding / fs / del / dup / ins protein aliases are indexed
alongside the short form. Re-running the ClinVar terminology import upserts the new
aliases additively (``ON CONFLICT DO UPDATE`` on
``(entry_id, normalized_alias, alias_type)``), so the widened derivation is applied
to existing ``terminology_entries`` without dropping prior data.

The legacy ``protein_short`` aliases of the form ``p.<A><pos>X`` (the old stop
representation) are now dead — superseded by the ``*`` form produced by the new
importer. This script deletes them after the re-import so the alias index carries
only the canonical stop representation.

Both steps are idempotent:

  * Re-running the import re-upserts the same rows (no-op effect on already-widened
    aliases).
  * Re-running the cleanup deletes zero rows once no ``X``-form stop aliases remain.

Run from the backend directory so application config loads::

    cd backend
    uv run python ../scripts/reindex_clinvar_aliases.py --version 2026-05-26
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from loguru import logger
from sqlalchemy import text

from src.core.config import get_config
from src.dao.postgresql import async_session_factory, build_async_engine

# Protein-short aliases of the legacy stop form ``p.<A><pos>X`` (one-letter ref,
# one-or-more digits, trailing ``X``). Anchored so it never matches the new ``*``
# form, fs/del/dup/ins forms, or three-letter aliases like ``p.Glu243X``.
_DEAD_STOP_ALIAS_REGEX = r"^p\.[A-Z]\d+X$"

_COUNT_DEAD_STOP_ALIASES_SQL = text(
    "SELECT count(*) FROM terminology_aliases "
    "WHERE entity_type = 'variant' "
    "AND alias_type = 'protein_short' "
    f"AND normalized_alias ~ '{_DEAD_STOP_ALIAS_REGEX}'"
)

_DELETE_DEAD_STOP_ALIASES_SQL = text(
    "DELETE FROM terminology_aliases "
    "WHERE entity_type = 'variant' "
    "AND alias_type = 'protein_short' "
    f"AND normalized_alias ~ '{_DEAD_STOP_ALIAS_REGEX}'"
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the ClinVar alias reindex."""
    parser = argparse.ArgumentParser(
        description="Reindex ClinVar aliases and clean dead X-form stop aliases.",
    )
    parser.add_argument(
        "--version",
        default="2026-05-26",
        help="Terminology version label (default: 2026-05-26).",
    )
    parser.add_argument(
        "--terminology-root",
        default="database/terminology_database",
        help="Path to the terminology database root (default: database/terminology_database).",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["clinvar"],
        help="Terminology sources to import (default: clinvar).",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Skip the re-import step; only run the dead-alias cleanup.",
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip the dead-alias cleanup; only run the re-import.",
    )
    return parser.parse_args()


def _configure_logger() -> None:
    """Configure loguru to emit concise progress lines to stderr."""
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")


async def _run_import(args: argparse.Namespace) -> None:
    """Re-run the ClinVar terminology import through the public facade."""
    from src.core.standardize_entities_and_align_knowledge.api import import_terminology

    logger.info(
        "Re-importing terminology: root={}, version={}, sources={}",
        args.terminology_root,
        args.version,
        args.sources,
    )
    started = time.perf_counter()
    await import_terminology(
        cfg=get_config(),
        terminology_root=Path(args.terminology_root),
        version=args.version,
        sources=args.sources,
    )
    logger.info("Terminology re-import finished in {:.2f}s", time.perf_counter() - started)


async def _cleanup_dead_stop_aliases() -> int:
    """Delete legacy X-form stop aliases and return the count removed.

    The configured schema is set on the session connection explicitly (the async
    engine already sets it via ``server_settings``, but this makes the intent
    unambiguous and survives any future engine-level change).
    """
    cfg = get_config()
    schema = cfg.postgresql.schema_
    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)
    try:
        async with session_factory() as session:
            await session.execute(text(f"SET search_path TO {schema}, public"))
            match_count = (
                await session.execute(_COUNT_DEAD_STOP_ALIASES_SQL)
            ).scalar_one()
            logger.info(
                "Dead X-form stop aliases matching {}: {}",
                _DEAD_STOP_ALIAS_REGEX,
                match_count,
            )
            if match_count == 0:
                logger.info("No dead X-form stop aliases to delete; cleanup is a no-op")
                return 0
            result = await session.execute(_DELETE_DEAD_STOP_ALIASES_SQL)
            deleted = result.rowcount or 0
            await session.commit()
            logger.info("Deleted {} dead X-form stop aliases", deleted)
            return deleted
    finally:
        await engine.dispose()


async def main() -> None:
    """Run the re-import (unless --skip-import) then cleanup (unless --skip-cleanup)."""
    _configure_logger()
    args = parse_args()
    started = time.perf_counter()

    if not args.skip_import:
        await _run_import(args)
    else:
        logger.info("Skipping terminology re-import (--skip-import)")

    if not args.skip_cleanup:
        await _cleanup_dead_stop_aliases()
    else:
        logger.info("Skipping dead-alias cleanup (--skip-cleanup)")

    logger.info("reindex_clinvar_aliases.py finished in {:.2f}s", time.perf_counter() - started)


if __name__ == "__main__":
    asyncio.run(main())
