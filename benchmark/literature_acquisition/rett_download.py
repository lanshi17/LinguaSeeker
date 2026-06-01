"""Rett syndrome / MECP2 multilingual case report PDF acquisition.

Uses the project's online acquisition module (search_multilingual) for
language-routed regional search, then downloads PDFs and filters for
case_report literature type.

Usage (run from project root):
    uv run --directory backend python ../benchmark/literature_acquisition/rett_download.py
    uv run --directory backend python ../benchmark/literature_acquisition/rett_download.py --lang zh
    uv run --directory backend python ../benchmark/literature_acquisition/rett_download.py --lang en --dry-run
    uv run --directory backend python ../benchmark/literature_acquisition/rett_download.py --target 10

    # To skip literature type filtering (download all candidates):
    # Set "literature_types": [] in rett_config.json
"""

from __future__ import annotations

import argparse
import asyncio
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
) -> List[DownloadRecord]:
    """Search + download for one language. Returns list of records."""
    records: List[DownloadRecord] = []
    queries = list(lang_cfg.get("queries", []))
    downloaded = 0
    query_idx = 0

    while downloaded < target and query_idx < len(queries):
        query = queries[query_idx]
        query_idx += 1

        # search_multilingual may try 3-7 providers sequentially;
        # use a longer timeout than individual downloads.
        search_timeout = max(timeout_s * 3, 180)

        async with sem:
            try:
                candidates = await asyncio.wait_for(
                    search_multilingual(
                        target=query,
                        disease=disease,
                        language=lang_code,
                        candidate_limit=candidate_limit,
                    ),
                    timeout=search_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"[{lang_code}] search_multilingual timed out for: {query}")
                continue
            except Exception as exc:
                logger.warning(f"[{lang_code}] search_multilingual failed for '{query}': {exc}")
                continue

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


async def run(config: Dict[str, Any], lang_filter: Optional[str], dry_run: bool) -> DownloadStats:
    """Main orchestration: iterate languages, search, download, classify."""
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
        lang_target = _resolve_target(lang_code)
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
        )
        stats.records.extend(records)

        ok_count = sum(1 for r in records if r.success)
        logger.info(
            f"[{lang_code}] {ok_count}/{len(records)} downloaded "
            f"(target: {lang_target})"
        )

    # Aggregate stats
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

    asyncio.run(run(config, lang_filter=args.lang, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
