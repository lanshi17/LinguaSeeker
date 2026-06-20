"""Filter downloaded literature for genetic variant evidence.

Two-tier approach:
  Tier 1 — regex/keyword pre-filter (fast, no LLM)
  Tier 2 — LLM classification for borderline papers

Usage:
    cd backend
    uv run python ../benchmark/runners/filter_variant_evidence.py --dry-run --keyword-only
    uv run python ../benchmark/runners/filter_variant_evidence.py
    uv run python ../benchmark/runners/filter_variant_evidence.py --lang en
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import fitz
import httpx
from loguru import logger
from benchmark.config.defaults import (
    DEFAULT_FILTER_INPUT_DIRS as DEFAULT_INPUT_DIRS,
    DEFAULT_FILTER_OUTPUT_DIR as DEFAULT_OUTPUT_DIR,
    FILTER_TIER1_KEEP_THRESHOLD as TIER1_KEEP_THRESHOLD,
    FILTER_TIER1_REJECT_THRESHOLD as TIER1_REJECT_THRESHOLD,
)

# ═══════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"


# ═══════════════════════════════════════════════════════════════════
# Genetic variant keyword dictionaries (per language)
# ═══════════════════════════════════════════════════════════════════

VARIANT_KEYWORDS: Dict[str, List[str]] = {
    "en": [
        "variant", "mutation", "polymorphism", "SNV", "SNP", "deletion",
        "insertion", "frameshift", "nonsense", "missense", "splice site",
        "pathogenic", "likely pathogenic", "benign", "VUS",
        "loss of function", "gain of function", "truncating",
        "allele", "genotype", "heterozygous", "homozygous", "hemizygous",
        "de novo", "germline mutation", "somatic mutation",
        "copy number", "CNV", "LOH", "loss of heterozygosity",
        "exon", "intron", "promoter", "splice donor", "splice acceptor",
        "nucleotide change", "amino acid change", "protein change",
        "whole exome", "whole genome", "gene panel",
        "ClinVar", "HGMD", "gnomAD", "dbSNP",
    ],
    "zh": [
        "突变", "变异", "多态", "缺失", "插入", "移码", "无义突变",
        "错义突变", "剪接位点", "致病性", "致病变异", "良性变异",
        "意义不明", "功能丧失", "功能获得", "截短",
        "等位基因", "基因型", "杂合", "纯合", "半合子",
        "新发突变", "胚系突变", "体细胞突变",
        "拷贝数", "杂合性缺失", "外显子", "内含子", "启动子",
        "核苷酸", "氨基酸", "全外显子", "全基因组", "基因panel",
    ],
    "ja": [
        "変異", "突然変異", "多型", "欠失", "挿入", "フレームシフト",
        "ナンセンス", "ミスセンス", "スプライス", "病原性",
        "対立遺伝子", "遺伝子型", "ヘテロ接合", "ホモ接合",
        "デノボ", "生殖細胞系", "体細胞",
        "コピー数", "エクソン", "イントロン",
    ],
    "ko": [
        "변이", "돌연변이", "다형성", "결실", "삽입", "프레임시프트",
        "병원성", "대립유전자", "유전자형", "이형접합", "동형접합",
        "신생돌연변이", "생식세포", "체세포",
        "복제수", "엑손", "인트론",
    ],
    "es": [
        "variante", "mutación", "polimorfismo", "deleción", "inserción",
        "cambio de marco", "patogénico", "alelo", "genotipo",
        "heterocigoto", "homocigoto", "de novo",
        "germinal", "somática", "número de copias", "exón", "intrón",
    ],
    "pt": [
        "variante", "mutação", "polimorfismo", "deleção", "inserção",
        "mudança de quadro", "patogênico", "alelo", "genótipo",
        "heterozigoto", "homozigoto", "de novo",
        "germinativa", "somática", "número de cópias", "éxon", "ítron",
    ],
    "ru": [
        "мутация", "вариант", "полиморфизм", "делеция", "инсерция",
        "сдвиг рамки", "патогенный", "аллель", "генотип",
        "гетерозиготный", "гомозиготный", "de novo",
        "герминальный", "соматический", "число копий", "экзон", "интрон",
    ],
}

CANCER_GENES = [
    "BRCA1", "BRCA2", "TP53", "MECP2", "EGFR", "KRAS", "NRAS", "HRAS",
    "PIK3CA", "PIK3CB", "APC", "PTEN", "RB1", "CDH1", "MLH1", "MSH2",
    "MSH6", "PMS2", "RET", "VHL", "CDKL5", "FOXG1", "ATM", "CHEK2",
    "PALB2", "RAD51C", "RAD51D", "BARD1", "STK11", "SMAD4", "BMPR1A",
    "MUTYH", "EPCAM", "NF1", "NF2", "TSC1", "TSC2", "MEN1", "CDKN2A",
    "BRAF", "ALK", "ROS1", "ERBB2", "HER2", "FGFR1", "FGFR2", "FGFR3",
    "IDH1", "IDH2", "JAK2", "FLT3", "NPM1", "DNMT3A", "TET2",
    "ARID1A", "SMARCA4", "NOTCH1", "FBXW7", "CTNNB1",
]

# ═══════════════════════════════════════════════════════════════════
# HGVS & variant notation regex patterns
# ═══════════════════════════════════════════════════════════════════

HGVS_PATTERNS = [
    re.compile(r"\bc\.\d+[ACGT]"),
    re.compile(r"\bc\.\d+_\d+"),
    re.compile(r"\bc\.\d+[+-]\d+"),
    re.compile(r"\bc\.\d+del"),
    re.compile(r"\bc\.\d+ins"),
    re.compile(r"\bc\.\d+dup"),
    re.compile(r"\bp\.[A-Z][a-z]{2}\d+"),
    re.compile(r"\bp\.[A-Z]\d+[A-Z*]"),
    re.compile(r"\bp\.\(?\w+\)?"),
    re.compile(r"\brs\d{4,}"),
    re.compile(r"\bNM_\d{5,}"),
    re.compile(r"\bNP_\d{5,}"),
    re.compile(r"\bENST\d{8,}"),
    re.compile(r"\bENSP\d{8,}"),
    re.compile(r"chr[\dXY]{1,2}[pq]\d+"),
    re.compile(r"\b\d+[pq]\d+(?:\.\d+)?"),
]

GENE_PATTERN = re.compile(r"\b(" + "|".join(CANCER_GENES) + r")\b", re.IGNORECASE)

# ═══════════════════════════════════════════════════════════════════
# Result types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class FilterResult:
    file_path: str
    lang: str
    tier: int
    action: str
    score: int = 0
    matched_patterns: List[str] = field(default_factory=list)
    llm_result: Optional[Dict[str, Any]] = None
    reason: str = ""
    text_length: int = 0


@dataclass
class FilterReport:
    timestamp: str = ""
    total_scanned: int = 0
    total_kept: int = 0
    total_rejected: int = 0
    total_errors: int = 0
    tier1_kept: int = 0
    tier1_rejected: int = 0
    tier2_kept: int = 0
    tier2_rejected: int = 0
    tier2_errors: int = 0
    by_lang: Dict[str, Dict[str, int]] = field(default_factory=dict)
    results: List[FilterResult] = field(default_factory=list)

# ═══════════════════════════════════════════════════════════════════
# Core functions
# ═══════════════════════════════════════════════════════════════════

def extract_text(pdf_path: Path, max_pages: int = 5, max_chars: int = 8000) -> str:
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return ""
    chunks: List[str] = []
    try:
        for i in range(min(max_pages, len(doc))):
            txt = cast(str, doc[i].get_text("text") or "")
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                chunks.append(txt)
            if sum(len(c) for c in chunks) >= max_chars:
                break
    finally:
        doc.close()
    return "\n".join(chunks)[:max_chars]


def keyword_score(text: str, lang: str) -> Tuple[int, List[str]]:
    if not text:
        return 0, []

    score = 0
    matched: List[str] = []

    for pat in HGVS_PATTERNS:
        m = pat.search(text)
        if m:
            score += 3
            matched.append(m.group(0))

    gene_matches = GENE_PATTERN.findall(text)
    if gene_matches:
        unique_genes = set(g.upper() for g in gene_matches)
        score += 2 * len(unique_genes)
        matched.extend(sorted(unique_genes)[:10])

    keywords = VARIANT_KEYWORDS.get(lang, VARIANT_KEYWORDS["en"])
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            score += 1
            matched.append(kw)

    return score, matched


def _load_llm_config() -> Tuple[str, str, str]:
    sys.path.insert(0, str(BACKEND_DIR))
    from src.core.config import get_config
    cfg = get_config()
    model = (cfg.llm.model or "").strip()
    base_url = (cfg.llm.base_url or "").strip().rstrip("/")
    for suffix in ("/v1", "/v1/"):
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)]
    api_key = (cfg.llm.api_key or "").strip()
    return model, base_url, api_key


def llm_classify_sync(
    text: str,
    title: str,
    lang: str,
    model: str,
    base_url: str,
    api_key: str,
    timeout: int = 60,
) -> Tuple[bool, Dict[str, Any]]:
    system_prompt = (
        "You are a medical literature classifier specializing in genetic variants.\n"
        "Determine whether the paper reports or discusses SPECIFIC genetic variants "
        "(mutations, polymorphisms, copy number changes, HGVS notations, rsIDs) "
        "in the context of human disease or functional studies.\n\n"
        "A paper HAS variant evidence if it:\n"
        "- Reports specific nucleotide or amino acid changes (e.g., c.524G>A, p.R175H)\n"
        "- Discusses known pathogenic/benign variants in specific genes\n"
        "- Presents sequencing results identifying variants in patients or samples\n"
        "- Studies functional effects of specific mutations\n\n"
        "A paper does NOT have variant evidence if it:\n"
        "- Only mentions genetics/mutations in general terms without specifics\n"
        "- Is a review without original variant data\n"
        "- Is about treatment outcomes without genetic analysis\n"
        "- Is a methodology paper without variant results\n\n"
        "Reply with ONLY JSON: "
        '{"has_variant_evidence": true/false, "variant_examples": "brief examples or empty", "reason": "brief explanation"}'
    )

    user_prompt = (
        f"Language: {lang}\n"
        f"Title: {title or 'N/A'}\n\n"
        f"Text excerpt:\n{text[:4000]}"
    )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 512,
    }

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    except Exception as exc:
        return False, {"error": str(exc)[:200]}

    text_clean = content
    if text_clean.startswith("```"):
        lines = text_clean.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text_clean = "\n".join(lines).strip()

    match = re.search(r"\{[\s\S]*\}", text_clean)
    if match:
        text_clean = match.group(0)

    try:
        obj = json.loads(text_clean)
    except json.JSONDecodeError:
        return False, {"error": "invalid_json", "raw": content[:200]}

    has_evidence = bool(obj.get("has_variant_evidence", False))
    return has_evidence, obj


# ═══════════════════════════════════════════════════════════════════
# Async LLM wrapper
# ═══════════════════════════════════════════════════════════════════

async def llm_classify_async(
    sem: asyncio.Semaphore,
    text: str,
    title: str,
    lang: str,
    model: str,
    base_url: str,
    api_key: str,
    timeout: int = 60,
) -> Tuple[bool, Dict[str, Any]]:
    async with sem:
        return await asyncio.to_thread(
            llm_classify_sync, text, title, lang, model, base_url, api_key, timeout
        )


# ═══════════════════════════════════════════════════════════════════
# Directory scanning
# ═══════════════════════════════════════════════════════════════════

LANG_CODES = {"zh", "ja", "ko", "es", "pt", "ru", "en"}


def discover_input_dirs(input_dirs: List[Path]) -> List[Tuple[Path, str]]:
    pairs: List[Tuple[Path, str]] = []
    for root in input_dirs:
        if not root.is_dir():
            continue
        for lang in sorted(LANG_CODES):
            lang_dir = root / lang
            if lang_dir.is_dir() and any(lang_dir.glob("*.pdf")):
                pairs.append((lang_dir, lang))
    return pairs


def infer_title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    parts = re.split(r"[_]+", stem)
    if len(parts) >= 3:
        return " ".join(parts[:-1])
    return stem


# ═══════════════════════════════════════════════════════════════════
# Main processing
# ═══════════════════════════════════════════════════════════════════


def process_all(
    input_pairs: List[Tuple[Path, str]],
    output_dir: Path,
    *,
    keyword_only: bool = False,
    concurrency: int = 5,
    dry_run: bool = False,
    max_pages: int = 5,
    max_chars: int = 8000,
) -> FilterReport:
    report = FilterReport(timestamp=datetime.now(timezone.utc).isoformat())

    all_results: List[Tuple[FilterResult, str, Path]] = []

    for lang_dir, lang in input_pairs:
        pdfs = sorted(lang_dir.glob("*.pdf"))
        report.by_lang[lang] = {"scanned": len(pdfs), "kept": 0, "rejected": 0, "errors": 0}
        logger.info(f"[{lang}] scanning {len(pdfs)} PDFs in {lang_dir}")

        for pdf_path in pdfs:
            text = extract_text(pdf_path, max_pages=max_pages, max_chars=max_chars)
            if not text or len(text.strip()) < 30:
                result = FilterResult(
                    file_path=str(pdf_path),
                    lang=lang,
                    tier=1,
                    action="reject",
                    reason="empty_or_unreadable_pdf",
                )
                all_results.append((result, lang, pdf_path))
                continue

            score, matched = keyword_score(text, lang)
            title = infer_title_from_filename(pdf_path.name)

            if score >= TIER1_KEEP_THRESHOLD:
                result = FilterResult(
                    file_path=str(pdf_path),
                    lang=lang,
                    tier=1,
                    action="keep",
                    score=score,
                    matched_patterns=matched[:20],
                    reason="strong_keyword_match",
                    text_length=len(text),
                )
            elif score <= TIER1_REJECT_THRESHOLD:
                result = FilterResult(
                    file_path=str(pdf_path),
                    lang=lang,
                    tier=1,
                    action="reject",
                    score=score,
                    matched_patterns=matched[:10],
                    reason="no_genetic_signals",
                    text_length=len(text),
                )
            else:
                result = FilterResult(
                    file_path=str(pdf_path),
                    lang=lang,
                    tier=2,
                    action="pending",
                    score=score,
                    matched_patterns=matched[:20],
                    reason="borderline_needs_llm",
                    text_length=len(text),
                )

            all_results.append((result, lang, pdf_path))

    tier1_results = [(r, l, p) for r, l, p in all_results if r.tier == 1]
    tier2_candidates = [(r, l, p) for r, l, p in all_results if r.tier == 2]

    for r, lang, _ in tier1_results:
        if r.action == "keep":
            report.by_lang[lang]["kept"] += 1
            report.tier1_kept += 1
            report.total_kept += 1
        else:
            report.by_lang[lang]["rejected"] += 1
            report.tier1_rejected += 1
            report.total_rejected += 1
        report.results.append(r)

    logger.info(
        f"Tier 1 done: kept={report.tier1_kept}, rejected={report.tier1_rejected}, "
        f"borderline={len(tier2_candidates)}"
    )

    if tier2_candidates and not keyword_only:
        model, base_url, api_key = _load_llm_config()
        if not model or not base_url:
            logger.warning("LLM config missing — treating borderline as keep")
            for r, lang, _ in tier2_candidates:
                r.action = "keep"
                r.reason = "llm_unavailable_kept_by_default"
                report.by_lang[lang]["kept"] = report.by_lang[lang].get("kept", 0) + 1
                report.tier2_kept += 1
                report.total_kept += 1
                report.results.append(r)
        else:
            logger.info(f"Tier 2: classifying {len(tier2_candidates)} borderline papers via LLM")
            sem = asyncio.Semaphore(concurrency)

            async def run_tier2():
                tasks = []
                for r, lang, pdf_path in tier2_candidates:
                    text = extract_text(pdf_path, max_pages=3, max_chars=4000)
                    title = infer_title_from_filename(pdf_path.name)
                    tasks.append((r, lang, pdf_path, text, title))

                coros = []
                for r, lang, pdf_path, text, title in tasks:
                    coro = llm_classify_async(sem, text, title, lang, model, base_url, api_key)
                    coros.append((r, lang, pdf_path, coro))

                done_count = 0
                for r, lang, pdf_path, coro in coros:
                    has_evidence, llm_obj = await coro
                    done_count += 1
                    if done_count % 50 == 0:
                        logger.info(f"  Tier 2 progress: {done_count}/{len(coros)}")

                    r.llm_result = llm_obj
                    if "error" in llm_obj:
                        r.action = "keep"
                        r.reason = f"llm_error_kept: {llm_obj['error'][:80]}"
                        report.tier2_errors += 1
                        report.by_lang[lang]["errors"] = report.by_lang[lang].get("errors", 0) + 1
                        report.total_kept += 1
                        report.tier2_kept += 1
                    elif has_evidence:
                        r.action = "keep"
                        r.reason = f"llm_confirmed: {str(llm_obj.get('reason', ''))[:80]}"
                        report.tier2_kept += 1
                        report.total_kept += 1
                        report.by_lang[lang]["kept"] = report.by_lang[lang].get("kept", 0) + 1
                    else:
                        r.action = "reject"
                        r.reason = f"llm_rejected: {str(llm_obj.get('reason', ''))[:80]}"
                        report.tier2_rejected += 1
                        report.total_rejected += 1
                        report.by_lang[lang]["rejected"] = report.by_lang[lang].get("rejected", 0) + 1

                    report.results.append(r)

            asyncio.run(run_tier2())
            logger.info(
                f"Tier 2 done: kept={report.tier2_kept}, rejected={report.tier2_rejected}, "
                f"errors={report.tier2_errors}"
            )
    elif tier2_candidates and keyword_only:
        logger.info(f"Tier 2 skipped (--keyword-only): treating {len(tier2_candidates)} borderline as keep")
        for r, lang, _ in tier2_candidates:
            r.action = "keep"
            r.reason = "borderline_kept_keyword_only_mode"
            report.by_lang[lang]["kept"] = report.by_lang[lang].get("kept", 0) + 1
            report.tier2_kept += 1
            report.total_kept += 1
            report.results.append(r)

    report.total_scanned = len(all_results)
    report.total_errors = sum(v.get("errors", 0) for v in report.by_lang.values())

    if not dry_run:
        filtered_dir = output_dir / "filtered"
        rejected_dir = output_dir / "rejected"
        moved_kept = 0
        moved_rejected = 0

        for r in report.results:
            src = Path(r.file_path)
            if not src.exists():
                continue

            if r.action == "keep":
                dest_dir = filtered_dir / r.lang
            else:
                dest_dir = rejected_dir / r.lang

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            if dest.exists():
                dest = dest_dir / f"{src.stem}_{hash(str(src)) % 10000:04d}{src.suffix}"

            shutil.move(str(src), str(dest))
            r.file_path = str(dest)
            if r.action == "keep":
                moved_kept += 1
            else:
                moved_rejected += 1

        logger.info(f"File moves: kept→filtered={moved_kept}, rejected→rejected={moved_rejected}")

    return report


# ═══════════════════════════════════════════════════════════════════
# Report output
# ═══════════════════════════════════════════════════════════════════

def print_summary(report: FilterReport) -> None:
    print("\n" + "=" * 60)
    print("  GENETIC VARIANT EVIDENCE FILTER — SUMMARY")
    print("=" * 60)
    print(f"  Total scanned:    {report.total_scanned}")
    print(f"  Total kept:       {report.total_kept}")
    print(f"  Total rejected:   {report.total_rejected}")
    print(f"  Total errors:     {report.total_errors}")
    print(f"  ── Tier 1 ──")
    print(f"    kept:           {report.tier1_kept}")
    print(f"    rejected:       {report.tier1_rejected}")
    print(f"  ── Tier 2 (LLM) ──")
    print(f"    kept:           {report.tier2_kept}")
    print(f"    rejected:       {report.tier2_rejected}")
    print(f"    errors:         {report.tier2_errors}")
    print()
    print("  Per language:")
    for lang in sorted(report.by_lang.keys()):
        stats = report.by_lang[lang]
        print(f"    {lang}: scanned={stats.get('scanned', 0)}, "
              f"kept={stats.get('kept', 0)}, rejected={stats.get('rejected', 0)}, "
              f"errors={stats.get('errors', 0)}")
    print("=" * 60)


def save_report(report: FilterReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "timestamp": report.timestamp,
        "total_scanned": report.total_scanned,
        "total_kept": report.total_kept,
        "total_rejected": report.total_rejected,
        "total_errors": report.total_errors,
        "tier1_kept": report.tier1_kept,
        "tier1_rejected": report.tier1_rejected,
        "tier2_kept": report.tier2_kept,
        "tier2_rejected": report.tier2_rejected,
        "tier2_errors": report.tier2_errors,
        "by_lang": report.by_lang,
        "results": [asdict(r) for r in report.results],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Report saved: {output_path}")


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Filter PDFs for genetic variant evidence")
    parser.add_argument("--input-dirs", nargs="+", type=Path, default=DEFAULT_INPUT_DIRS,
                        help="Input directories containing {lang}/ PDF subdirs")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="Output base dir for filtered/ and rejected/")
    parser.add_argument("--keyword-only", action="store_true",
                        help="Skip LLM tier; keep borderline papers")
    parser.add_argument("--concurrency", type=int, default=5,
                        help="LLM concurrency (default 5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report only, don't move files")
    parser.add_argument("--lang", type=str, default=None,
                        help="Filter only this language")
    parser.add_argument("--max-pages", type=int, default=5,
                        help="Pages to extract per PDF (default 5)")
    parser.add_argument("--max-chars", type=int, default=8000,
                        help="Max chars to extract per PDF (default 8000)")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} {level: <8} {message}")

    input_pairs = discover_input_dirs(args.input_dirs)
    if args.lang:
        input_pairs = [(d, l) for d, l in input_pairs if l == args.lang]

    if not input_pairs:
        logger.error("No input directories found")
        sys.exit(1)

    total_pdfs = sum(len(list(d.glob("*.pdf"))) for d, _ in input_pairs)
    logger.info(f"Found {len(input_pairs)} language dirs, {total_pdfs} PDFs total")
    for d, l in input_pairs:
        logger.info(f"  {l}: {len(list(d.glob('*.pdf')))} PDFs in {d}")

    if args.dry_run:
        logger.info("DRY RUN — no files will be moved")

    t0 = time.time()
    report = process_all(
        input_pairs,
        args.output_dir,
        keyword_only=args.keyword_only,
        concurrency=args.concurrency,
        dry_run=args.dry_run,
        max_pages=args.max_pages,
        max_chars=args.max_chars,
    )
    elapsed = time.time() - t0

    print_summary(report)
    logger.info(f"Elapsed: {elapsed:.1f}s")

    report_path = args.output_dir / "filter_report.json"
    save_report(report, report_path)


if __name__ == "__main__":
    main()
