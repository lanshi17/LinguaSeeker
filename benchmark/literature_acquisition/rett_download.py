"""Rett syndrome / MECP2 multilingual case report PDF acquisition.

Uses the project's online acquisition module (search_multilingual) for
language-routed regional search, then downloads PDFs and filters for
case_report literature type.

Usage (run from project root):
    # Default: keyword pre-filter, then download
    uv run --directory backend python ../benchmark/literature_acquisition/rett_download.py

    # Single language test
    uv run --directory backend python ../benchmark/literature_acquisition/rett_download.py --lang en --dry-run

    # LLM verification mode: download all → LLM checks each PDF for case report + variant
    uv run --directory backend python ../benchmark/literature_acquisition/rett_download.py --llm-verify

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
from urllib.parse import urljoin

# Ensure backend/src is importable when run from project root.
# The uv-managed venv already has all deps; we just need the source path.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_SRC = _PROJECT_ROOT / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC.parent))  # insert backend/

import httpx
import fitz
from loguru import logger

from src.core.config import get_config
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
    OnlineAcquisitionItem,
)
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.literature_type_classifier import (
    classify_item,
)
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.search_service import (
    search_multilingual,
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
class LLMVerification:
    """Result of LLM-based case report verification."""
    is_case_report: bool = False
    confidence: str = "low"  # high / medium / low
    reasoning: str = ""
    has_variant_report: bool = False
    variant_details: str = ""
    model: str = ""
    error: str = ""


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
    llm_verification: dict | None = None  # LLMVerification as dict after verification pass


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
# PDF download (reused from benchmark.py)
# ═══════════════════════════════════════════════════════════════════════════

async def _download_from_url(url: str, dest: Path, timeout: int = 30) -> bool:
    """Download PDF from URL; scan HTML for PDF links if direct hit misses."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, verify=False,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "Chrome/124.0 ACMG-Lingua/1.0"
                ),
            },
        ) as client:
            r = await client.get(url)
            if r.content[:4] == b"%PDF":
                dest.write_bytes(r.content)
                logger.debug(f"Wrote PDF: {dest} ({len(r.content)} bytes)")
                return True
            if b"<html" in r.content[:2048].lower():
                pdf_links = re.findall(
                    r'href=["\']([^"\']*(?:\.pdf|/bitstream/|download.*?pdf)[^"\']*)["\']',
                    r.text, re.IGNORECASE,
                )
                seen: set[str] = set()
                for link in pdf_links[:3]:
                    abs_url = urljoin(str(r.url), link)
                    if abs_url in seen:
                        continue
                    seen.add(abs_url)
                    try:
                        r2 = await client.get(abs_url)
                        if r2.content[:4] == b"%PDF":
                            dest.write_bytes(r2.content)
                            logger.debug(f"Wrote PDF: {dest} ({len(r2.content)} bytes) via {abs_url}")
                            return True
                    except Exception:
                        logger.debug(f"Failed nested PDF link: {abs_url}")
                        continue
    except Exception:
        logger.debug(f"Download exception for URL: {url}")
    return False


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
            cand: dict[str, Any] = {
                "title": r.title,
                "doi": "",  # PubMed search doesn't return DOI in basic mode
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{r.pmid}/",
                "provider": "pubmed",
                "route": "api",
                "journal": r.journal,
                "year": r.pub_date[:4] if r.pub_date else "",
                "identifiers": {"pmid": r.pmid},
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
    skip_filter: bool = False,
    skip_dois: set[str] | None = None,
) -> List[DownloadRecord]:
    """Search + download for one language. Returns list of records.

    When skip_filter=True (--llm-verify mode), all candidates are downloaded
    regardless of literature_type; LLM verification runs later.

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

            if not url:
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

            # Filter by requested literature types (skip when LLM will verify later)
            if not skip_filter and literature_types and lit_type not in literature_types:
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
                    success=True, source_url=url,
                ))
                downloaded += 1
                continue

            # Download PDF
            fname = f"{_sanitize(lang_code)}_{_sanitize(title or 'untitled')[:60]}_{cand_idx}.pdf"
            dest = download_dir / lang_code / fname
            t0 = time.monotonic()
            ok = await _download_from_url(url, dest, timeout=timeout_s)
            elapsed = int((time.monotonic() - t0) * 1000)

            if ok:
                # SHA256 dedup: skip if same file already downloaded
                if not await _check_dedup(str(dest), lang_code):
                    records.append(DownloadRecord(
                        lang=lang_code, query=query,
                        literature_type=lit_type, title=title, doi=doi,
                        source=source, provider=cand.get("provider", ""),
                        success=False, source_url=url,
                        error="sha256_duplicate", elapsed_ms=elapsed,
                    ))
                    continue

                file_size = dest.stat().st_size
                logger.info(
                    f"[{lang_code}] ✓ {downloaded+1}/{target} "
                    f"{file_size//1024}KB [{lit_type}] {title[:60] if title else 'N/A'}"
                )
                records.append(DownloadRecord(
                    lang=lang_code, query=query,
                    literature_type=lit_type, title=title, doi=doi,
                    source=source, provider=cand.get("provider", ""),
                    success=True, file_path=str(dest),
                    file_size=file_size, source_url=url,
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
                    success=False, source_url=url,
                    error="download_failed", elapsed_ms=elapsed,
                ))

    return records


async def run(
    config: Dict[str, Any],
    lang_filter: Optional[str],
    dry_run: bool,
    *,
    llm_verify: bool = False,
    llm_model: str = "",
    resume_report: Optional[Path] = None,
) -> DownloadStats:
    """Main orchestration: iterate languages, search, download, classify.

    When llm_verify=True: downloads all candidates (no keyword filter),
    then runs LLM verification on each PDF to identify true case reports.

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
            # Restore llm_verification if present (may be dict or null)
            if r.get("llm_verification"):
                rec.llm_verification = r["llm_verification"]
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
    logger.info(f"  LLM verify: {llm_verify}")
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
            skip_filter=llm_verify,
            skip_dois=prev_dois if resume_report is not None else None,
        )
        stats.records.extend(records)

        ok_count = sum(1 for r in records if r.success)
        logger.info(
            f"[{lang_code}] {ok_count}/{len(records)} downloaded "
            f"(target: {lang_target})"
        )

    # ── LLM verification pass (post-download) ────────────────────────────
    if llm_verify and not dry_run:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"  LLM VERIFICATION PASS")
        logger.info(f"{'=' * 60}")
        stats.records = await _run_llm_verification_pass(
            stats.records,
            timeout_sec=timeout_s,
            model=llm_model,
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
# LLM verification (--llm-verify mode)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_pdf_text_for_llm(pdf_path: Path, max_pages: int = 3, max_chars: int = 8000) -> str:
    """Extract plain text from the first pages of a PDF for LLM classification."""
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return ""

    chunks: list[str] = []
    try:
        for i in range(min(max_pages, len(doc))):
            txt = str(doc[i].get_text("text") or "")
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                chunks.append(txt)
            if sum(len(c) for c in chunks) >= max_chars:
                break
    finally:
        doc.close()

    return "\n".join(chunks)[:max_chars]


def _verify_case_report_via_llm(
    *,
    title: str,
    lang: str,
    pdf_text: str,
    timeout_sec: int = 60,
    model_override: str = "",
) -> LLMVerification:
    """Use LLM to verify if a PDF is a case report reporting genetic variants.

    Returns LLMVerification with reasoning for auditability.
    """
    cfg = get_config()
    model = model_override or (cfg.llm.model or "").strip()
    base_url = (cfg.llm.base_url or "").strip().rstrip("/")
    api_key = (cfg.llm.api_key or "").strip()

    if not model:
        return LLMVerification(error="missing_llm_model")
    if not base_url:
        return LLMVerification(error="missing_llm_base_url")

    system_prompt = (
        "You are a medical literature triage assistant specialized in "
        "Rett syndrome and MECP2-related disorders. Given a paper title "
        "and PDF excerpt, answer three questions. "
        "Return strict JSON only with keys: is_case_report (bool), "
        "confidence (high/medium/low), reasoning (1-2 sentences), "
        "has_variant_report (bool), variant_details (string or empty).\n\n"
        "Criteria for is_case_report=true:\n"
        "- Describes one or more specific patients/clinicians' observations\n"
        "- Reports clinical features, genetic findings, or treatment outcomes\n"
        "- Is NOT a review, meta-analysis, guideline, or methods-only paper\n\n"
        "Criteria for has_variant_report=true:\n"
        "- Mentions specific genetic variants (e.g. c.502C>T, p.Arg168Ter, "
        "exon deletion, duplication, frameshift, missense)\n"
        "- If yes, list the variant(s) in variant_details"
    )
    user_prompt = (
        f"language={lang}\n"
        f"title={title or 'N/A'}\n\n"
        "PDF excerpt (first pages):\n"
        f"{pdf_text[:8000]}"
    )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }

    # Build endpoint: avoid double /v1 if base_url already includes it
    api_url = base_url.rstrip("/")
    if not api_url.endswith("/v1"):
        api_url = f"{api_url}/v1"
    api_url = f"{api_url}/chat/completions"

    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            resp = client.post(api_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = (
            ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ).strip()
    except Exception as exc:
        return LLMVerification(error=f"llm_request_failed:{exc}")

    # Parse JSON response
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON object from text
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                return LLMVerification(error="llm_invalid_json")
        else:
            return LLMVerification(error="llm_invalid_json")

    confidence = str(parsed.get("confidence", "low")).strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"

    return LLMVerification(
        is_case_report=bool(parsed.get("is_case_report", False)),
        confidence=confidence,
        reasoning=str(parsed.get("reasoning", ""))[:500],
        has_variant_report=bool(parsed.get("has_variant_report", False)),
        variant_details=str(parsed.get("variant_details", ""))[:300],
        model=model,
    )


async def _run_llm_verification_pass(
    records: list[DownloadRecord],
    timeout_sec: int = 60,
    model: str = "",
) -> list[DownloadRecord]:
    """Run LLM verification on all successfully downloaded PDFs.

    Modifies records in-place: sets llm_verification for each PDF.
    Only records with is_case_report=true + confidence=high remain as success=True.
    Failed verifications and non-case-reports are marked success=False.
    """
    candidates = [r for r in records if r.success and r.file_path]
    if not candidates:
        logger.info("LLM verify: no downloaded PDFs to check")
        return records

    logger.info(f"LLM verify: {len(candidates)} PDFs to check")
    verified = 0
    passed = 0

    for r in candidates:
        pdf_path = Path(r.file_path)
        if not pdf_path.exists():
            r.llm_verification = asdict(LLMVerification(error="file_not_found"))
            r.success = False
            r.error = "llm_verify:file_not_found"
            continue

        text = _extract_pdf_text_for_llm(pdf_path)
        if not text:
            r.llm_verification = asdict(LLMVerification(error="pdf_text_empty"))
            r.success = False
            r.error = "llm_verify:pdf_text_empty"
            continue

        result = _verify_case_report_via_llm(
            title=r.title,
            lang=r.lang,
            pdf_text=text,
            timeout_sec=timeout_sec,
            model_override=model,
        )
        r.llm_verification = asdict(result)
        verified += 1

        if result.error:
            logger.warning(
                f"[{r.lang}] LLM verify error for {r.title[:50]}: {result.error}"
            )
            r.success = False
            r.error = f"llm_verify:{result.error}"
        elif result.is_case_report and result.confidence == "high":
            logger.info(
                f"[{r.lang}] ✓ LLM verified: {r.title[:60]} "
                f"(variant={'yes' if result.has_variant_report else 'no'})"
            )
            passed += 1
            # Update literature_type based on LLM
            r.literature_type = "case_report"
        else:
            logger.info(
                f"[{r.lang}] ✗ LLM rejected (confidence={result.confidence}, "
                f"is_case_report={result.is_case_report}): {r.title[:60]}"
            )
            r.success = False
            r.error = (
                f"llm_verify:rejected "
                f"(is_case_report={result.is_case_report}, "
                f"confidence={result.confidence})"
            )

    logger.info(f"LLM verify done: {verified} checked, {passed} passed")
    return records


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
        "--llm-verify", action="store_true",
        help="Download all candidates, then use LLM to verify each PDF "
             "is a genuine case report with variant details. Skips keyword "
             "pre-filter; only high-confidence case reports are kept.",
    )
    parser.add_argument(
        "--llm-model", type=str, default="",
        help="Override LLM model for verification (default: from .env config)",
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
        llm_verify=args.llm_verify,
        llm_model=args.llm_model,
        resume_report=args.resume,
    ))


if __name__ == "__main__":
    main()
