"""Rett syndrome / MECP2 multilingual case report PDF acquisition.

Uses the project's online acquisition module (search_multilingual) for
language-routed regional search, then downloads PDFs and filters for
case_report literature type.

Usage (run from project root):
    # Default: keyword pre-filter, then download
    uv run --directory backend python ../benchmark/literature_acquisition/rett_download.py

    # Single language test
    uv run --directory backend python ../benchmark/literature_acquisition/rett_download.py --lang en --dry-run

    # Override target count
    uv run --directory backend python ../benchmark/literature_acquisition/rett_download.py --target 10

    # To skip literature type filtering entirely:
    # Set "literature_types": [] in rett_config.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure backend/src is importable when run from project root.
# The uv-managed venv already has all deps; we just need the source path.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_SRC = _PROJECT_ROOT / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC.parent))  # insert backend/

from loguru import logger
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
    OnlineAcquisitionItem,
)
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.literature_type_classifier import (
    classify_item,
)
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.search_service import (
    search_multilingual,
)
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import (
    download_file_from_url,
)
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.pubmed_service import (
    get_pubmed_service,
)

# ═══════════════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════════════

MODULE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = MODULE_DIR / "rett_config.json"
LOG_DIR = MODULE_DIR / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════════════════════

def setup_logging(log_dir: Path = LOG_DIR, level: str = "INFO") -> None:
    """Configure loguru to log to console + rotating file."""
    logger.remove()
    logger.add(
        sys.stderr, level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} {level:<8} {message}",
    )
    logger.add(
        str(log_dir / "rett_download.log"),
        rotation="5 MB", retention=5, encoding="utf-8", level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} {level:<8} {message}",
    )
    import logging as _pylogging
    _pylogging.getLogger("httpx").setLevel(_pylogging.WARNING)
    _pylogging.getLogger("urllib3").setLevel(_pylogging.WARNING)


# ═══════════════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DownloadRecord:
    lang: str
    query: str
    literature_type: str
    title: str
    doi: str
    source: str
    provider: str
    success: bool
    file_path: str = ""
    file_size: int = 0
    source_url: str = ""
    error: str = ""
    elapsed_ms: int = 0


@dataclass
class DownloadStats:
    config_file: str = ""
    disease: str = ""
    target_per_lang: Any = 0  # int or dict[str, int]
    total_attempted: int = 0
    total_downloaded: int = 0
    by_lang: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_source: Dict[str, int] = field(default_factory=dict)
    elapsed_sec: float = 0.0
    records: List[DownloadRecord] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _sanitize(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", name)[:80]


def _now_ts() -> str:
    """Return current UTC timestamp string safe for filenames."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")


def _normalize_record(raw: dict) -> dict:
    """Normalize old-format records (from benchmark.py or older runs)
    to the current DownloadRecord field names."""
    out = dict(raw)
    # Map old field name 'method' → 'source'
    if "method" in out and "source" not in out:
        out["source"] = out.pop("method")
    # Fill required fields that may be missing in old format
    out.setdefault("query", "")
    out.setdefault("source", "unknown")
    out.setdefault("provider", out.get("source", "unknown"))
    out.setdefault("success", bool(out.get("success", False)))
    out.setdefault("lang", out.get("lang", "unknown"))
    out.setdefault("literature_type", out.get("literature_type", "unclassified"))
    out.setdefault("title", out.get("title", ""))
    out.setdefault("doi", out.get("doi", ""))
    out.setdefault("file_path", out.get("file_path", ""))
    out.setdefault("file_size", int(out.get("file_size", 0)))
    out.setdefault("source_url", out.get("source_url", ""))
    out.setdefault("error", out.get("error", ""))
    out.setdefault("elapsed_ms", int(out.get("elapsed_ms", 0)))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# SHA256 dedup registry (shared across all languages)
# ═══════════════════════════════════════════════════════════════════════════

# Maps sha256 hex → (lang_code, file_path) of the first occurrence
_HASH_REGISTRY: dict[str, tuple[str, str]] = {}
_HASH_LOCK = asyncio.Lock()


