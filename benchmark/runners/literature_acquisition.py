"""Benchmark toolkit: literature acquisition & data analysis.

Usage:
    uv run python benchmark/literature_acquisition/benchmark.py download [--lang zh]
    uv run python benchmark/literature_acquisition/benchmark.py analyze [report.json] [--llm-classify]
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
from typing import Any, Dict, List, Optional, cast

import httpx
import fitz

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import (
    multilingual_acquisition_workflow,
    online_acquisition_workflow,
)
from src.core.config import get_config

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


@dataclass
class MedicalDomainClassification:
    domain: str
    subdomain: str
    confidence: str
    rationale: str
    evidence_excerpt: str
    model: str


# ═══════════════════════════════════════════════════════════════════
# Language search configs (download mode)
# ═══════════════════════════════════════════════════════════════════

LANG_SEARCHES: Dict[str, Dict] = {
    "zh": {
        "code": "zh", "name": "Chinese",
        "queries": [
            # ── 队列研究 ──
            "队列研究 基因突变", "前瞻性队列 癌症",
            "回顾性队列 基因", "队列研究 乳腺癌",
            "队列研究 预后", "队列研究 风险因素 基因",
            "队列研究 肺癌", "队列研究 胃癌",
            "队列研究 肝癌", "队列研究 结直肠癌",
            "队列研究 甲状腺癌", "队列研究 卵巢癌",
            "队列研究 宫颈癌", "队列研究 食管癌",
            "队列研究 BRCA", "队列研究 TP53",
            "队列研究 遗传性肿瘤", "队列研究 基因多态性",
            "队列研究 生存分析", "队列研究 无病生存",
            "队列研究 总生存期", "队列研究 化疗 基因",
            "队列研究 靶向治疗 疗效", "队列研究 免疫治疗",
            # ── 功能实验 ──
            "功能实验 基因", "功能研究 基因突变",
            "体外功能实验 癌症", "功能实验 蛋白表达",
            "功能实验 细胞增殖", "基因功能研究 肿瘤",
            "功能实验 细胞凋亡", "功能实验 细胞迁移",
            "功能实验 细胞侵袭", "功能实验 Western blot",
            "功能实验 荧光素酶", "功能实验 细胞周期",
            "功能实验 siRNA", "功能实验 基因过表达",
            "功能实验 CRISPR", "功能实验 信号通路",
            "功能实验 乳腺癌 细胞", "功能实验 肺癌 细胞",
            "功能实验 胃癌 细胞", "功能实验 肝癌 细胞",
            "功能实验 结直肠癌 细胞", "功能实验 卵巢癌 细胞",
            "功能实验 转录因子", "功能实验 甲基化",
            "功能实验 microRNA", "功能实验 lncRNA",
            "功能实验 蛋白互作", "功能实验 泛素化",
            # ── 基因与癌症综合 ──
            "乳腺癌 基因突变", "癌症 基因测序", "肿瘤 基因检测",
            "病例报告 基因", "基因组测序 癌", "靶向测序 肿瘤",
            "基因突变 功能研究", "乳腺癌 细胞系", "癌症 蛋白表达",
            "肿瘤 凋亡", "基因编辑 癌", "外显子测序 肿瘤",
            "乳腺癌 病例分析", "基因 突变 临床", "癌症 机制研究",
            "肿瘤 增殖 迁移", "基因 敲除 癌", "乳腺癌 免疫组化",
            "癌症 靶向治疗 基因", "肿瘤 基因组 变异",
            "肺癌 EGFR 突变", "胃癌 HER2 扩增",
            "肝癌 TERT 启动子", "结直肠癌 KRAS 突变",
            "甲状腺癌 BRAF 突变", "卵巢癌 BRCA 突变",
            "宫颈癌 HPV 整合", "食管癌 TP53 突变",
            "胰腺癌 KRAS", "前列腺癌 雄激素受体",
            "膀胱癌 FGFR3", "肾癌 VHL 基因",
            "白血病 BCR-ABL", "淋巴瘤 MYC 重排",
            "神经母细胞瘤 ALK", "黑色素瘤 BRAF V600E",
            "骨肉瘤 TP53", "软组织肉瘤 基因融合",
            # ── 技术与方法 ──
            "NGS 肿瘤 panel", "全外显子组测序 癌症",
            "全基因组测序 肿瘤", "RNA-seq 肿瘤",
            "单细胞测序 癌症", "液体活检 ctDNA",
            "循环肿瘤DNA", "甲基化检测 肿瘤",
            "FISH 基因扩增 肿瘤", "PCR 基因突变 检测",
            "免疫组化 肿瘤标记物", "质谱 蛋白质组 肿瘤",
            # ── 遗传与家系 ──
            "遗传性乳腺癌 家系", "Lynch综合征 家系",
            "遗传性胃癌 基因", "家族性腺瘤性息肉病",
            "遗传性卵巢癌 BRCA", "Li-Fraumeni综合征",
            "多发性内分泌腺瘤", "遗传性肾癌 基因",
            "胚系突变 肿瘤", "新生突变 遗传病",
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
# Download mode — uses online_acquisition module (search + gateway)
# ═══════════════════════════════════════════════════════════════════

async def cmd_download(lang_filter: Optional[str] = None) -> None:
    setup_logging()
    stats = BenchmarkStats()
    start = time.monotonic()

    all_langs = ["zh", "ja", "ko", "es", "pt", "ru", "en"]
    if lang_filter:
        all_langs = [lang_filter]
    target_per_lang = 1000

    logger.info("Starting download benchmark")
    logger.info(f"Downloading via online_acquisition_workflow (API + Firecrawl, target {target_per_lang} per lang)")
    logger.info(f"Languages: {', '.join(all_langs)}")

    for lang in all_langs:
        cfg = LANG_SEARCHES[lang]
        lang_code = cfg["code"]
        downloaded = 0
        query_idx = 0
        dest_dir = DOWNLOAD_ROOT / lang_code
        dest_dir.mkdir(parents=True, exist_ok=True)

        seen_files: set[str] = {
            str(p) for p in dest_dir.rglob("*.pdf")
        }

        while downloaded < target_per_lang and query_idx < len(cfg["queries"]):
            query = cfg["queries"][query_idx]
            query_idx += 1

            payload: Dict[str, Any] = {
                "action": "download",
                "query": query,
                "limit": 20,
                "language": lang_code,
                "download_path": str(DOWNLOAD_ROOT),
            }

            stats.total_attempted += 1

            result: Optional[Dict[str, Any]] = None
            try:
                result = await asyncio.wait_for(
                    online_acquisition_workflow(payload),
                    timeout=300,
                )
            except asyncio.TimeoutError:
                logger.info(f"[{lang}] timeout for '{query}' — scanning disk for new files")
            except Exception as exc:
                logger.info(f"[{lang}] workflow failed for '{query}': {exc}")

            items = (result or {}).get("items", [])
            route_info = (result or {}).get("route", {})

            new_files = {str(p) for p in dest_dir.rglob("*.pdf")} - seen_files
            seen_files |= new_files

            for fp in sorted(new_files):
                if downloaded >= target_per_lang:
                    break
                dest = Path(fp)
                if not dest.exists() or dest.stat().st_size == 0:
                    continue

                title = ""
                doi = ""
                source = route_info.get("used", "workflow")
                lit_type = "unclassified"

                for item in items:
                    item_title = item.get("title") or ""
                    if item_title:
                        title = item_title
                        doi = (item.get("doi") or "").strip()
                        lt = item.get("literature_type")
                        if lt:
                            lit_type = lt
                        break

                record = DownloadRecord(
                    lang=lang_code, literature_type=lit_type,
                    title=title, doi=doi,
                    method=source, success=True,
                    file_path=str(dest), file_size=dest.stat().st_size,
                    source_url="", elapsed_ms=0,
                )
                stats.records.append(record)
                stats.total_downloaded += 1
                stats.by_lang[lang] = stats.by_lang.get(lang, 0) + 1
                stats.by_type[lit_type] = stats.by_type.get(lit_type, 0) + 1
                stats.by_method[source] = stats.by_method.get(source, 0) + 1
                downloaded += 1
                logger.info(
                    f"[{lang}] {downloaded}/{target_per_lang} OK "
                    f"{record.file_size // 1024}KB [{lit_type}] via {source}"
                )

            if not new_files:
                logger.info(f"[{lang}] no new files for: {query}")

    stats.elapsed_sec = round(time.monotonic() - start, 1)

    # Save report
    report_path = DOWNLOAD_ROOT / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(asdict(stats), f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"\nDone. {stats.total_downloaded}/{stats.total_attempted} downloaded in {stats.elapsed_sec:.1f}s")
    logger.info(f"Report: {report_path}")



# ═══════════════════════════════════════════════════════════════════
# Multilingual mode — uses multilingual_acquisition_workflow
# ═══════════════════════════════════════════════════════════════════


@dataclass
class MultilingualRunRecord:
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
class MultilingualRunStats:
    queries: List[MultilingualRunRecord] = field(default_factory=list)
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
) -> None:
    """Run multilingual_acquisition_workflow over a list of seed queries.

    Each seed query is internally translated into 6 languages and searched
    in parallel; this loop iterates over distinct *seed* queries.
    Reports include per-search-lang candidate counts and pre-parsed
    (early MinerU) markdown counts on surviving downloads.
    """
    setup_logging()
    out_dir = Path(download_dir) if download_dir else (DOWNLOAD_ROOT / "multilingual")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "multilingual_report.json"

    stats = MultilingualRunStats()
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
        }

        q_start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                multilingual_acquisition_workflow(payload),
                timeout=600,
            )
        except asyncio.TimeoutError:
            stats.queries.append(MultilingualRunRecord(
                query=query, success=False, candidates_total=0,
                warnings=["workflow_timeout"],
                elapsed_sec=round(time.monotonic() - q_start, 2),
            ))
            continue
        except Exception as exc:  # noqa: BLE001
            stats.queries.append(MultilingualRunRecord(
                query=query, success=False, candidates_total=0,
                warnings=[str(exc)[:200]],
                elapsed_sec=round(time.monotonic() - q_start, 2),
            ))
            continue

        candidates = result.get("candidate_links", []) or []
        downloads = result.get("downloads", []) or []
        warnings = result.get("warnings", []) or []

        by_lang: Dict[str, int] = {}
        for c in candidates:
            lang = c.get("search_lang") or "?"
            by_lang[lang] = by_lang.get(lang, 0) + 1

        pre_parsed = sum(1 for d in downloads if d.get("parsed_markdown"))

        record = MultilingualRunRecord(
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
            record.candidates_total, by_lang,
            record.downloads_total, pre_parsed, record.elapsed_sec,
        )

    stats.total_elapsed_sec = round(time.monotonic() - overall_start, 2)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as rf:
        json.dump(asdict(stats), rf, indent=2, ensure_ascii=False)

    logger.info(
        "Multilingual benchmark complete: queries={} candidates={} downloads={} pre_parsed={}",
        len(stats.queries), stats.total_candidates,
        stats.total_downloads, stats.total_pre_parsed,
    )
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


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a JSON object from model output."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None
    return None


def _extract_pdf_text_for_classification(pdf_path: Path, max_pages: int, max_chars: int) -> str:
    """Extract plain text from the first pages of a PDF for lightweight domain classification."""
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return ""

    chunks: List[str] = []
    try:
        page_count = min(max_pages, len(doc))
        for i in range(page_count):
            txt = cast(str, doc[i].get_text("text") or "")
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                chunks.append(txt)
            if sum(len(c) for c in chunks) >= max_chars:
                break
    finally:
        doc.close()

    merged = "\n".join(chunks)
    return merged[:max_chars]


def _classify_medical_domain_via_llm(
    *,
    title: str,
    lang: str,
    literature_type: str,
    pdf_text: str,
    timeout_sec: int,
) -> tuple[Optional[MedicalDomainClassification], str]:
    """Classify a paper's medical domain using configured default LLM."""
    cfg = get_config()
    model_name = (cfg.llm.model or "").strip()
    base_url = (cfg.llm.base_url or "").strip().rstrip("/")
    api_key = (cfg.llm.api_key or "").strip()

    if not model_name:
        return None, "missing_llm_model"
    if not base_url:
        return None, "missing_llm_base_url"

    allowed_domains = [
        "oncology", "genetics", "hematology", "cardiology", "neurology", "endocrinology",
        "immunology", "infectious_disease", "nephrology", "gastroenterology", "pulmonology",
        "dermatology", "obstetrics_gynecology", "pediatrics", "psychiatry", "ophthalmology",
        "orthopedics", "otolaryngology", "urology", "pathology", "radiology", "surgery",
        "critical_care", "public_health", "other", "unknown",
    ]
    system_prompt = (
        "You are a medical literature triage assistant. "
        "Given title and PDF excerpt, classify the primary medical domain. "
        "Return strict JSON only with keys: domain, subdomain, confidence, rationale, evidence_excerpt. "
        f"Domain must be one of: {', '.join(allowed_domains)}. "
        "confidence must be one of: high, medium, low."
    )
    user_prompt = (
        f"language={lang}\n"
        f"literature_type={literature_type}\n"
        f"title={title or 'N/A'}\n\n"
        "PDF excerpt:\n"
        f"{pdf_text[:12000]}"
    )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: Dict[str, Any] = {
        "model": model_name,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }

    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            resp = client.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    except Exception as exc:
        return None, f"llm_request_failed:{exc}"

    parsed = _extract_json_object(content)
    if not parsed:
        return None, "llm_invalid_json"

    domain = str(parsed.get("domain", "unknown")).strip().lower().replace(" ", "_")
    if domain not in allowed_domains:
        domain = "unknown"

    confidence = str(parsed.get("confidence", "low")).strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"

    result = MedicalDomainClassification(
        domain=domain,
        subdomain=str(parsed.get("subdomain", "")).strip()[:80],
        confidence=confidence,
        rationale=str(parsed.get("rationale", "")).strip()[:400],
        evidence_excerpt=str(parsed.get("evidence_excerpt", "")).strip()[:400],
        model=model_name,
    )
    return result, ""


