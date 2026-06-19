"""CLI: catalog-driven reannotation for Rett ground-truth entries."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from src.annotator import annotate_article
from src.catalog_annotation import load_literature_catalog
from src.config import Config, get_config
from src.review import generate_selection_json

_RETT_ROOT = Path(__file__).resolve().parent.parent
_LEGACY_ROOT = _RETT_ROOT.parents[1] / "annotation"


@dataclass(frozen=True)
class ReannotationRow:
    """Result for one reannotated Rett entry."""

    entry_id: str
    language: str
    model: str
    source_path: str
    expected_fields: int
    variants: int
    status: str
    error: str = ""


@dataclass(frozen=True)
class ReannotationReport:
    """Summary of one catalog-driven reannotation run."""

    model: str
    write: bool
    started_at: str
    finished_at: str
    catalog_field_count: int
    rows: list[ReannotationRow] = field(default_factory=list)


@dataclass(frozen=True)
class EntryInput:
    """Input material for one Rett reannotation entry."""

    entry_id: str
    language: str
    source_path: Path
    source_text: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _selected_entry_ids(ground_truth_dir: Path, requested: list[str], limit: int) -> list[str]:
    if requested:
        entry_ids = requested
    else:
        selection_path = ground_truth_dir / "selection.json"
        selection = _load_json(selection_path) if selection_path.exists() else []
        if isinstance(selection, list):
            entry_ids = [str(item["entry_id"]) for item in selection if isinstance(item, dict) and item.get("entry_id")]
        else:
            entry_ids = []
        if not entry_ids:
            entry_ids = sorted(path.name for path in ground_truth_dir.glob("rett_*") if path.is_dir())
    return entry_ids[:limit] if limit else entry_ids


def _entry_language(ground_truth_dir: Path, entry_id: str) -> str:
    meta_path = ground_truth_dir / entry_id / "meta.json"
    if meta_path.exists():
        meta = _load_json(meta_path)
        if isinstance(meta, dict) and meta.get("language"):
            return str(meta["language"])
    expected_path = ground_truth_dir / entry_id / "expected.json"
    if expected_path.exists():
        expected = _load_json(expected_path)
        if isinstance(expected, dict) and expected.get("source_language"):
            return str(expected["source_language"])
    return "en"


def _source_path(ground_truth_dir: Path, entry_id: str) -> Path | None:
    candidates = (
        ground_truth_dir / entry_id / "source.md",
        _LEGACY_ROOT / "ground_truth" / entry_id / "source.md",
        _LEGACY_ROOT / "approved" / entry_id / "source.md",
        _LEGACY_ROOT / "draft" / entry_id / "source.md",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_entry(ground_truth_dir: Path, entry_id: str) -> EntryInput | None:
    source_path = _source_path(ground_truth_dir, entry_id)
    if source_path is None:
        return None
    return EntryInput(
        entry_id=entry_id,
        language=_entry_language(ground_truth_dir, entry_id),
        source_path=source_path,
        source_text=source_path.read_text(encoding="utf-8"),
    )


def _write_expected_to_dirs(config: Config, entry_id: str, payload: str, source: EntryInput, model: str) -> None:
    target_dirs = [config.resolved_paths["ground_truth_dir"] / entry_id]
    for key in ("approved_dir", "draft_dir"):
        target_dir = config.resolved_paths[key] / entry_id
        if target_dir.exists():
            target_dirs.append(target_dir)

    for target_dir in target_dirs:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "expected.json").write_text(payload, encoding="utf-8")
        source_out = target_dir / "source.md"
        if not source_out.exists():
            source_out.write_text(source.source_text, encoding="utf-8")
        _update_meta(target_dir / "meta.json", model)


def _update_meta(meta_path: Path, model: str) -> None:
    if not meta_path.exists():
        return
    meta = _load_json(meta_path)
    if not isinstance(meta, dict):
        return
    meta["llm_model"] = model
    meta["generated_at"] = _now_iso()
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


async def _annotate_one(
    config: Config,
    source: EntryInput,
    model: str,
    write: bool,
    semaphore: asyncio.Semaphore,
) -> ReannotationRow:
    async with semaphore:
        logger.info("Annotating {} with {}", source.entry_id, model)
        try:
            expected = await annotate_article(source.source_text, source.entry_id, source.language, config)
        except Exception as exc:  # noqa: BLE001 - keep batch running and report per-entry failure.
            logger.exception("Failed {}", source.entry_id)
            return ReannotationRow(
                entry_id=source.entry_id,
                language=source.language,
                model=model,
                source_path=str(source.source_path),
                expected_fields=0,
                variants=0,
                status="failed",
                error=str(exc),
            )
        if not expected.expected_evidence:
            error = "empty annotation: no expected_evidence fields returned"
            logger.warning("Failed {}: {}", source.entry_id, error)
            return ReannotationRow(
                entry_id=source.entry_id,
                language=source.language,
                model=model,
                source_path=str(source.source_path),
                expected_fields=0,
                variants=0,
                status="failed",
                error=error,
            )

        payload = expected.model_dump_json(indent=2)
        if write:
            _write_expected_to_dirs(config, source.entry_id, payload, source, model)
        return ReannotationRow(
            entry_id=source.entry_id,
            language=source.language,
            model=model,
            source_path=str(source.source_path),
            expected_fields=len(expected.expected_evidence),
            variants=len(expected.variants),
            status="written" if write else "scanned",
        )


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="Catalog-driven Rett reannotation")
    parser.add_argument("--model", required=True, help="LLM model name")
    parser.add_argument("--entries", nargs="*", default=[], help="Specific Rett entry IDs")
    parser.add_argument("--limit", type=int, default=0, help="Limit entries")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrent LLM calls")
    parser.add_argument("--write", action="store_true", help="Persist expected.json outputs")
    parser.add_argument("--report", type=Path, default=None, help="Report JSON path")
    parser.add_argument("--max-tokens", type=int, default=0, help="Override max output tokens")
    parser.add_argument("--chunk-size", type=int, default=0, help="Override input chunk size")
    args = parser.parse_args()

    config = get_config()
    config.llm.model = args.model
    config.llm.timeout = max(config.llm.timeout, 240)
    if args.max_tokens:
        config.llm.max_tokens = args.max_tokens
    if args.chunk_size:
        config.annotation.chunk_size = args.chunk_size
    fields = load_literature_catalog()
    ground_truth_dir = config.resolved_paths["ground_truth_dir"]
    entry_ids = _selected_entry_ids(ground_truth_dir, args.entries, args.limit)
    sources = [_load_entry(ground_truth_dir, entry_id) for entry_id in entry_ids]
    missing = [entry_id for entry_id, source in zip(entry_ids, sources, strict=True) if source is None]
    if missing:
        logger.warning("Missing source.md for {}", ", ".join(missing))
    loaded_sources = [source for source in sources if source is not None]

    started_at = _now_iso()
    semaphore = asyncio.Semaphore(args.concurrency)
    rows = await asyncio.gather(
        *[
            _annotate_one(config, source, args.model, args.write, semaphore)
            for source in loaded_sources
        ]
    )
    finished_at = _now_iso()

    if args.write:
        generate_selection_json(ground_truth_dir)

    report = ReannotationReport(
        model=args.model,
        write=args.write,
        started_at=started_at,
        finished_at=finished_at,
        catalog_field_count=len(fields),
        rows=list(rows),
    )
    report_path = args.report or (
        _RETT_ROOT / "reports" / f"catalog_reannotation_{args.model}_{started_at.replace(':', '').replace('+', 'Z')}.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "model": report.model,
                "write": report.write,
                "started_at": report.started_at,
                "finished_at": report.finished_at,
                "catalog_field_count": report.catalog_field_count,
                "rows": [row.__dict__ for row in report.rows],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ok = sum(1 for row in rows if row.status in {"written", "scanned"})
    failed = sum(1 for row in rows if row.status == "failed")
    logger.info("Done: {} ok, {} failed, report={}", ok, failed, report_path)


if __name__ == "__main__":
    asyncio.run(main_async())
