"""Benchmark toolkit: literature acquisition & data analysis.

Usage:
    uv run python benchmark/literature_acquisition/benchmark.py download [--lang zh]
    uv run python benchmark/literature_acquisition/benchmark.py analyze [report.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
import hashlib
from loguru import logger
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
    OnlineAcquisitionItem,
)
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.literature_type_classifier import (
    classify_item,
)

# ═══════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════

DOWNLOAD_ROOT = Path(__file__).resolve().parent / "downloads"
REPORT_PATH = DOWNLOAD_ROOT / "report.json"

MODULE_DIR = Path(__file__).resolve().parent
LOG_DIR = MODULE_DIR / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging(log_dir: Path = LOG_DIR, level: str = "INFO") -> None:
    """Configure loguru to log to console and rotating file under module log dir."""
    logger.remove()
    # console
    logger.add(sys.stderr, level=level, format="{time:YYYY-MM-DD HH:mm:ss} {level: <8} {message}")
    # file with rotation and retention
    logger.add(str(log_dir / "benchmark.log"), rotation="5 MB", retention=5, encoding="utf-8", level=level,
               format="{time:YYYY-MM-DD HH:mm:ss} {level: <8} {message}")
    # reduce noise from httpx/urllib3
    import logging as _pylogging
    _pylogging.getLogger("httpx").setLevel(_pylogging.WARNING)
    _pylogging.getLogger("urllib3").setLevel(_pylogging.WARNING)

LANG_NAMES: Dict[str, str] = {
    "zh": "Chinese", "ja": "Japanese", "es": "Spanish",
    "pt": "Portuguese", "ru": "Russian", "en": "English", "ko": "Korean",
}

# ═══════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════


@dataclass
class DownloadRecord:
    lang: str
    literature_type: str
    title: str
    doi: str
    method: str
    success: bool
    file_path: str = ""
    file_size: int = 0
    source_url: str = ""
    error: str = ""
    elapsed_ms: int = 0


@dataclass
class BenchmarkStats:
    total_attempted: int = 0
    total_downloaded: int = 0
    by_lang: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_method: Dict[str, int] = field(default_factory=dict)
    elapsed_sec: float = 0.0
    records: List[DownloadRecord] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# Language search configs (download mode)
# ═══════════════════════════════════════════════════════════════════

LANG_SEARCHES: Dict[str, Dict] = {
    "zh": {
        "code": "zh", "name": "Chinese",
        "queries": [
            "乳腺癌 基因突变", "癌症 基因测序", "肿瘤 基因检测",
            "病例报告 基因", "基因组测序 癌", "靶向测序 肿瘤",
            "基因突变 功能研究", "乳腺癌 细胞系", "癌症 蛋白表达",
            "肿瘤 凋亡", "基因编辑 癌", "外显子测序 肿瘤",
            "乳腺癌 病例分析", "基因 突变 临床", "癌症 机制研究",
            "肿瘤 增殖 迁移", "基因 敲除 癌", "乳腺癌 免疫组化",
            "癌症 靶向治疗 基因", "肿瘤 基因组 变异",
        ],
    },
    "ja": {
        "code": "ja", "name": "Japanese",
        "queries": [
            "乳癌 遺伝子変異", "がん 遺伝子検査", "腫瘍 ゲノム",
            "症例報告 遺伝子", "遺伝子シークエンス がん", "ターゲットシーケンス 腫瘍",
            "遺伝子変異 機能解析", "乳癌 細胞株", "がん タンパク質発現",
            "腫瘍 アポトーシス", "遺伝子編集 がん", "エクソームシーケンシング",
            "乳癌 症例研究", "遺伝子 変異 臨床", "がん メカニズム",
            "腫瘍 増殖 遊走", "遺伝子 ノックダウン", "乳癌 免疫染色",
            "がん 分子標的 遺伝子", "腫瘍 ゲノム 変異",
        ],
    },
    "ko": {
        "code": "ko", "name": "Korean",
        "queries": [
            "breast cancer", "gastric cancer", "lung cancer",
            "liver cancer", "colorectal cancer", "thyroid cancer",
            "case report", "gene mutation", "genetic testing",
            "cancer genome", "tumor marker", "BRCA mutation",
            "cancer diagnosis", "cancer treatment", "cancer prognosis",
            "immunohistochemistry", "gene sequencing", "mutation analysis",
            "oncogene", "tumor suppressor",
        ],
    },
    "es": {
        "code": "es", "name": "Spanish",
        "queries": [
            "cáncer mama mutación gen", "genómica cáncer secuenciación",
            "tumor gen panel", "caso clínico genético",
            "secuenciación genómica cáncer", "gen mutación funcional",
            "cáncer línea celular", "tumor expresión proteica",
            "apoptosis cáncer gen", "edición genética tumor",
            "exoma secuenciación cáncer", "caso clínico mutación",
            "gen supresor tumoral", "cáncer mama genómica",
            "tumor proliferación migración", "gen silenciamiento cáncer",
            "cáncer mama inmunohistoquímica", "terapia dirigida gen",
            "tumor genómica variante", "secuenciación panel cáncer",
        ],
    },
    "pt": {
        "code": "pt", "name": "Portuguese",
        "queries": [
            "câncer mama mutação gene", "genômica câncer sequenciamento",
            "tumor gene painel", "relato caso genética",
            "sequenciamento genômico câncer", "gene mutação funcional",
            "câncer linha celular", "tumor expressão proteica",
            "apoptose câncer gene", "edição genética tumor",
            "exoma sequenciamento câncer", "relato caso mutação",
            "gene supressor tumoral", "câncer mama genômica",
            "tumor proliferação migração", "gene silenciamento câncer",
            "câncer mama imuno-histoquímica", "terapia alvo gene",
            "tumor genômica variante", "sequenciamento painel câncer",
        ],
    },
    "ru": {
        "code": "ru", "name": "Russian",
        "queries": [
            "BRCA1", "BRCA2", "молочная железа ген", "опухоль ДНК",
            "генетика рак", "рак лечение генетический", "мутация ген рак",
            "секвенирование рак", "геном опухоль", "рак молочной железы",
            "онкология ДНК", "ген супрессор", "рак клетка ген",
            "опухоль мутация", "таргетная терапия рак", "рак геномный",
            "иммуногистохимия рак", "генетический анализ опухоль",
            "рак экспрессия гена", "молочная железа мутация",
        ],
    },
    "en": {
        "code": "en", "name": "English",
        "queries": [
            "BRCA1 case report breast cancer",
            "cancer gene panel sequencing study",
            "BRCA1 functional characterization in vitro",
            "tumor suppressor gene functional study",
            "next-generation sequencing cancer diagnosis",
            "cancer cell line functional assay",
            "whole exome sequencing tumor",
            "BRCA2 mutation case series",
            "targeted sequencing hereditary cancer",
            "CRISPR gene editing cancer cells",
            "gene knockdown tumor suppression",
            "whole genome sequencing pediatric cancer",
            "Sanger sequencing BRCA1 validation",
            "luciferase assay gene promoter",
            "Western blot protein expression cancer",
            "xenograft tumor model gene therapy",
            "RT-qPCR gene expression breast cancer",
            "immunohistochemistry BRCA1 tumor",
            "NGS panel clinical oncology",
            "proliferation assay cancer cell lines",
        ],
    },
}


def _sanitize(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", name)[:80]

# ═══════════════════════════════════════════════════════════════════
# Download mode
# ═══════════════════════════════════════════════════════════════════

async def _download_from_url(url: str, dest: Path, timeout: int = 30) -> bool:
    """Download PDF from URL, scan HTML for PDF links if needed."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        logger.debug(f"Fetching URL: {url}")
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, verify=False,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 ACMG-Lingua/1.0"},
        ) as client:
            r = await client.get(url)
            if r.content[:4] == b"%PDF":
                dest.write_bytes(r.content)
                logger.info(f"Wrote PDF: {dest} ({len(r.content)} bytes)")
                return True
            if b"<html" in r.content[:2048].lower():
                # Try .pdf links, /bitstream/ paths (DSpace), and download handlers
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
                            logger.info(f"Wrote PDF: {dest} ({len(r2.content)} bytes) via {abs_url}")
                            return True
                    except Exception:
                        logger.debug(f"Failed to get nested PDF link {abs_url}")
                        continue
    except Exception:
        logger.exception(f"Exception while downloading URL: {url}")
        pass
    return False