def _run_llm_domain_classification(
    records: List[Dict[str, Any]],
    *,
    max_pages: int,
    max_chars: int,
    timeout_sec: int,
    force: bool,
) -> None:
    """Populate per-record medical domain labels via PDF text + LLM."""
    candidates = [r for r in records if r.get("success") and r.get("file_path")]
    logger.info(f"LLM domain classification: candidates={len(candidates)}")

    done = 0
    skipped = 0
    failed = 0

    for rec in candidates:
        existing = rec.get("medical_domain")
        if existing and not force:
            skipped += 1
            continue

        pdf_path = Path(str(rec.get("file_path") or ""))
        if not pdf_path.exists():
            rec["medical_domain"] = {
                "domain": "unknown",
                "subdomain": "",
                "confidence": "low",
                "rationale": "",
                "evidence_excerpt": "",
                "model": "",
                "error": "file_not_found",
            }
            failed += 1
            continue

        text = _extract_pdf_text_for_classification(pdf_path, max_pages=max_pages, max_chars=max_chars)
        if not text:
            rec["medical_domain"] = {
                "domain": "unknown",
                "subdomain": "",
                "confidence": "low",
                "rationale": "",
                "evidence_excerpt": "",
                "model": "",
                "error": "pdf_text_empty",
            }
            failed += 1
            continue

        result, err = _classify_medical_domain_via_llm(
            title=str(rec.get("title") or ""),
            lang=str(rec.get("lang") or ""),
            literature_type=str(rec.get("literature_type") or ""),
            pdf_text=text,
            timeout_sec=timeout_sec,
        )
        if result:
            rec["medical_domain"] = asdict(result)
            done += 1
        else:
            rec["medical_domain"] = {
                "domain": "unknown",
                "subdomain": "",
                "confidence": "low",
                "rationale": "",
                "evidence_excerpt": "",
                "model": "",
                "error": err or "unknown_error",
            }
            failed += 1

    logger.info(f"LLM domain classification done={done}, skipped={skipped}, failed={failed}")


