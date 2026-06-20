"""Rett syndrome literature acquisition benchmark.

Usage:
    uv run python benchmark/literature_acquisition/rett_download.py download [--config rett_config.json] [--dry-run]
    uv run python benchmark/literature_acquisition/rett_download.py download [--query-file queries.txt] [--dry-run]
    uv run python benchmark/literature_acquisition/rett_download.py analyze [report.json]
    uv run python benchmark/literature_acquisition/rett_download.py seed-queries [--force]
    uv run python benchmark/literature_acquisition/rett_download.py cleanup [--download-dir DIR] [--dry-run]
    uv run python benchmark/literature_acquisition/rett_download.py rename [--download-dir DIR] [--dry-run]

All acquisition logic delegates to online_acquisition_workflow (API + Firecrawl).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import fitz
from loguru import logger
from openai import AsyncOpenAI
from benchmark.config.defaults import DEFAULT_SEED_QUERIES, RETT_CONFIG_PATH

from src.core.config import get_config
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.relevance_gate import (
    RelevanceGateResult,
    run_relevance_gate,
)

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import (
    multilingual_acquisition_workflow,
    online_acquisition_workflow,
)

MODULE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = RETT_CONFIG_PATH  # Ansible-deployed to benchmark/data/inputs/literature_acquisition/
QUERY_FILE = MODULE_DIR / "rett_syndrome_queries.txt"
OUTPUT_FILE = MODULE_DIR / "downloads" / "rett_syndrome_candidates.jsonl"
REPORT_FILE = MODULE_DIR / "downloads" / "rett_syndrome_report.json"
LOG_DIR = MODULE_DIR / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logger.add(str(LOG_DIR / "rett_download.log"), rotation="5 MB", retention=3, encoding="utf-8")


def setup_logging(log_dir: Path = LOG_DIR, level: str = "INFO") -> None:
    """Configure loguru: console + rotating file, suppress noisy libraries."""
    logger.remove()
    logger.add(sys.stderr, level=level, format="{time:YYYY-MM-DD HH:mm:ss} {level: <8} {message}")
    logger.add(
        str(log_dir / "rett_download.log"),
        rotation="5 MB", retention=3, encoding="utf-8", level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} {level: <8} {message}",
    )
    import logging as _pylogging
    _pylogging.getLogger("httpx").setLevel(_pylogging.WARNING)
    _pylogging.getLogger("urllib3").setLevel(_pylogging.WARNING)
    _pylogging.getLogger("openai").setLevel(_pylogging.WARNING)


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
    total_deduped: int = 0
    by_source: Dict[str, int] = field(default_factory=dict)
    elapsed_sec: float = 0.0
    records: List[Dict[str, Any]] = field(default_factory=list)


class DedupTracker:
    """Track downloaded files by DOI and content hash to avoid duplicates."""

    def __init__(self) -> None:
        self._seen_dois: Set[str] = set()
        self._seen_hashes: Set[str] = set()

    def is_duplicate(self, doi: str, file_path: Path) -> bool:
        """Return True if this file (by DOI or content hash) was already seen."""
        norm_doi = doi.strip().lower()
        if norm_doi and norm_doi in self._seen_dois:
            return True
        if file_path.exists():
            h = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if h in self._seen_hashes:
                return True
        return False

    def record(self, doi: str, file_path: Path) -> None:
        """Register a file as seen."""
        norm_doi = doi.strip().lower()
        if norm_doi:
            self._seen_dois.add(norm_doi)
        if file_path.exists():
            h = hashlib.sha256(file_path.read_bytes()).hexdigest()
            self._seen_hashes.add(h)


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


@dataclass
class ConfigQuery:
    """A single query entry parsed from the JSON config."""
    text: str
    lang_code: str
    lang_name: str


@dataclass
class ConfigData:
    """Parsed config: flattened queries + search parameters."""
    queries: List[ConfigQuery]
    max_results: int
    concurrency: int
    download_dir: str
    literature_types: List[str]
    task_name: str
    target_per_lang: Dict[str, int]


def load_config(path: Path) -> ConfigData:
    """Load rett_config.json — flatten per-language queries into a single list.

    Config structure::

        {
          "candidate_limit": 10,
          "download_dir": "downloads/rett",
          "literature_types": ["case_report"],
          "concurrency": 3,
          "target_per_lang": { "zh": 10, "en": 10, ... },
          "languages": {
            "zh": { "name": "Chinese", "queries": ["...", ...] },
            "en": { "name": "English", "queries": ["...", ...] },
            ...
          }
        }
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    max_results = raw.get("candidate_limit", 10)
    concurrency = raw.get("concurrency", 3)
    download_dir = raw.get("download_dir", "downloads/rett")
    literature_types = raw.get("literature_types", ["case_report"])
    target_per_lang = raw.get("target_per_lang", {})
    task_name = raw.get("disease", "rett_syndrome_acquisition")

    flat: List[ConfigQuery] = []
    languages_section = raw.get("languages", {})
    for lang_code, lang_cfg in languages_section.items():
        lang_name = lang_cfg.get("name", lang_code)
        for text in lang_cfg.get("queries", []):
            text = text.strip()
            if text:
                flat.append(ConfigQuery(text=text, lang_code=lang_code, lang_name=lang_name))

    return ConfigData(
        queries=flat,
        max_results=max_results,
        concurrency=concurrency,
        download_dir=download_dir,
        literature_types=literature_types,
        task_name=task_name,
        target_per_lang=target_per_lang,
    )


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
    limit: int = 10,
    language: str = "auto",
    literature_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run a single query through the module's workflow."""
    action = "search" if dry_run else "download"
    payload: Dict[str, Any] = {
        "action": action,
        "query": query,
        "limit": limit,
        "language": language,
        "download_path": download_path,
        # Disable LLM relevance gate — metadata classifier + candidate
        # filtering already provide sufficient type/quality control.
        # The gate was rejecting valid case reports because the LLM
        # considered them not specific enough to the search query.
        "relevance_gate": False,
    }
    if literature_types:
        payload["literature_types"] = literature_types

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
    config: Optional[ConfigData] = None,
) -> None:
    stats = DownloadStats()
    stats.total_queries = len(queries)
    dedup = DedupTracker()

    if dry_run:
        logger.info("Dry-run mode enabled. Candidates will not be downloaded.")
    else:
        logger.info("Download mode enabled.")

    out_dir = Path(download_dir) if download_dir else (
        MODULE_DIR / config.download_dir if config else MODULE_DIR / "downloads" / "rett_syndrome"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    limit = config.max_results if config else 10
    literature_types = config.literature_types if config else []

    # Build (query_text, lang_code, lang_name) list
    if config:
        entries = [(cq.text, cq.lang_code, cq.lang_name) for cq in config.queries]
    else:
        entries = [(q, "auto", "auto") for q in queries]

    logger.info("Starting Rett syndrome literature benchmark")
    logger.info(f"Queries: {len(entries)}, limit: {limit}, Download dir: {out_dir}")

    with open(OUTPUT_FILE, "a", encoding="utf-8") as out_f:
        for i, (query, lang_code, lang_name) in enumerate(entries, 1):
            logger.info(f"[{i}/{len(entries)}] [{lang_name}] query: {query}")
            stats.total_queries = i

            entry = await _run_one_query(
                query, str(out_dir), dry_run=dry_run,
                limit=limit, language=lang_code,
                literature_types=literature_types,
            )

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

                    # Dedup: skip files already downloaded (same DOI or content)
                    if dedup.is_duplicate(doi, dest):
                        stats.total_deduped += 1
                        logger.info(f"  Dedup: skipping {doi or dest.name}")
                        try:
                            dest.unlink()
                        except OSError:
                            pass
                        continue
                    dedup.record(doi, dest)

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
    logger.info(f"Candidates: {stats.total_candidates}, Downloaded: {stats.total_downloaded}, Deduped: {stats.total_deduped}")


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
# Cleanup — LLM-based relevance filtering
# ═══════════════════════════════════════════════════════════════════

_TITLE_SYSTEM = """Extract a concise, descriptive title from this PDF for file renaming.

Rules:
1. If the document has a clear paper/article title, return it.
2. Return the title in ENGLISH. Translate if necessary.
3. Keep it short (max 80 chars), suitable for a filename.
4. Use only ASCII letters, numbers, spaces, hyphens.
5. Always include Rett/MECP2 context if relevant.

Reply with ONLY the title text, nothing else. No quotes, no JSON."""

_TITLE_USER = """Language: {lang}
Filename: {filename}
Content (first {max_pages} pages):
---
{text}
---

Extract a short English title for this document."""


def _extract_text(pdf_path: Path, max_pages: int = 3, max_chars: int = 3000) -> str:
    """Extract plain text from the first pages of a PDF."""
    try:
        doc = fitz.open(str(pdf_path))
        texts = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            texts.append(page.get_text())
        doc.close()
        return "\n".join(texts)[:max_chars]
    except Exception:
        return ""


def _file_hash(pdf_path: Path) -> str:
    """Short hex hash of full file content."""
    return hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:8]