async def _check_dedup(file_path: str, lang_code: str) -> bool:
    """Check SHA256 dedup. Returns True if file is new (kept), False if duplicate.

    When a duplicate is detected, the file is deleted and the hash is recorded
    as already-seen. Thread-safe via asyncio.Lock.
    """
    p = Path(file_path)
    if not p.exists():
        return False
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    async with _HASH_LOCK:
        if sha in _HASH_REGISTRY:
            first_lang, first_path = _HASH_REGISTRY[sha]
            logger.info(
                f"[{lang_code}] 🔄 duplicate of [{first_lang}] {Path(first_path).name[:40]} — skipped"
            )
            p.unlink(missing_ok=True)
            return False
        _HASH_REGISTRY[sha] = (lang_code, file_path)
        return True


# ═══════════════════════════════════════════════════════════════════════════
# PubMed search (additional data source)
# ═══════════════════════════════════════════════════════════════════════════

async def _search_pubmed(
    query: str,
    disease: str,
    lang_code: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search PubMed directly for clinically-relevant results.

    Uses MeSH-based precision queries when the target is a known disease.
    Returns candidates in the same format as search_multilingual().
    """
    svc = get_pubmed_service()

    # Build a PubMed-optimized query with MeSH terms and filters
    # Prefer "case reports"[Publication Type] for precision
    pubmed_query = (
        f'("{disease}"[MeSH Terms] OR "{disease}"[All Fields]) '
        f"AND ({query})"
    )
    # Also try a broader query with case report filter
    alt_query = (
        f'("{disease}"[MeSH Terms] OR "{disease}"[All Fields]) '
        f'AND ("case reports"[Publication Type] OR case report*[Title/Abstract])'
    )

    candidates: list[dict[str, Any]] = []
    seen_pmids: set[str] = set()

    for q in (pubmed_query, alt_query):
        try:
            results = await asyncio.wait_for(
                svc.search_candidates(q, candidate_limit=min(limit, 15)),
                timeout=15,
            )
        except Exception as exc:
            logger.debug(f"[{lang_code}] PubMed search failed for '{q[:60]}': {exc}")
            continue

        for r in results:
            if r.pmid in seen_pmids:
                continue
            seen_pmids.add(r.pmid)

            # Build candidate dict in same format as search_multilingual output
            # Prefer PMC direct PDF URL when PMCID is available
            identifiers: dict[str, str] = {"pmid": r.pmid}
            if r.pmcid:
                identifiers["pmcid"] = r.pmcid
            cand: dict[str, Any] = {
                "title": r.title,
                "doi": r.doi,
                "url": r.pmc_pdf_url or f"https://pubmed.ncbi.nlm.nih.gov/{r.pmid}/",
                "provider": "pubmed",
                "route": "api",
                "journal": r.journal,
                "year": r.pub_date[:4] if r.pub_date else "",
                "identifiers": identifiers,
                "detail_link": f"https://pubmed.ncbi.nlm.nih.gov/{r.pmid}/",
                "language": lang_code,
            }
            candidates.append(cand)

        if len(candidates) >= limit:
            break

    return candidates[:limit]


# ═══════════════════════════════════════════════════════════════════════════
# Core logic
# ═══════════════════════════════════════════════════════════════════════════

async def _process_language(
    lang_code: str,
    lang_cfg: Dict[str, Any],
    disease: str,
    target: int,
    candidate_limit: int,
    download_dir: Path,
    literature_types: List[str],
    timeout_s: int,
    dry_run: bool,
    sem: asyncio.Semaphore,
    *,
    skip_dois: set[str] | None = None,
) -> List[DownloadRecord]:
    """Search + download for one language. Returns list of records.

    skip_dois: DOIs already attempted in a previous run — skip these
    candidates so incremental re-runs find new papers.
    """
    records: List[DownloadRecord] = []
    queries = list(lang_cfg.get("queries", []))
    downloaded = 0
    query_idx = 0
    _skip = skip_dois or set()

    while downloaded < target and query_idx < len(queries):
        query = queries[query_idx]
        query_idx += 1

        # search_multilingual may try 3-7 providers sequentially;
        # use a longer timeout than individual downloads.
        search_timeout = max(timeout_s * 3, 180)

        async with sem:
            # Run search_multilingual + PubMed in parallel
            search_task = asyncio.create_task(
                asyncio.wait_for(
                    search_multilingual(
                        target=query,
                        disease=disease,
                        language=lang_code,
                        candidate_limit=candidate_limit,
                    ),
                    timeout=search_timeout,
                )
            )
            pubmed_task = asyncio.create_task(
                _search_pubmed(
                    query=query,
                    disease=disease,
                    lang_code=lang_code,
                    limit=candidate_limit,
                )
            )

            candidates: list[dict[str, Any]] = []
            for task, label in ((search_task, "search_multilingual"), (pubmed_task, "pubmed")):
                try:
                    results = await task
                    candidates.extend(results)
                except asyncio.TimeoutError:
                    logger.warning(f"[{lang_code}] {label} timed out for: {query}")
                except Exception as exc:
                    logger.warning(f"[{lang_code}] {label} failed for '{query}': {exc}")

            # Dedupe by title (case-folded, first 80 chars)
            seen_titles: set[str] = set()
            deduped: list[dict[str, Any]] = []
            for c in candidates:
                t = (c.get("title") or "").strip().casefold()[:80]
                if t and t in seen_titles:
                    continue
                if t:
                    seen_titles.add(t)
                deduped.append(c)
            candidates = deduped

        if not candidates:
            logger.debug(f"[{lang_code}] no candidates for: {query}")
            continue

        logger.info(
            f"[{lang_code}] query={query!r} → {len(candidates)} candidates"
        )

        for cand_idx, cand in enumerate(candidates):
            if downloaded >= target:
                break

            title = cand.get("title", "")
            doi = cand.get("doi") or ""
            source = cand.get("provider", "unknown")
            url = (
                cand.get("url")
                or cand.get("detail_link")
                or (cand.get("identifiers") or {}).get("url")
                or ""
            )
            # Build fallback PDF URLs for PMC/PubMed to increase hit rate
            _alt_urls: list[str] = []
            pmcid = (cand.get("identifiers") or {}).get("pmcid") or ""
            pmid = (cand.get("identifiers") or {}).get("pmid") or ""

            # PMC landing page → direct PDF URL
            _pmc_match = re.search(r"PMC(\d+)", url + pmcid + pmid)
            if _pmc_match:
                _alt_urls.append(
                    f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{_pmc_match.group(1)}/pdf/"
                )

            # PubMed landing page → try PMC pdf pattern with PMID
            if pmid and not _pmc_match:
                _alt_urls.append(
                    f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmid}/pdf/"
                )

            # Build ordered URL list: direct PDF variants first, original last
            _urls = _alt_urls + ([url] if url and url not in _alt_urls else [])

            if not _urls:
                logger.debug(f"[{lang_code}] candidate {cand_idx}: no URL, skipping")
                continue

            # Skip DOIs already attempted in a previous run
            if doi and doi in _skip:
                logger.debug(f"[{lang_code}] candidate {cand_idx}: DOI already attempted, skipping")
                continue

            # Classify literature type
            item = OnlineAcquisitionItem(
                source=source,
                title=title or None,
                doi=doi or None,
            )
            lt = classify_item(item)
            lit_type = lt.value if lt else "unclassified"

            # Fallback: if unclassified but title mentions disease keywords,
            # treat as a likely clinical report (many case reports don't
            # literally say "case report" in the title).
            _disease_keywords = re.compile(
                r"Rett|MECP2|CDKL5|FOXG1|レット|레트|синдром\s+Ретта",
                re.IGNORECASE,
            )
            if lit_type == "unclassified" and _disease_keywords.search(title):
                lit_type = "case_report"

            # Filter by requested literature types
            if literature_types and lit_type not in literature_types:
                logger.debug(
                    f"[{lang_code}] candidate {cand_idx}: type={lit_type}, "
                    f"not in {literature_types}, skipping"
                )
                # Still record the attempt
                records.append(DownloadRecord(
                    lang=lang_code, query=query,
                    literature_type=lit_type, title=title, doi=doi,
                    source=source, provider=cand.get("provider", ""),
                    success=False, error=f"type_filtered:{lit_type}",
                ))
                continue

            if dry_run:
                logger.info(
                    f"[{lang_code}] DRY-RUN {lit_type}: {title[:80] if title else 'N/A'}"
                )
                records.append(DownloadRecord(
                    lang=lang_code, query=query,
                    literature_type=lit_type, title=title, doi=doi,
                    source=source, provider=cand.get("provider", ""),
                    success=True, source_url=_urls[0] if _urls else "",
                ))
                downloaded += 1
                continue

            # Download PDF — try each URL variant via gateway (Rust + httpx dual-tier)
            fname_stem = f"{_sanitize(lang_code)}_{_sanitize(title or 'untitled')[:60]}_{cand_idx}"
            download_dir_str = str(download_dir / lang_code)
            ok = False
            used_url = ""
            elapsed = 0
            dest_path: Optional[str] = None
            for try_url in _urls:
                t0 = time.monotonic()
                try:
                    result_path, final_url, warns = await download_file_from_url(
                        try_url, download_dir_str, fname_stem,
                    )
                    elapsed = int((time.monotonic() - t0) * 1000)
                    if result_path:
                        ok = True
                        used_url = final_url or try_url
                        dest_path = result_path
                        break
                except Exception:
                    elapsed = int((time.monotonic() - t0) * 1000)
                    logger.debug(f"[{lang_code}] download exception for {try_url}")

            if ok and dest_path:
                # SHA256 dedup: skip if same file already downloaded
                if not await _check_dedup(dest_path, lang_code):
                    records.append(DownloadRecord(
                        lang=lang_code, query=query,
                        literature_type=lit_type, title=title, doi=doi,
                        source=source, provider=cand.get("provider", ""),
                        success=False, source_url=used_url,
                        error="sha256_duplicate", elapsed_ms=elapsed,
                    ))
                    continue

                dest = Path(dest_path)
                file_size = dest.stat().st_size
                logger.info(
                    f"[{lang_code}] ✓ {downloaded+1}/{target} "
                    f"{file_size//1024}KB [{lit_type}] {title[:60] if title else 'N/A'}"
                )
                records.append(DownloadRecord(
                    lang=lang_code, query=query,
                    literature_type=lit_type, title=title, doi=doi,
                    source=source, provider=cand.get("provider", ""),
                    success=True, file_path=dest_path,
                    file_size=file_size, source_url=used_url,
                    elapsed_ms=elapsed,
                ))
                downloaded += 1
            else:
                logger.debug(
                    f"[{lang_code}] ✗ download failed: {title[:60] if title else 'N/A'}"
                )
                records.append(DownloadRecord(
                    lang=lang_code, query=query,
                    literature_type=lit_type, title=title, doi=doi,
                    source=source, provider=cand.get("provider", ""),
                    success=False, source_url=_urls[0] if _urls else "",
                    error="download_failed", elapsed_ms=elapsed,
                ))

    return records


async def run(
    config: Dict[str, Any],
    lang_filter: Optional[str],
    dry_run: bool,
    *,
    resume_report: Optional[Path] = None,
) -> DownloadStats:
    """Main orchestration: iterate languages, search, download, classify.

    When resume_report is set: reads previous report, only re-runs
    languages that haven't met their targets, and merges records.
    """
    # ── Resume mode: load previous report, compute deficit ──────────────
    prev_records: list[DownloadRecord] = []
    prev_downloaded: dict[str, int] = {}
    prev_dois: set[str] = set()
    if resume_report is not None:
        if not resume_report.exists():
            logger.error(f"Resume report not found: {resume_report}")
            sys.exit(1)
        with open(resume_report, encoding="utf-8") as f:
            prev = json.load(f)
        prev_records_raw = prev.get("records", [])
        for r in prev_records_raw:
            # Normalize old-format records (benchmark.py or older runs)
            nr = _normalize_record(r)
            rec = DownloadRecord(**{k: nr[k] for k in DownloadRecord.__dataclass_fields__ if k in nr})
            prev_records.append(rec)
            if rec.success:
                prev_downloaded[rec.lang] = prev_downloaded.get(rec.lang, 0) + 1
            # Track all previously attempted DOIs for skip
            if rec.doi:
                prev_dois.add(rec.doi)
        logger.info(
            f"Resume: loaded {len(prev_records)} previous records, "
            f"already downloaded: {prev_downloaded}, "
            f"skipping {len(prev_dois)} previously-attempted DOIs"
        )

    disease = config["disease"]
    target_per_lang_raw = config.get("target_per_lang", 5)
    candidate_limit = config.get("candidate_limit", 10)
    literature_types = config.get("literature_types", [])
    timeout_s = config.get("timeout_s", 60)
    concurrency = config.get("concurrency", 3)
    download_root = Path(config.get("download_dir", "downloads/rett"))
    if not download_root.is_absolute():
        download_root = MODULE_DIR / download_root
    download_root.mkdir(parents=True, exist_ok=True)

    # target_per_lang can be a uniform int or a per-language dict
    def _resolve_target(code: str) -> int:
        if isinstance(target_per_lang_raw, dict):
            return int(target_per_lang_raw.get(code, 5))
        return int(target_per_lang_raw)

    lang_map = config.get("languages", {})
    if lang_filter:
        if lang_filter not in lang_map:
            logger.error(f"Language '{lang_filter}' not in config. Available: {list(lang_map)}")
            sys.exit(1)
        lang_map = {lang_filter: lang_map[lang_filter]}

    # ── Resume: compute remaining targets, skip completed ──────────────
    remaining_targets: dict[str, int] = {}
    for code in list(lang_map.keys()):
        orig = _resolve_target(code)
        done = prev_downloaded.get(code, 0)
        rem = max(0, orig - done)
        remaining_targets[code] = rem
        if resume_report is not None and rem == 0:
            logger.info(f"[{code}] already at target ({done}/{orig}), skipping")
            del lang_map[code]

    if resume_report is not None and not lang_map:
        logger.info("All languages at target — nothing to do.")
        # Build empty stats from previous report and return
        stats = DownloadStats(
            config_file=str(CONFIG_PATH),
            disease=disease,
            target_per_lang=target_per_lang_raw,
            records=list(prev_records),
        )
        for r in prev_records:
            stats.total_attempted += 1
            if r.success:
                stats.total_downloaded += 1
                stats.by_lang[r.lang] = stats.by_lang.get(r.lang, 0) + 1
                stats.by_type[r.literature_type] = stats.by_type.get(r.literature_type, 0) + 1
                stats.by_source[r.source] = stats.by_source.get(r.source, 0) + 1
        return stats

    stats = DownloadStats(
        config_file=str(CONFIG_PATH),
        disease=disease,
        target_per_lang=target_per_lang_raw,
    )
    start = time.monotonic()
    sem = asyncio.Semaphore(concurrency)

    logger.info("=" * 60)
    logger.info(f"  Rett/MECP2 Multilingual Case Report Download")
    logger.info(f"  Disease: {disease}")
    logger.info(f"  Languages: {len(lang_map)} ({', '.join(lang_map)})")
    logger.info(f"  Target per lang: {target_per_lang_raw}")
    logger.info(f"  Literature types: {literature_types or 'all'}")
    logger.info(f"  Download dir: {download_root}")
    logger.info(f"  Dry run: {dry_run}")
    logger.info("=" * 60)

    for lang_code, lang_cfg in lang_map.items():
        lang_name = lang_cfg.get("name", lang_code)
        lang_target = remaining_targets.get(lang_code, _resolve_target(lang_code))
        prev_done = prev_downloaded.get(lang_code, 0)
        if resume_report is not None:
            logger.info(
                f"\n── {lang_name} ({lang_code}) "
                f"target={_resolve_target(lang_code)} done={prev_done} remaining={lang_target} ──"
            )
        else:
            logger.info(f"\n── {lang_name} ({lang_code}) target={lang_target} ──")

        records = await _process_language(
            lang_code=lang_code,
            lang_cfg=lang_cfg,
            disease=disease,
            target=lang_target,
            candidate_limit=candidate_limit,
            download_dir=download_root,
            literature_types=literature_types,
            timeout_s=timeout_s,
            dry_run=dry_run,
            sem=sem,
            skip_dois=prev_dois if resume_report is not None else None,
        )
        stats.records.extend(records)

        ok_count = sum(1 for r in records if r.success)
        logger.info(
            f"[{lang_code}] {ok_count}/{len(records)} downloaded "
            f"(target: {lang_target})"
        )

    # ── Merge previous records from resume ────────────────────────────
    if resume_report is not None and prev_records:
        # Avoid double-counting: merge new records, keep old ones
        stats.records = list(prev_records) + stats.records
        logger.info(
            f"Resume merge: {len(prev_records)} old + "
            f"{len(stats.records) - len(prev_records)} new records"
        )

    # Aggregate stats (recompute from scratch after merge)
    stats.total_attempted = 0
    stats.total_downloaded = 0
    stats.by_lang = {}
    stats.by_type = {}
    stats.by_source = {}
    for r in stats.records:
        stats.total_attempted += 1
        if r.success:
            stats.total_downloaded += 1
            stats.by_lang[r.lang] = stats.by_lang.get(r.lang, 0) + 1
            stats.by_type[r.literature_type] = stats.by_type.get(r.literature_type, 0) + 1
            stats.by_source[r.source] = stats.by_source.get(r.source, 0) + 1

    stats.elapsed_sec = round(time.monotonic() - start, 1)

    # ── Write report ──────────────────────────────────────────────────────
    ts = _now_ts()
    report_path = download_root / f"report_{ts}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(asdict(stats), f, indent=2, default=str, ensure_ascii=False)

    # ── Summary ───────────────────────────────────────────────────────────
    logger.info(f"\n{'=' * 60}")
    logger.info(f"  DONE")
    logger.info(f"  Downloaded: {stats.total_downloaded}/{stats.total_attempted}")
    logger.info(f"  Elapsed:    {stats.elapsed_sec:.1f}s")
    logger.info(f"  Report:     {report_path}")
    logger.info(f"{'=' * 60}")

    # Per-language breakdown
    for lang in sorted(stats.by_lang):
        logger.info(f"  {lang}: {stats.by_lang[lang]}")

    return stats


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rett/MECP2 multilingual case report PDF download",
    )
    parser.add_argument(
        "--config", type=Path, default=CONFIG_PATH,
        help=f"Path to JSON config (default: {CONFIG_PATH})",
    )
    parser.add_argument(
        "--lang", type=str, default=None,
        help="Filter to a single language code (e.g. zh, en, ja)",
    )
    parser.add_argument(
        "--target", type=int, default=None,
        help="Override target_per_lang from config",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Search only — do not download PDFs",
    )
    parser.add_argument(
        "--resume", type=Path, default=None, metavar="REPORT.json",
        help="Incremental re-run: read previous report, only re-run "
             "languages that haven't met their targets, merge results.",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        help="Log level (default: INFO)",
    )
    args = parser.parse_args()

    setup_logging(level=args.log_level)

    # Load config
    config_path: Path = args.config
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    if args.target is not None:
        config["target_per_lang"] = args.target

    asyncio.run(run(
        config,
        lang_filter=args.lang,
        dry_run=args.dry_run,
        resume_report=args.resume,
    ))


if __name__ == "__main__":
    main()
