"""CLI: Generate AI annotation drafts from parsed source files."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from src.annotator import annotate_article
from src.config import get_config
from src.manifest import load_manifest, save_manifest, update_status
from src.models import DraftMeta


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _process_entry(
    entry_dir: Path,
    entry_id: str,
    language: str,
    config,
    sem: asyncio.Semaphore,
) -> bool:
    source_path = entry_dir / "source.md"
    if not source_path.exists():
        logger.warning("No source.md for {}, skipping", entry_id)
        return False

    async with sem:
        logger.info("Annotating {}", entry_id)
        try:
            source_md = source_path.read_text(encoding="utf-8")
            result = await annotate_article(source_md, entry_id, language, config)

            expected_path = entry_dir / "expected.json"
            expected_path.write_text(
                result.model_dump_json(indent=2), encoding="utf-8"
            )

            meta_path = entry_dir / "meta.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    meta = DraftMeta(**json.load(f))
                meta.annotation_status = "generated"
                meta.generated_at = _now_iso()
                meta.llm_model = config.llm.model
                meta.variant_count = len(result.variants)
                meta.clinical_feature_count = sum(
                    1 for f in result.expected_evidence if f.field_id.startswith("B.")
                )
                meta_path.write_text(
                    json.dumps(meta.model_dump(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

            logger.info("Generated draft for {} ({} variants, {} clinical fields)",
                        entry_id, meta.variant_count, meta.clinical_feature_count)
            return True
        except Exception as e:
            logger.error("Failed to annotate {}: {}", entry_id, e)
            if meta_path.exists():
                with open(meta_path) as f:
                    meta = DraftMeta(**json.load(f))
                meta.annotation_status = "failed"
                meta_path.write_text(
                    json.dumps(meta.model_dump(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            return False


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="Generate AI annotation drafts")
    parser.add_argument("--limit", type=int, default=0, help="Max entries to process")
    parser.add_argument("--entries", nargs="+", help="Specific entry IDs")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--force", action="store_true", help="Re-generate even if expected.json exists")
    args = parser.parse_args()

    cfg = get_config()
    draft_dir = cfg.resolved_paths["draft_dir"]
    manifest_path = draft_dir.parent / "ground_truth" / "manifest.json"
    manifest = load_manifest(manifest_path)

    entry_dirs: list[tuple[Path, str, str]] = []
    for d in sorted(draft_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith("rett_"):
            continue
        entry_id = d.name
        if args.entries and entry_id not in args.entries:
            continue
        if not args.force and (d / "expected.json").exists():
            logger.info("Skipping {} (already generated)", entry_id)
            continue

        meta_path = d / "meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = DraftMeta(**json.load(f))
            language = meta.language
        else:
            language = "en"

        entry_dirs.append((d, entry_id, language))

    if args.limit:
        entry_dirs = entry_dirs[: args.limit]

    logger.info("Processing {} entries", len(entry_dirs))
    sem = asyncio.Semaphore(args.concurrency)

    tasks = [
        _process_entry(d, eid, lang, cfg, sem)
        for d, eid, lang in entry_dirs
    ]
    results = await asyncio.gather(*tasks)

    success = sum(1 for r in results if r)
    for d, entry_id, _ in entry_dirs:
        status = "draft" if (d / "expected.json").exists() else "parsed"
        update_status(manifest, entry_id, status, str(d))

    save_manifest(manifest, manifest_path)
    logger.info("Done: {} generated, {} failed", success, len(results) - success)


if __name__ == "__main__":
    asyncio.run(main_async())