async def _try_openalex_oa_inner(
    lang_code: str, query: str, dest_dir: Path, fname_prefix: str,
) -> Optional[DownloadRecord]:
    """Search OpenAlex for OA articles, try downloading the first match."""
    url = (
        f"https://api.openalex.org/works?search={query}"
        f"&filter=language:{lang_code},is_oa:true&per_page=5&mailto=bench@acmg-lingua"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
        data = r.json()
    for i, w in enumerate(data.get("results", [])):
        oa_url = (w.get("open_access") or {}).get("oa_url", "")
        if not oa_url or any(s in oa_url for s in ["dbpia", "kiss", "kmbase", "ndsl"]):
            continue
        title = w.get("title", "")
        doi = w.get("doi", "")
        dest = dest_dir / f"{_sanitize(fname_prefix)}_{i}.pdf"
        t0 = time.monotonic()
        ok = await _download_from_url(oa_url, dest)
        elapsed = int((time.monotonic() - t0) * 1000)
        if ok:
            cls = classify_item(OnlineAcquisitionItem(source="openalex", title=title, doi=doi))
            lit_type = cls.value if cls else "unclassified"
            return DownloadRecord(
                lang=lang_code, literature_type=lit_type,
                title=title, doi=doi,
                method="openalex_oa", success=True,
                file_path=str(dest), file_size=dest.stat().st_size,
                source_url=oa_url, elapsed_ms=elapsed,
            )
    return None


async def _try_openalex_oa(
    lang_code: str, query: str, dest_dir: Path, fname_prefix: str,
) -> Optional[DownloadRecord]:
    """Search OpenAlex with overall timeout per query."""
    try:
        return await asyncio.wait_for(
            _try_openalex_oa_inner(lang_code, query, dest_dir, fname_prefix),
            timeout=45,
        )
    except (asyncio.TimeoutError, Exception):
        return None


async def cmd_download(lang_filter: Optional[str] = None) -> None:
    setup_logging()
    stats = BenchmarkStats()
    start = time.monotonic()

    all_langs = ["zh", "ja", "ko", "es", "pt", "ru", "en"]
    if lang_filter:
        all_langs = [lang_filter]
    target_per_lang = 20

    logger.info("Starting download benchmark")
    logger.info(f"Downloading via OpenAlex OA (target {target_per_lang} per lang)")
    logger.info(f"Languages: {', '.join(all_langs)}")

    for lang in all_langs:
        cfg = LANG_SEARCHES[lang]
        downloaded = 0
        query_idx = 0

        while downloaded < target_per_lang and query_idx < len(cfg["queries"]):
            query = cfg["queries"][query_idx]
            query_idx += 1
            dest_dir = DOWNLOAD_ROOT / lang
            fname = f"{lang}_{downloaded}"

            record = await _try_openalex_oa(cfg["code"], query, dest_dir, fname)
            if record:
                stats.records.append(record)
                stats.total_attempted += 1
                stats.total_downloaded += 1
                stats.by_lang[lang] = stats.by_lang.get(lang, 0) + 1
                stats.by_type[record.literature_type] = stats.by_type.get(record.literature_type, 0) + 1
                stats.by_method[record.method] = stats.by_method.get(record.method, 0) + 1
                downloaded += 1
                msg = f"[{lang}] {downloaded}/{target_per_lang} OK {record.file_size // 1024}KB [{record.literature_type}]"
                logger.info(msg)
            else:
                stats.total_attempted += 1
                logger.debug(f"No result for query '{query}' in {lang}")

    stats.elapsed_sec = round(time.monotonic() - start, 1)

    # Save report
    report_path = DOWNLOAD_ROOT / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(asdict(stats), f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"\nDone. {stats.total_downloaded}/{stats.total_attempted} downloaded in {stats.elapsed_sec:.1f}s")
    logger.info(f"Report: {report_path}")



# ═══════════════════════════════════════════════════════════════════
# Analyze mode
# ═══════════════════════════════════════════════════════════════════

def _fmt_size(n: int) -> str:
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n} B"


