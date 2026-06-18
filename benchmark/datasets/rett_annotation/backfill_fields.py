"""Backfill expanded fields (13→35) into existing ground truth entries.

Reads source.md from each ground truth entry, re-annotates with the expanded
LLM prompt, and merges new fields into expected.json while preserving existing
human-reviewed values.

Usage:
    uv run python backfill_fields.py [--dry-run] [--entry rett_001]
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from loguru import logger

from src.annotator import annotate_article
from src.config import get_config
from src.models import ExpectedEvidenceField, RettExpectedJson


def _load_existing(entry_dir: Path) -> dict:
    """Load existing expected.json as raw dict."""
    path = entry_dir / "expected.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _merge_evidence(
    existing_fields: list[dict],
    new_fields: list[ExpectedEvidenceField],
) -> list[dict]:
    """Merge new evidence fields into existing ones.

    Strategy:
    - Existing fields are kept as-is (human-reviewed).
    - New fields are added only if their field_id doesn't already exist.
    - This preserves all human corrections from prior review cycles.
    """
    existing_ids = {f["field_id"] for f in existing_fields}
    merged = list(existing_fields)

    added = 0
    for nf in new_fields:
        if nf.field_id not in existing_ids:
            merged.append(nf.model_dump())
            existing_ids.add(nf.field_id)
            added += 1

    return merged, added


def _update_evaluation_config(existing_config: dict) -> dict:
    """Replace evaluation_config with the expanded version."""
    default = RettExpectedJson.model_fields["evaluation_config"].default_factory()
    return default


async def backfill_entry(
    entry_id: str,
    config,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Backfill a single ground truth entry. Returns (existing_count, added_count)."""
    gt_dir = config.resolved_paths["ground_truth_dir"]
    entry_dir = gt_dir / entry_id

    if not entry_dir.exists():
        logger.warning("Entry dir not found: {}", entry_dir)
        return 0, 0

    # Load source markdown
    source_md_path = entry_dir / "source.md"
    if not source_md_path.exists():
        logger.warning("source.md not found for {}", entry_id)
        return 0, 0

    source_md = source_md_path.read_text(encoding="utf-8")

    # Load existing expected.json
    existing = _load_existing(entry_dir)
    existing_fields = existing.get("expected_evidence", [])
    existing_count = len(existing_fields)

    # Read language from meta.json or manifest
    meta_path = entry_dir / "meta.json"
    language = "en"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        language = meta.get("language", "en")

    # Re-annotate with expanded prompt
    logger.info("Annotating {} (lang={}, md={} chars)...", entry_id, language, len(source_md))
    new_result = await annotate_article(source_md, entry_id, language, config)

    # Merge evidence fields
    merged_fields, added_count = _merge_evidence(existing_fields, new_result.expected_evidence)

    # Update evaluation_config
    new_eval_config = _update_evaluation_config(existing.get("evaluation_config", {}))

    # Update variants with new fields
    new_variants = [v.model_dump() for v in new_result.variants]

    if dry_run:
        logger.info(
            "[DRY RUN] {}: existing={} new_fields={} total_after_merge={}",
            entry_id, existing_count, added_count, len(merged_fields),
        )
        # Show which new field_ids would be added
        existing_ids = {f["field_id"] for f in existing_fields}
        for nf in new_result.expected_evidence:
            if nf.field_id not in existing_ids:
                logger.info("  + {} = {}", nf.field_id, nf.value[:60])
        return existing_count, added_count

    # Update the raw dict and save
    existing["expected_evidence"] = merged_fields
    existing["evaluation_config"] = new_eval_config
    existing["variants"] = new_variants

    output_path = entry_dir / "expected.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    logger.info(
        "✓ {}: {} existing + {} new = {} total fields",
        entry_id, existing_count, added_count, len(merged_fields),
    )
    return existing_count, added_count


async def main():
    dry_run = "--dry-run" in sys.argv
    single_entry = None
    for arg in sys.argv[1:]:
        if arg.startswith("--entry"):
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv):
                single_entry = sys.argv[idx + 1]

    config = get_config()
    gt_dir = config.resolved_paths["ground_truth_dir"]

    if single_entry:
        entries = [single_entry]
    else:
        entries = sorted(
            d.name for d in gt_dir.iterdir()
            if d.is_dir() and (d / "expected.json").exists()
        )

    logger.info("Backfilling {} entries (dry_run={})", len(entries), dry_run)

    total_existing = 0
    total_added = 0

    for entry_id in entries:
        try:
            existing, added = await backfill_entry(entry_id, config, dry_run)
            total_existing += existing
            total_added += added
        except Exception as e:
            logger.error("Failed {}: {}", entry_id, e)

    logger.info(
        "Done. {} entries: {} existing fields, {} new fields added.",
        len(entries), total_existing, total_added,
    )


if __name__ == "__main__":
    asyncio.run(main())
