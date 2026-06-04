"""Rett syndrome literature acquisition benchmark.

Usage:
    uv run python benchmark/literature_acquisition/rett_download.py [--dry-run] [--query-file FILE]

All acquisition logic delegates to online_acquisition_workflow (API + Firecrawl).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import (
    online_acquisition_workflow,
)

MODULE_DIR = Path(__file__).resolve().parent
QUERY_FILE = MODULE_DIR / "rett_syndrome_queries.txt"
OUTPUT_FILE = MODULE_DIR / "downloads" / "rett_syndrome_candidates.jsonl"
REPORT_FILE = MODULE_DIR / "downloads" / "rett_syndrome_report.json"
LOG_DIR = MODULE_DIR / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logger.add(str(LOG_DIR / "rett_download.log"), rotation="5 MB", retention=3, encoding="utf-8")


@dataclass
class DownloadRecord:
    query: str
    source: str
    title: str
    doi: str
    url: str
    success: bool
    file_path: str = ""
    file_size: int = 0
    error: str = ""


@dataclass
class DownloadStats:
    total_queries: int = 0
    total_candidates: int = 0
    total_downloaded: int = 0
    by_source: Dict[str, int] = field(default_factory=dict)
    elapsed_sec: float = 0.0
    records: List[Dict[str, Any]] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# Query management
# ═══════════════════════════════════════════════════════════════════

def load_queries(path: Path) -> List[str]:
    """Load queries from file (one per line, skip blanks and # comments)."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


def save_queries(path: Path, queries: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(queries) + "\n", encoding="utf-8")


DEFAULT_SEED_QUERIES = [
    "Rett syndrome MECP2 mutation case report",
    "Rett syndrome gene sequencing",
    "Rett syndrome functional study MECP2",
    "Rett syndrome CDKL5 mutation",
    "Rett syndrome FOXG1 clinical case",
    "Rett syndrome whole exome sequencing",
    "Rett syndrome genotype phenotype correlation",
    "Rett syndrome novel mutation",
    "Rett syndrome atypical case report",
    "Rett syndrome male case report",
    "Rett syndrome neurodevelopmental",
    "Rett syndrome EEG clinical",
    "Rett syndrome呼吸异常",
    "Rett综合征 基因突变",
    "Rett syndrome遺伝子変異",
    "Rett síndrome mutación genética",
    "Rett syndrome targeted sequencing",
    "Rett syndrome CRISPR model",
    "Rett syndrome mouse model functional",
    "Rett syndrome protein expression",
    "MECP2 duplication syndrome case report",
    "Rett syndrome brain derived neurotrophic factor",
    "Rett syndrome methyl CpG binding protein 2",
    "Rett syndrome临床特征",
    "Rett syndrome natural history study",
]


# ═══════════════════════════════════════════════════════════════════
# Seed queries subcommand
# ═══════════════════════════════════════════════════════════════════

def cmd_seed_queries(force: bool = False) -> None:
    if QUERY_FILE.exists() and not force:
        logger.info(f"Query file already exists: {QUERY_FILE}")
        return
    save_queries(QUERY_FILE, DEFAULT_SEED_QUERIES)
    logger.info(f"Wrote {len(DEFAULT_SEED_QUERIES)} seed queries → {QUERY_FILE}")


# ═══════════════════════════════════════════════════════════════════
# Download — delegates to online_acquisition_workflow
# ═══════════════════════════════════════════════════════════════════

async def _run_one_query(
    query: str,
    download_path: str,
    *,
    dry_run: bool,
) -> Dict[str, Any]:
    """Run a single query through the module's workflow."""
    action = "search" if dry_run else "download"
    payload: Dict[str, Any] = {
        "action": action,
        "query": query,
        "limit": 10,
        "download_path": download_path,
    }

    try:
        result = await asyncio.wait_for(
            online_acquisition_workflow(payload),
            timeout=120,
        )
    except asyncio.TimeoutError:
        return {"query": query, "success": False, "error": "workflow_timeout",
                "candidates": [], "downloads": []}
    except Exception as exc:
        return {"query": query, "success": False, "error": str(exc)[:200],
                "candidates": [], "downloads": []}

    return {"query": query, **result}


async def cmd_download(
    queries: List[str],
    *,
    dry_run: bool = False,
    download_dir: Optional[str] = None,
) -> None:
    stats = DownloadStats()
    stats.total_queries = len(queries)

    if dry_run:
        logger.info("Dry-run mode enabled. Candidates will not be downloaded.")
    else:
        logger.info("Download mode enabled.")

    out_dir = Path(download_dir) if download_dir else MODULE_DIR / "downloads" / "rett_syndrome"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting Rett syndrome literature benchmark")
    logger.info(f"Queries: {len(queries)}, Download dir: {out_dir}")

    with open(OUTPUT_FILE, "a", encoding="utf-8") as out_f:
        for i, query in enumerate(queries, 1):
            logger.info(f"[{i}/{len(queries)}] query: {query}")
            stats.total_queries = i

            entry = await _run_one_query(query, str(out_dir), dry_run=dry_run)

            # Collect candidates (from search-only or full workflow)
            candidates = entry.get("candidate_links", [])
            items = entry.get("items", [])
            downloads_list = entry.get("downloads", [])
            route_info = entry.get("route", {})
            success = entry.get("success", False)

            stats.total_candidates += len(candidates)

            if dry_run:
                # Write each candidate as a separate JSONL record
                for cand in candidates:
                    cand["query"] = query
                    out_f.write(json.dumps(cand, ensure_ascii=False) + "\n")
                stats.records.append(entry)

                if success:
                    logger.info(f"  Found {len(candidates)} candidates via {route_info.get('used', '?')}")
                else:
                    warns = entry.get("warnings", [])
                    logger.info(f"  No candidates: {warns}")
            else:
                # Actual download mode
                for dl in downloads_list:
                    fp = dl.get("file_path") or ""
                    if not fp or not Path(fp).exists():
                        continue

                    dest = Path(fp)
                    # Match title/doi from items
                    dl_doi = (dl.get("doi") or "").strip()
                    title = ""
                    doi = ""
                    for item in items:
                        item_doi = (item.get("doi") or "").strip()
                        if item_doi and item_doi == dl_doi:
                            title = item.get("title") or ""
                            doi = item_doi
                            break
                    if not title and items:
                        title = items[0].get("title") or ""
                    if not doi:
                        doi = dl_doi

                    source = dl.get("source", route_info.get("used", "workflow"))

                    rec = DownloadRecord(
                        query=query, source=source, title=title, doi=doi,
                        url=dl.get("url") or "", success=True,
                        file_path=str(dest), file_size=dest.stat().st_size,
                    )
                    stats.records.append(asdict(rec))
                    stats.total_downloaded += 1
                    stats.by_source[source] = stats.by_source.get(source, 0) + 1
                    logger.info(f"  Downloaded: {title[:60]} [{source}] {dest.stat().st_size // 1024}KB")

                if not downloads_list:
                    warns = entry.get("warnings", [])
                    logger.info(f"  No downloads: {warns}")
                    stats.records.append(entry)

    stats.elapsed_sec = round(time.monotonic(), 1)

    with open(REPORT_FILE, "w", encoding="utf-8") as rf:
        json.dump(asdict(stats), rf, indent=2, ensure_ascii=False)
    logger.info(f"Report: {REPORT_FILE}")
    logger.info(f"Candidates: {stats.total_candidates}, Downloaded: {stats.total_downloaded}")


# ═══════════════════════════════════════════════════════════════════
# Analyze mode
# ═══════════════════════════════════════════════════════════════════

def _bar(count: int, total: int, width: int = 30) -> str:
    filled = int(count / max(total, 1) * width)
    return "█" * filled + "░" * (width - filled)


def cmd_analyze(report_path: Optional[Path] = None, llm_classify: bool = False) -> None:
    path = report_path or REPORT_FILE
    if not path.exists():
        logger.error(f"Report file not found: {path}")
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    records = data.get("records", [])
    total_queries = data.get("total_queries", 0)
    total_candidates = data.get("total_candidates", 0)
    total_downloaded = data.get("total_downloaded", 0)
    elapsed = data.get("elapsed_sec", 0)
    by_source = data.get("by_source", {})

    ok_records = [r for r in records if r.get("success") or r.get("file_path")]

    print("\n" + "=" * 64)
    print("  RETT SYNDROME LITERATURE BENCHMARK — REPORT")
    print("=" * 64)
    print(f"  Queries:     {total_queries}")
    print(f"  Candidates:  {total_candidates}")
    print(f"  Downloaded:  {total_downloaded}")
    print(f"  Elapsed:     {elapsed:.1f}s")

    # Source distribution
    if by_source:
        print(f"\n{'─' * 64}")
        print("  BY SOURCE")
        print(f"{'─' * 64}")
        for src, cnt in sorted(by_source.items(), key=lambda x: x[1], reverse=True):
            print(f"  {src:<24} {cnt:>4}  {_bar(cnt, max(total_downloaded, 1))}")

    # Per-query summary
    print(f"\n{'─' * 64}")
    print("  PER-QUERY CANDIDATE COUNTS")
    print(f"{'─' * 64}")
    for rec in records:
        q = rec.get("query", "")[:55]
        n_cand = len(rec.get("candidates", rec.get("candidate_links", [])))
        n_dl = len(rec.get("downloads", []))
        ok = "✓" if rec.get("success") else "✗"
        print(f"  {ok} [{n_cand:>2} cand, {n_dl:>2} dl]  {q}")

    # Literature type distribution
    type_counts: Dict[str, int] = {}
    for rec in ok_records:
        for item in rec.get("items", []):
            lt = item.get("literature_type") or "unclassified"
            type_counts[lt] = type_counts.get(lt, 0) + 1

    if type_counts:
        print(f"\n{'─' * 64}")
        print("  LITERATURE TYPE DISTRIBUTION")
        print(f"{'─' * 64}")
        for lt, cnt in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {lt:<18} {cnt:>4}  {_bar(cnt, sum(type_counts.values()))}")

    if llm_classify:
        logger.info("LLM domain classification: run benchmark.py analyze --llm-classify on the download report instead")

    # Write annotated report
    data["analysis_summary"] = {
        "by_source": by_source,
        "literature_type_distribution": type_counts,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 64}")


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Rett syndrome literature acquisition benchmark")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed-queries", help="Generate seed query file")
    p_seed.add_argument("--force", action="store_true", help="Overwrite existing query file")

    p_dl = sub.add_parser("download", help="Run literature download benchmark")
    p_dl.add_argument("--dry-run", action="store_true",
                      help="Search only, do not download files")
    p_dl.add_argument("--query-file", type=str, default=str(QUERY_FILE),
                      help="Path to query file (one query per line)")
    p_dl.add_argument("--download-dir", type=str, default=None,
                      help="Override download directory")

    p_an = sub.add_parser("analyze", help="Print analysis of benchmark report")
    p_an.add_argument("path", nargs="?", help="Path to report JSON (default: rett_syndrome_report.json)")
    p_an.add_argument("--llm-classify", action="store_true",
                      help="Classify medical domain via LLM (delegates to benchmark.py)")

    args = parser.parse_args()

    if args.cmd == "seed-queries":
        cmd_seed_queries(args.force)
    elif args.cmd == "download":
        qfile = Path(args.query_file)
        if not qfile.exists():
            logger.info("Query file not found. Generating seed queries...")
            cmd_seed_queries(force=False)
        queries = load_queries(qfile)
        if not queries:
            logger.error(f"No queries found in {qfile}")
            sys.exit(1)
        asyncio.run(cmd_download(queries, dry_run=args.dry_run, download_dir=args.download_dir))
    elif args.cmd == "analyze":
        cmd_analyze(Path(args.path) if args.path else None, llm_classify=args.llm_classify)


if __name__ == "__main__":
    main()