def _bar(count: int, total: int, width: int = 30) -> str:
    filled = int(count / max(total, 1) * width)
    return "█" * filled + "░" * (width - filled)


def _norm_type(t: str) -> str:
    t_upper = t.upper()
    if "CASE_REPORT" in t_upper or "case_report" in t:
        return "case_report"
    if "SEQUENCING" in t_upper or "sequencing" in t:
        return "sequencing"
    if "FUNCTIONAL" in t_upper or "functional" in t:
        return "functional"
    return "unclassified"


def cmd_analyze(report_path: Optional[Path] = None) -> None:
    path = report_path or REPORT_PATH
    if not path.exists():
        print(f"Report not found: {path}")
        sys.exit(1)

    setup_logging()
    logger.info(f"Starting analysis for report: {path}")

    with open(path) as f:
        data = json.load(f)

    records: List[Dict[str, Any]] = data["records"]
    total_attempted: int = data["total_attempted"]
    total_downloaded: int = data["total_downloaded"]
    elapsed: float = data["elapsed_sec"]

    ok_records = [r for r in records if r["success"]]
    fail_records = [r for r in records if not r["success"]]

    # === Validation & de-duplication ===
    # Compute file-level validation information (exists, sha256) and detect duplicates
    sha_map: Dict[str, List[int]] = {}
    file_path_map: Dict[str, List[int]] = {}
    suspicious_count = 0
    for i, r in enumerate(records):
        r.setdefault("_validation", {})
        val = r["_validation"]
        val["exists"] = False
        val["sha256"] = None
        val["duplicate"] = False
        val["suspicious"] = []

        fp = r.get("file_path") or ""
        if not fp:
            val["suspicious"].append("missing_file_path")
            suspicious_count += 1
            continue

        p = Path(fp)
        if not p.exists():
            val["suspicious"].append("file_not_found")
            suspicious_count += 1
            continue

        try:
            val["exists"] = True
            # compute sha256 for real de-duplication
            h = hashlib.sha256()
            with p.open("rb") as fh:
                for chunk in iter(lambda: fh.read(8192), b""):
                    h.update(chunk)
            s = h.hexdigest()
            val["sha256"] = s
            sha_map.setdefault(s, []).append(i)
            file_path_map.setdefault(str(p), []).append(i)

            # suspicious heuristics
            if r.get("file_size", 0) <= 0:
                val["suspicious"].append("zero_file_size")
            if r.get("elapsed_ms", 0) <= 0:
                val["suspicious"].append("zero_elapsed_ms")
            if not r.get("title"):
                val["suspicious"].append("missing_title")
            if not r.get("source_url") and not r.get("doi"):
                val["suspicious"].append("missing_source")
            if val["suspicious"]:
                suspicious_count += 1
        except Exception as e:
            val["suspicious"].append(f"read_error:{e}")
            suspicious_count += 1

    # mark duplicates by identical sha256
    duplicate_groups = [ids for ids in sha_map.values() if len(ids) > 1]
    for grp in duplicate_groups:
        for idx in grp:
            records[idx]["_validation"]["duplicate"] = True

    # also mark duplicates by identical file path (defensive)
    for ids in file_path_map.values():
        if len(ids) > 1:
            for idx in ids:
                records[idx]["_validation"]["duplicate"] = True

    unique_files = len(sha_map)
    dup_count = sum(1 for r in records if r.get("_validation", {}).get("duplicate"))

    # ── Overview ──
    logger.info("=" * 64)
    logger.info("  BENCHMARK DOWNLOAD REPORT — DATA ANALYSIS")
    logger.info("=" * 64)
    logger.info(f"  Attempted:  {total_attempted}")
    logger.info(f"  Downloaded: {total_downloaded}")
    rate = total_downloaded / max(total_attempted, 1) * 100
    logger.info(f"  Success:    {rate:.1f}%")
    logger.info(f"  Elapsed:    {elapsed:.1f}s ({elapsed / 60:.1f} min)")
    if ok_records:
        avg_ms = sum(r["elapsed_ms"] for r in ok_records) / len(ok_records)
        logger.info(f"  Avg DL:     {avg_ms / 1000:.1f}s per file")

    # Validation summary
    logger.info(f"\n  Unique files (by sha256): {unique_files}")
    logger.info(f"  Duplicate records detected: {dup_count}")
    logger.info(f"  Suspicious records flagged: {suspicious_count}")

    # ── By Language ──
    lang_ok = Counter(r["lang"] for r in ok_records)
    lang_all = Counter(r["lang"] for r in records)
    print(f"\n{'─' * 64}")
    print("  BY LANGUAGE")
    print(f"{'─' * 64}")
    print(f"  {'Language':<14} {'DL':>4} {'Total':>6} {'Rate':>7}  {'Visual'}")
    print(f"  {'─' * 13}  {'─' * 4} {'─' * 6} {'─' * 7}  {'─' * 20}")
    for lang in sorted(lang_all, key=lambda x: lang_all[x], reverse=True):
        n_ok = lang_ok.get(lang, 0)
        n_all = lang_all[lang]
        r = n_ok / max(n_all, 1) * 100
        name = LANG_NAMES.get(lang, lang)
        print(f"  {name:<14} {n_ok:>4} {n_all:>6} {r:>6.1f}%  {_bar(n_ok, n_all)}")

    # ── By Literature Type ──
    type_ok = Counter(_norm_type(r["literature_type"]) for r in ok_records)
    print(f"\n{'─' * 64}")
    print("  BY LITERATURE TYPE (downloaded only)")
    print(f"{'─' * 64}")
    print(f"  {'Type':<18} {'Count':>6}  {'Visual'}")
    print(f"  {'─' * 17}  {'─' * 6}  {'─' * 20}")
    for t, cnt in type_ok.most_common():
        print(f"  {t:<18} {cnt:>6}  {_bar(cnt, len(ok_records))}")
    unclass = type_ok.get("unclassified", 0)
    class_rate = (len(ok_records) - unclass) / max(len(ok_records), 1) * 100
    print(f"\n  Classification rate: {class_rate:.1f}% ({len(ok_records) - unclass}/{len(ok_records)} classified)")

    # ── By Method ──
    method_ok = Counter(r["method"] for r in ok_records)
    logger.info(f"\n{'─' * 64}")
    logger.info("  BY DOWNLOAD METHOD")
    logger.info(f"{'─' * 64}")
    for m, cnt in method_ok.most_common():
        logger.info(f"  {m:<22} {cnt:>4}")

    # write validated report copy
    # Write validated report back to report.json (replace original)
    try:
        validated_path = path.parent / "report.json"
        with open(validated_path, "w") as vf:
            json.dump(data, vf, indent=2, ensure_ascii=False)
        logger.info(f"\n  Validated report written to: {validated_path}")
    except Exception:
        logger.exception("Failed to write validated report.json")

    # Suspicious records CSV export was removed per request.

    # ── File Size Stats ──
    sizes = [r["file_size"] for r in ok_records if r["file_size"] > 0]
    if sizes:
        print(f"\n{'─' * 64}")
        print("  FILE SIZE DISTRIBUTION")
        print(f"{'─' * 64}")
        sizes.sort()
        total_bytes = sum(sizes)
        print(f"  Total:   {_fmt_size(total_bytes)}")
        print(f"  Min:     {_fmt_size(sizes[0])}")
        print(f"  Max:     {_fmt_size(sizes[-1])}")
        print(f"  Median:  {_fmt_size(sizes[len(sizes) // 2])}")
        print(f"  Mean:    {_fmt_size(total_bytes // len(sizes))}")

        lang_sizes: Dict[str, List[int]] = {}
        for r in ok_records:
            if r["file_size"] > 0:
                lang_sizes.setdefault(r["lang"], []).append(r["file_size"])
        print(f"\n  {'Language':<14} {'Total Size':>12} {'Avg Size':>12} {'Files':>6}")
        print(f"  {'─' * 13}  {'─' * 12} {'─' * 12} {'─' * 6}")
        for lang in sorted(lang_sizes, key=lambda x: sum(lang_sizes[x]), reverse=True):
            ss = lang_sizes[lang]
            name = LANG_NAMES.get(lang, lang)
            print(f"  {name:<14} {_fmt_size(sum(ss)):>12} {_fmt_size(sum(ss) // len(ss)):>12} {len(ss):>6}")

    # ── Download Time Stats ──
    times = [r["elapsed_ms"] for r in ok_records if r["elapsed_ms"] > 0]
    if times:
        print(f"\n{'─' * 64}")
        print("  DOWNLOAD TIME DISTRIBUTION")
        print(f"{'─' * 64}")
        times.sort()
        print(f"  Min:     {times[0] / 1000:.1f}s")
        print(f"  Max:     {times[-1] / 1000:.1f}s")
        print(f"  Median:  {times[len(times) // 2] / 1000:.1f}s")
        print(f"  Mean:    {sum(times) / len(times) / 1000:.1f}s")

    # ── Failure Analysis ──
    if fail_records:
        err_counts = Counter(r["error"] for r in fail_records)
        print(f"\n{'─' * 64}")
        print(f"  FAILURE ANALYSIS ({len(fail_records)} failures)")
        print(f"{'─' * 64}")
        for err, cnt in err_counts.most_common():
            print(f"  {err:<30} {cnt:>4}")

    # ── Per-Language Detail ──
    print(f"\n{'─' * 64}")
    print("  PER-LANGUAGE DETAIL")
    print(f"{'─' * 64}")
    for lang in sorted(lang_all):
        name = LANG_NAMES.get(lang, lang)
        lang_records = [r for r in records if r["lang"] == lang]
        lang_success = [r for r in lang_records if r["success"]]
        print(f"\n  [{name}] {len(lang_success)}/{len(lang_records)} downloaded")
        for r in lang_success:
            t = _norm_type(r["literature_type"])
            title = (r["title"] or "")[:65]
            sz = _fmt_size(r["file_size"])
            print(f"    [{t:<13}] {sz:>8}  {title}")

    print(f"\n{'=' * 64}")


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark toolkit for literature download & analysis")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dl = sub.add_parser("download", help="Download literature via OpenAlex OA")
    p_dl.add_argument("--lang", help="Filter to single language code (e.g. zh, ko)")


    p_an = sub.add_parser("analyze", help="Print analysis of report.json")
    p_an.add_argument("path", nargs="?", help="Path to report.json (default: downloads/report.json)")

    args = parser.parse_args()

    if args.cmd == "download":
        asyncio.run(cmd_download(args.lang))
    elif args.cmd == "analyze":
        cmd_analyze(Path(args.path) if args.path else None)


if __name__ == "__main__":
    main()