def cmd_analyze(
    report_path: Optional[Path] = None,
    *,
    llm_classify: bool = False,
    llm_max_pages: int = 4,
    llm_max_chars: int = 12000,
    llm_timeout: int = 60,
    llm_force: bool = False,
) -> None:
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
        rate_pct = n_ok / max(n_all, 1) * 100
        name = LANG_NAMES.get(lang, lang)
        print(f"  {name:<14} {n_ok:>4} {n_all:>6} {rate_pct:>6.1f}%  {_bar(n_ok, n_all)}")

    # ── By Language × Literature Type (downloaded only) ──
    lang_type_counts: Dict[str, Dict[str, int]] = {}
    for r in ok_records:
        lang = str(r.get("lang") or "")
        t = _norm_type(str(r.get("literature_type") or ""))
        lang_type_counts.setdefault(lang, {})
        lang_type_counts[lang][t] = lang_type_counts[lang].get(t, 0) + 1

    all_types = ["case_report", "sequencing", "functional", "unclassified"]
    print(f"\n{'─' * 64}")
    print("  LANGUAGE × LITERATURE TYPE (downloaded only)")
    print(f"{'─' * 64}")
    header = f"  {'Language':<14} {'Total':>5} " + " ".join(f"{t[:10]:>10}" for t in all_types)
    print(header)
    print(f"  {'─' * 13} {'─' * 5} " + " ".join(f"{'─' * 10}" for _ in all_types))
    for lang in sorted(lang_type_counts):
        name = LANG_NAMES.get(lang, lang)
        row = lang_type_counts[lang]
        total_lang = sum(row.values())
        cols = " ".join(f"{row.get(t, 0):>10}" for t in all_types)
        print(f"  {name:<14} {total_lang:>5} {cols}")

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

    # Optional LLM medical-domain classification
    if llm_classify:
        logger.info("\nRunning LLM medical-domain classification from PDF content...")
        _run_llm_domain_classification(
            records,
            max_pages=llm_max_pages,
            max_chars=llm_max_chars,
            timeout_sec=llm_timeout,
            force=llm_force,
        )

    domain_counts = Counter(
        str((r.get("medical_domain") or {}).get("domain") or "unknown")
        for r in ok_records
        if r.get("medical_domain")
    )
    if domain_counts:
        print(f"\n{'─' * 64}")
        print("  MEDICAL DOMAIN (LLM, downloaded only)")
        print(f"{'─' * 64}")
        for d, cnt in domain_counts.most_common():
            print(f"  {d:<24} {cnt:>4}  {_bar(cnt, len(ok_records))}")

    domain_by_lang: Dict[str, Dict[str, int]] = {}
    for r in ok_records:
        if not r.get("medical_domain"):
            continue
        lang = str(r.get("lang") or "")
        domain = str((r.get("medical_domain") or {}).get("domain") or "unknown")
        domain_by_lang.setdefault(lang, {})
        domain_by_lang[lang][domain] = domain_by_lang[lang].get(domain, 0) + 1

    data["analysis_summary"] = {
        "by_language_and_literature_type": lang_type_counts,
        "by_medical_domain": dict(domain_counts),
        "by_language_and_medical_domain": domain_by_lang,
        "llm_classification_enabled": llm_classify,
    }

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
    p_an.add_argument("--llm-classify", action="store_true", help="Use LLM to classify medical domain from PDFs")
    p_an.add_argument("--llm-max-pages", type=int, default=4, help="Max pages extracted from each PDF for LLM")
    p_an.add_argument("--llm-max-chars", type=int, default=12000, help="Max extracted chars sent to LLM")
    p_an.add_argument("--llm-timeout", type=int, default=60, help="LLM request timeout in seconds")
    p_an.add_argument("--llm-force", action="store_true", help="Reclassify records even if medical_domain exists")

    p_ml = sub.add_parser(
        "multilingual",
        help="Run multilingual_acquisition_workflow on seed queries",
    )
    p_ml.add_argument("--query", type=str, default=None,
                      help="Single seed query (English recommended)")
    p_ml.add_argument("--query-file", type=str, default=None,
                      help="Plain text query file; one seed query per line")
    p_ml.add_argument("--download-dir", type=str, default=None,
                      help="Override download directory (default: downloads/multilingual)")
    p_ml.add_argument("--limit", type=int, default=12,
                      help="Per-request candidate limit across all 6 languages")
    p_ml.add_argument("--dry-run", action="store_true",
                      help="Search only, do not download files")

    args = parser.parse_args()

    if args.cmd == "download":
        asyncio.run(cmd_download(args.lang))
    elif args.cmd == "analyze":
        cmd_analyze(
            Path(args.path) if args.path else None,
            llm_classify=args.llm_classify,
            llm_max_pages=args.llm_max_pages,
            llm_max_chars=args.llm_max_chars,
            llm_timeout=args.llm_timeout,
            llm_force=args.llm_force,
        )
    elif args.cmd == "multilingual":
        seeds: List[str] = []
        if args.query:
            seeds = [args.query]
        elif args.query_file:
            qfile = Path(args.query_file)
            if not qfile.exists():
                logger.error(f"Query file not found: {qfile}")
                sys.exit(1)
            seeds = [
                ln.strip() for ln in qfile.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")
            ]
        else:
            logger.error("multilingual requires --query or --query-file")
            sys.exit(1)
        asyncio.run(cmd_multilingual(
            seeds,
            download_dir=args.download_dir,
            limit=args.limit,
            dry_run=args.dry_run,
        ))


if __name__ == "__main__":
    main()
