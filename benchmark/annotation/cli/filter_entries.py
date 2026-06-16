"""CLI: Filter draft entries — keep only articles with genetic variant info, detect language."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from src.config import get_config
from src.manifest import load_manifest, save_manifest, update_status
from src.models import DraftMeta

_SYSTEM_PROMPT = """\
You are a medical genetics literature classifier. Analyze the article and answer:

1. Does this article report **specific genetic variants** (HGVS notation, mutation names, \
amino acid changes, nucleotide changes) observed in **human patients or human-derived samples**? \
General disease background descriptions, mouse/animal model studies without patient data, \
review articles, and basic science papers do NOT count.

2. What is the **primary language** of the article text?

Respond with a JSON object:
{
  "has_variant_info": true/false,
  "article_type": "case_report" | "case_series" | "cohort_study" | "functional_study" | "review" | "basic_science" | "other",
  "language": "en" | "zh" | "ja" | "ko" | "fr" | "de" | "es" | "pt" | "ru" | "it" | "tr" | "other",
  "reason": "brief explanation"
}
"""


async def _classify_article(
    source_md: str,
    entry_id: str,
    llm_client,
    fallback_client,
) -> dict | None:
    from langchain_core.messages import HumanMessage, SystemMessage

    truncated = source_md[:15000]
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Article text:\n\n{truncated}"),
    ]

    for client in [llm_client, fallback_client]:
        if client is None:
            continue
        try:
            resp = await client.ainvoke(messages)
            import re
            match = re.search(r"\{[\s\S]*?\}", resp.content)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.warning("LLM failed for {}: {}", entry_id, e)

    return None


async def main_async() -> None:
    parser = argparse.ArgumentParser(
        description="Filter drafts: keep only articles with genetic variant info, detect language"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print results without modifying files")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--entries", nargs="+", help="Specific entry IDs")
    args = parser.parse_args()

    cfg = get_config()
    draft_dir = cfg.resolved_paths["draft_dir"]
    manifest_path = cfg.resolved_paths["ground_truth_dir"] / "manifest.json"
    manifest = load_manifest(manifest_path)

    llm = cfg.build_llm_client()
    fallback = cfg.build_fallback_client()

    entries: list[tuple[Path, str]] = []
    for d in sorted(draft_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith("rett_"):
            continue
        if args.entries and d.name not in args.entries:
            continue
        if not (d / "source.md").exists():
            continue
        entries.append((d, d.name))

    logger.info("Classifying {} entries", len(entries))
    sem = asyncio.Semaphore(args.concurrency)

    kept = 0
    removed = 0
    failed = 0

    async def _process(entry_dir: Path, entry_id: str) -> None:
        nonlocal kept, removed, failed

        source_md = (entry_dir / "source.md").read_text(encoding="utf-8")
        async with sem:
            result = await _classify_article(source_md, entry_id, llm, fallback)

        if result is None:
            logger.error("Classification failed for {}", entry_id)
            failed += 1
            return

        has_variant = result.get("has_variant_info", False)
        article_type = result.get("article_type", "unknown")
        language = result.get("language", "unknown")
        reason = result.get("reason", "")

        # Update meta.json with classification
        meta_path = entry_dir / "meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = DraftMeta(**json.load(f))
        else:
            meta = DraftMeta(entry_id=entry_id, pdf_path="", language="")

        meta.language = language

        if has_variant:
            meta.review_notes = f"[{article_type}] {reason}"
            kept += 1
            status_icon = "KEEP"
        else:
            meta.review_status = "rejected"
            meta.rejection_reason = f"[{article_type}] {reason}"
            removed += 1
            status_icon = "DROP"

        if not args.dry_run:
            meta_path.write_text(
                json.dumps(meta.model_dump(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            if not has_variant:
                update_status(manifest, entry_id, "rejected")

        logger.info("[{}] {} | {} | {} | {}", status_icon, entry_id, language, article_type, reason)

    tasks = [_process(d, eid) for d, eid in entries]
    await asyncio.gather(*tasks)

    if not args.dry_run:
        save_manifest(manifest, manifest_path)

    logger.info(
        "Done: {} kept, {} removed, {} failed{}",
        kept, removed, failed,
        " (dry-run, no changes)" if args.dry_run else "",
    )


if __name__ == "__main__":
    asyncio.run(main_async())