def _sanitize_title(title: str) -> str:
    """Convert title to filesystem-safe ASCII string."""
    title = unicodedata.normalize("NFKD", title)
    title = re.sub(r"[^a-zA-Z0-9 \-]", "", title)
    title = re.sub(r"\s+", "_", title.strip())
    title = re.sub(r"[_\-]{2,}", "_", title)
    title = title[:100].rstrip("_-")
    return title


async def _llm_call(
    client: AsyncOpenAI,
    sem: asyncio.Semaphore,
    model: str,
    system: str,
    user: str,
) -> str:
    """Single LLM chat completion with semaphore guard."""
    async with sem:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            max_tokens=4096,
        )
        return (resp.choices[0].message.content or "").strip()


async def cmd_cleanup(
    download_dir: Optional[str] = None,
    *,
    dry_run: bool = False,
    concurrency: int = 8,
) -> None:
    """Deduplicate PDFs by content hash, then check relevance via LLM.

    Dedup runs first to avoid wasting LLM calls on identical files.
    Relevance checking delegates to the core relevance_gate module.
    """
    setup_logging()
    base = Path(download_dir) if download_dir else MODULE_DIR / "downloads" / "rett"
    if not base.exists():
        logger.error(f"Directory not found: {base}")
        sys.exit(1)

    # Collect all PDFs into download-dict format for the core gate
    all_pdfs: List[tuple[str, Path]] = []
    for lang_dir in sorted(base.iterdir()):
        if not lang_dir.is_dir():
            continue
        for pdf in sorted(lang_dir.glob("*.pdf")):
            all_pdfs.append((lang_dir.name, pdf))

    lang_count = len(set(l for l, _ in all_pdfs))
    logger.info(f"Found {len(all_pdfs)} PDFs across {lang_count} languages")
    if dry_run:
        logger.info("DRY RUN — no files will be deleted")

    # Dedup by content hash before LLM gate — keep first occurrence
    seen_hashes: Dict[str, Path] = {}
    dedup_removed: List[str] = []
    unique_pdfs: List[tuple[str, Path]] = []
    for lang, pdf in all_pdfs:
        h = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if h in seen_hashes:
            dedup_removed.append(str(pdf))
            if not dry_run:
                pdf.unlink()
                logger.info(f"  Dedup: removed {lang}/{pdf.name} (dup of {seen_hashes[h].name})")
            else:
                logger.info(f"  Dedup: would remove {lang}/{pdf.name} (dup of {seen_hashes[h].name})")
        else:
            seen_hashes[h] = pdf
            unique_pdfs.append((lang, pdf))

    if dedup_removed:
        logger.info(f"Dedup: removed {len(dedup_removed)} duplicate files, {len(unique_pdfs)} unique remaining")
    all_pdfs = unique_pdfs

    # Build download dicts expected by the core relevance gate
    downloads = [
        {"file_path": str(p), "lang": lang, "title": p.stem}
        for lang, p in all_pdfs
    ]

    gate_result: RelevanceGateResult = await run_relevance_gate(
        query="Rett syndrome MECP2 mutation CDKL5 FOXG1",
        downloads=downloads,
        delete_files=not dry_run,
        concurrency=concurrency,
    )

    # Build per-language summary
    by_lang: Dict[str, Dict[str, int]] = {}
    for lang, _ in all_pdfs:
        by_lang.setdefault(lang, {"relevant": 0, "irrelevant": 0, "errors": 0})

    doc_type_counts: Dict[str, int] = {}
    for j in gate_result.judgments:
        # Recover lang from file path: .../downloads/rett/{lang}/file.pdf
        lang = Path(j.file_path).parent.name
        if lang not in by_lang:
            by_lang[lang] = {"relevant": 0, "irrelevant": 0, "errors": 0}
        if j.error:
            by_lang[lang]["errors"] += 1
        elif j.relevant:
            by_lang[lang]["relevant"] += 1
        else:
            by_lang[lang]["irrelevant"] += 1
        if j.doc_type:
            doc_type_counts[j.doc_type] = doc_type_counts.get(j.doc_type, 0) + 1

    # Save report
    report_path = base / f"cleanup_report_{int(time.time())}.json"
    report = {
        "stats": {
            "total": gate_result.total,
            "relevant": gate_result.relevant,
            "irrelevant": gate_result.irrelevant,
            "errors": gate_result.errors,
            "deleted": len(gate_result.removed_paths) if not dry_run else 0,
            "dedup_removed": len(dedup_removed),
            "by_lang": by_lang,
            "by_doc_type": doc_type_counts,
        },
        "removed_paths": gate_result.removed_paths,
        "dedup_removed_paths": dedup_removed,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    logger.info(f"Report: {report_path}")

    # Summary
    print(f"\n{'=' * 60}")
    print("CLEANUP SUMMARY")
    print(f"{'=' * 60}")
    print(f"{'Language':<10} {'Total':>6} {'Relevant':>10} {'Irrelevant':>12} {'Errors':>8}")
    print("-" * 60)
    for lang in sorted(by_lang):
        d = by_lang[lang]
        t = d["relevant"] + d["irrelevant"] + d["errors"]
        print(f"{lang:<10} {t:>6} {d['relevant']:>10} {d['irrelevant']:>12} {d['errors']:>8}")
    print("-" * 60)
    print(f"{'TOTAL':<10} {gate_result.total:>6} {gate_result.relevant:>10} "
          f"{gate_result.irrelevant:>12} {gate_result.errors:>8}")
    if doc_type_counts:
        print(f"\n{'─' * 60}")
        print("DOCUMENT TYPE DISTRIBUTION")
        print(f"{'─' * 60}")
        for dt, cnt in sorted(doc_type_counts.items(), key=lambda x: -x[1]):
            print(f"  {dt:<18} {cnt:>4}")
    if dedup_removed:
        print(f"\nDedup removed: {len(dedup_removed)}")
    if dry_run:
        print(f"Would delete: {gate_result.irrelevant} (dry run)")
    else:
        print(f"Deleted: {len(gate_result.removed_paths)}")


# ═══════════════════════════════════════════════════════════════════
# Rename — LLM-based title extraction
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RenameEntry:
    lang: str
    old_name: str
    new_name: str
    old_path: str
    new_path: str
    error: str = ""


async def cmd_rename(
    download_dir: Optional[str] = None,
    *,
    dry_run: bool = False,
    concurrency: int = 8,
) -> None:
    """Rename PDFs using LLM-extracted English titles."""
    setup_logging()
    base = Path(download_dir) if download_dir else MODULE_DIR / "downloads" / "rett"
    if not base.exists():
        logger.error(f"Directory not found: {base}")
        sys.exit(1)

    cfg = get_config()
    client = AsyncOpenAI(base_url=cfg.llm.base_url, api_key=cfg.llm.api_key)
    model = cfg.llm.model
    logger.info(f"LLM: {cfg.llm.base_url} / {model}")

    # Collect all PDFs
    all_pdfs: List[tuple[str, Path]] = []
    for lang_dir in sorted(base.iterdir()):
        if not lang_dir.is_dir():
            continue
        for pdf in sorted(lang_dir.glob("*.pdf")):
            all_pdfs.append((lang_dir.name, pdf))

    logger.info(f"Found {len(all_pdfs)} PDFs to rename")
    if dry_run:
        logger.info("DRY RUN — no files will be renamed")

    sem = asyncio.Semaphore(concurrency)
    used_names: Set[str] = set()
    entries: List[RenameEntry] = []

    async def _rename_one(lang: str, pdf_path: Path) -> RenameEntry:
        entry = RenameEntry(
            lang=lang, old_name=pdf_path.name,
            new_name="", old_path=str(pdf_path), new_path="",
        )
        try:
            # Try metadata title first
            meta_title = ""
            try:
                doc = fitz.open(str(pdf_path))
                meta_title = ((doc.metadata or {}).get("title") or "").strip()
                doc.close()
            except Exception:
                pass

            if meta_title and len(meta_title) > 10 and meta_title.count("_") <= len(meta_title) * 0.5:
                raw_title = meta_title
            else:
                text = await asyncio.to_thread(_extract_text, pdf_path, 2, 1500)
                if not text or len(text.strip()) < 30:
                    raw_title = f"document_{_file_hash(pdf_path)}"
                else:
                    raw_title = await _llm_call(
                        client, sem, model, _TITLE_SYSTEM,
                        _TITLE_USER.format(lang=lang, filename=pdf_path.name, max_pages=2, text=text),
                    )

            # Strip quotes
            raw_title = raw_title.strip().strip('"').strip("'")
            sanitized = _sanitize_title(raw_title)
            if len(sanitized) < 5:
                sanitized = f"document_{_file_hash(pdf_path)}"

            new_name = f"{lang}_{sanitized}.pdf"
            if new_name in used_names:
                new_name = f"{lang}_{sanitized}_{_file_hash(pdf_path)}.pdf"

            used_names.add(new_name)
            entry.new_name = new_name
            entry.new_path = str(pdf_path.parent / new_name)
        except Exception as e:
            entry.error = str(e)[:200]
        return entry

    tasks = [_rename_one(lang, p) for lang, p in all_pdfs]

    for i, coro in enumerate(asyncio.as_completed(tasks), 1):
        entry = await coro
        entries.append(entry)
        if entry.error:
            logger.info(f"[{i:>3}/{len(all_pdfs)}] {entry.lang}/{entry.old_name[:40]:<40s} ? ERR: {entry.error[:50]}")
        else:
            logger.info(f"[{i:>3}/{len(all_pdfs)}] {entry.lang}/{entry.old_name[:40]:<40s} → {entry.new_name[:60]}")

    # Apply renames
    renamed = 0
    errors = 0
    for e in entries:
        if e.error or not e.new_name:
            errors += 1
            continue
        if e.old_name == e.new_name:
            continue
        try:
            if not dry_run:
                if Path(e.new_path).exists() and e.old_path != e.new_path:
                    logger.warning(f"SKIP overwrite: {e.new_path}")
                    errors += 1
                    continue
                os.rename(e.old_path, e.new_path)
            renamed += 1
        except Exception as exc:
            logger.warning(f"Rename failed: {e.old_path} → {e.new_path}: {exc}")
            errors += 1

    # Save report
    report_path = base / f"rename_report_{int(time.time())}.json"
    report = {
        "total": len(all_pdfs),
        "renamed": renamed,
        "errors": errors,
        "changes": [
            {"lang": e.lang, "old": e.old_name, "new": e.new_name}
            for e in entries if not e.error and e.old_name != e.new_name
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    logger.info(f"Report: {report_path}")

    print(f"\n{'=' * 60}")
    print(f"Renamed: {renamed}  Errors: {errors}  Unchanged: {len(all_pdfs) - renamed - errors}")

    lang_stats: Dict[str, Dict[str, int]] = {}
    for e in entries:
        lang_stats.setdefault(e.lang, {"renamed": 0, "errors": 0})
        if e.error:
            lang_stats[e.lang]["errors"] += 1
        elif e.old_name != e.new_name:
            lang_stats[e.lang]["renamed"] += 1

    print(f"\n{'Language':<10} {'Renamed':>8} {'Errors':>8}")
    print("-" * 30)
    for lang in sorted(lang_stats):
        d = lang_stats[lang]
        print(f"{lang:<10} {d['renamed']:>8} {d['errors']:>8}")


# ═══════════════════════════════════════════════════════════════════
# Multilingual download — uses multilingual_acquisition_workflow
# ═══════════════════════════════════════════════════════════════════


@dataclass
class MultilingualBenchmarkRecord:
    """Per-query multilingual run report row."""

    query: str
    success: bool
    candidates_total: int
    candidates_by_lang: Dict[str, int] = field(default_factory=dict)
    downloads_total: int = 0
    downloads_pre_parsed: int = 0
    warnings: List[str] = field(default_factory=list)
    elapsed_sec: float = 0.0


@dataclass
class MultilingualBenchmarkStats:
    queries: List[MultilingualBenchmarkRecord] = field(default_factory=list)
    total_candidates: int = 0
    total_downloads: int = 0
    total_pre_parsed: int = 0
    total_elapsed_sec: float = 0.0


async def cmd_multilingual(
    queries: List[str],
    *,
    download_dir: Optional[str] = None,
    limit: int = 12,
    dry_run: bool = False,
    relevance_gate: bool = True,
    literature_types: Optional[List[str]] = None,
) -> None:
    """Drive multilingual_acquisition_workflow over a list of seed queries.

    Each query is translated into 6 languages internally; this loop only
    iterates over distinct seed queries (e.g. "Rett syndrome MECP2",
    "MECP2 case report"). Per-query stats include a per-search-lang
    candidate breakdown, pre-parsed (early MinerU) markdown counts, and
    surviving downloads after the relevance gate.
    """
    out_dir = Path(download_dir) if download_dir else (
        MODULE_DIR / "downloads" / "rett_multilingual"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "multilingual_report.json"

    stats = MultilingualBenchmarkStats()
    overall_start = time.monotonic()

    logger.info(
        "Starting multilingual benchmark: {} seed queries → 6 languages each",
        len(queries),
    )

    for idx, query in enumerate(queries, 1):
        logger.info(f"[{idx}/{len(queries)}] {query!r}")
        payload: Dict[str, Any] = {
            "action": "search" if dry_run else "download",
            "query": query,
            "limit": limit,
            "language": "auto",
            "download_path": str(out_dir),
            "relevance_gate": relevance_gate,
        }
        if literature_types:
            payload["literature_types"] = literature_types

        q_start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                multilingual_acquisition_workflow(payload),
                timeout=600,
            )
        except asyncio.TimeoutError:
            logger.warning(f"[{idx}] timeout: {query}")
            stats.queries.append(
                MultilingualBenchmarkRecord(
                    query=query, success=False,
                    candidates_total=0,
                    warnings=["workflow_timeout"],
                    elapsed_sec=round(time.monotonic() - q_start, 2),
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[{idx}] failed: {query}: {exc}")
            stats.queries.append(
                MultilingualBenchmarkRecord(
                    query=query, success=False,
                    candidates_total=0,
                    warnings=[str(exc)[:200]],
                    elapsed_sec=round(time.monotonic() - q_start, 2),
                )
            )
            continue

        candidates = result.get("candidate_links", []) or []
        downloads = result.get("downloads", []) or []
        warnings = result.get("warnings", []) or []

        by_lang: Dict[str, int] = {}
        for c in candidates:
            lang = c.get("search_lang") or "?"
            by_lang[lang] = by_lang.get(lang, 0) + 1

        pre_parsed = sum(1 for d in downloads if d.get("parsed_markdown"))

        record = MultilingualBenchmarkRecord(
            query=query,
            success=bool(result.get("success", False)),
            candidates_total=len(candidates),
            candidates_by_lang=by_lang,
            downloads_total=len(downloads),
            downloads_pre_parsed=pre_parsed,
            warnings=warnings,
            elapsed_sec=round(time.monotonic() - q_start, 2),
        )
        stats.queries.append(record)
        stats.total_candidates += record.candidates_total
        stats.total_downloads += record.downloads_total
        stats.total_pre_parsed += pre_parsed

        logger.info(
            "  candidates={} (by_lang={}) downloads={} pre_parsed={} elapsed={}s",
            record.candidates_total,
            by_lang,
            record.downloads_total,
            pre_parsed,
            record.elapsed_sec,
        )

    stats.total_elapsed_sec = round(time.monotonic() - overall_start, 2)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as rf:
        json.dump(asdict(stats), rf, indent=2, ensure_ascii=False)

    logger.info(
        "Multilingual benchmark complete: {} queries, {} candidates, {} downloads, {} pre-parsed",
        len(stats.queries),
        stats.total_candidates,
        stats.total_downloads,
        stats.total_pre_parsed,
    )
    logger.info(f"Report: {report_path}")


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
    p_dl.add_argument("--config", type=str, default=None,
                      help="Path to JSON config file (e.g. rett_config.json)")
    p_dl.add_argument("--query-file", type=str, default=None,
                      help="Path to plain text query file (one query per line)")
    p_dl.add_argument("--download-dir", type=str, default=None,
                      help="Override download directory")

    p_an = sub.add_parser("analyze", help="Print analysis of benchmark report")
    p_an.add_argument("path", nargs="?", help="Path to report JSON (default: rett_syndrome_report.json)")
    p_an.add_argument("--llm-classify", action="store_true",
                      help="Classify medical domain via LLM (delegates to benchmark.py)")

    p_clean = sub.add_parser("cleanup", help="LLM-based relevance check, remove irrelevant PDFs")
    p_clean.add_argument("--download-dir", type=str, default=None, help="PDF directory (default: downloads/rett)")
    p_clean.add_argument("--dry-run", action="store_true", help="Preview only, do not delete")
    p_clean.add_argument("--concurrency", type=int, default=8, help="Parallel LLM calls")

    p_ren = sub.add_parser("rename", help="Rename PDFs with LLM-extracted English titles")
    p_ren.add_argument("--download-dir", type=str, default=None, help="PDF directory (default: downloads/rett)")
    p_ren.add_argument("--dry-run", action="store_true", help="Preview only, do not rename")
    p_ren.add_argument("--concurrency", type=int, default=8, help="Parallel LLM calls")

    p_ml = sub.add_parser(
        "multilingual",
        help="Multilingual benchmark — drives multilingual_acquisition_workflow",
    )
    p_ml.add_argument("--query-file", type=str, default=None,
                      help="Plain text query file; one seed query per line")
    p_ml.add_argument("--query", type=str, default=None,
                      help="Single seed query (alternative to --query-file)")
    p_ml.add_argument("--download-dir", type=str, default=None,
                      help="Override download directory")
    p_ml.add_argument("--limit", type=int, default=12,
                      help="Per-request candidate limit (across all 6 languages)")
    p_ml.add_argument("--dry-run", action="store_true",
                      help="Search only, do not download files")
    p_ml.add_argument("--no-relevance-gate", action="store_true",
                      help="Disable LLM relevance gate")
    p_ml.add_argument("--literature-types", type=str, default=None,
                      help="Comma-separated literature_type filter (e.g. case_report,sequencing)")

    args = parser.parse_args()

    if args.cmd == "seed-queries":
        cmd_seed_queries(args.force)
    elif args.cmd == "download":
        cfg_data: Optional[ConfigData] = None
        queries: List[str] = []

        if args.config:
            cfg_path = Path(args.config)
            if not cfg_path.exists():
                logger.error(f"Config file not found: {cfg_path}")
                sys.exit(1)
            cfg_data = load_config(cfg_path)
            queries = [cq.text for cq in cfg_data.queries]
            logger.info(f"Loaded {len(queries)} queries from config: {cfg_path}")
        elif args.query_file:
            qfile = Path(args.query_file)
            if not qfile.exists():
                logger.info("Query file not found. Generating seed queries...")
                cmd_seed_queries(force=False)
            queries = load_queries(qfile)
        else:
            # Default: try config first, then query file
            if CONFIG_FILE.exists():
                cfg_data = load_config(CONFIG_FILE)
                queries = [cq.text for cq in cfg_data.queries]
                logger.info(f"Loaded {len(queries)} queries from default config: {CONFIG_FILE}")
            else:
                if not QUERY_FILE.exists():
                    cmd_seed_queries(force=False)
                queries = load_queries(QUERY_FILE)

        if not queries:
            logger.error("No queries found")
            sys.exit(1)

        asyncio.run(cmd_download(
            queries,
            dry_run=args.dry_run,
            download_dir=args.download_dir,
            config=cfg_data,
        ))
    elif args.cmd == "analyze":
        cmd_analyze(Path(args.path) if args.path else None, llm_classify=args.llm_classify)
    elif args.cmd == "cleanup":
        asyncio.run(cmd_cleanup(
            download_dir=args.download_dir,
            dry_run=args.dry_run,
            concurrency=args.concurrency,
        ))
    elif args.cmd == "rename":
        asyncio.run(cmd_rename(
            download_dir=args.download_dir,
            dry_run=args.dry_run,
            concurrency=args.concurrency,
        ))
    elif args.cmd == "multilingual":
        seeds: List[str] = []
        if args.query:
            seeds = [args.query]
        elif args.query_file:
            qfile = Path(args.query_file)
            if not qfile.exists():
                logger.error(f"Query file not found: {qfile}")
                sys.exit(1)
            seeds = load_queries(qfile)
        else:
            logger.error("multilingual requires --query or --query-file")
            sys.exit(1)

        lit_types = (
            [t.strip() for t in args.literature_types.split(",") if t.strip()]
            if args.literature_types else None
        )

        asyncio.run(cmd_multilingual(
            seeds,
            download_dir=args.download_dir,
            limit=args.limit,
            dry_run=args.dry_run,
            relevance_gate=not args.no_relevance_gate,
            literature_types=lit_types,
        ))


if __name__ == "__main__":
    main()
