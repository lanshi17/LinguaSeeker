"""Final pass: handle papers where LLM returned empty/invalid responses.

Uses a simpler prompt (yes/no) and extracts more text to give the LLM
better context. Papers that still fail are rejected as unreadable.

Usage:
    cd backend
    uv run python ../benchmark/runners/final_classify.py
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

import fitz
import httpx
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
REPORT_PATH = PROJECT_ROOT / "benchmark" / "runners" / "downloads" / "filter_report.json"
DOWNLOADS_DIR = PROJECT_ROOT / "benchmark" / "runners" / "downloads"


def load_llm_config() -> Tuple[str, str, str]:
    sys.path.insert(0, str(BACKEND_DIR))
    from src.core.config import get_config
    cfg = get_config()
    model = (cfg.llm.model or "").strip()
    base_url = (cfg.llm.base_url or "").strip().rstrip("/")
    for suffix in ("/v1", "/v1/"):
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)]
    api_key = (cfg.llm.api_key or "").strip()
    if not api_key and cfg.llm.all_api_keys:
        api_key = cfg.llm.all_api_keys[0]
    return model, base_url, api_key


def extract_text_full(pdf_path: Path, max_chars: int = 6000) -> str:
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return ""
    chunks: List[str] = []
    try:
        for i in range(min(8, len(doc))):
            txt = cast(str, doc[i].get_text("text") or "")
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                chunks.append(txt)
            if sum(len(c) for c in chunks) >= max_chars:
                break
    finally:
        doc.close()
    return "\n".join(chunks)[:max_chars]


SIMPLE_SYSTEM = (
    "You classify whether a scientific paper contains genetic variant evidence. "
    "Answer ONLY with one word: YES or NO.\n"
    "YES = the paper reports specific genetic variants (mutations, SNPs, HGVS notations like c.123A>G or p.R175H).\n"
    "NO = the paper does not report specific variants."
)


def classify_simple(
    text: str, title: str, lang: str,
    model: str, base_url: str, api_key: str,
) -> Tuple[bool, Dict[str, Any]]:
    user_msg = f"Title: {title}\nLanguage: {lang}\n\nText:\n{text[:5000]}"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SIMPLE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 20,
    }

    for attempt in range(3):
        try:
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                resp = client.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload)
                if resp.status_code == 429:
                    time.sleep(5 * (2 ** attempt))
                    continue
                resp.raise_for_status()
                data = resp.json()
            content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
            break
        except Exception as exc:
            if attempt == 2:
                return False, {"error": str(exc)[:200]}
            time.sleep(5 * (2 ** attempt))
    else:
        return False, {"error": "rate_limited"}

    if not content:
        return False, {"error": "empty_response", "action": "reject_unreadable"}

    answer = content.lower().strip().rstrip(".")
    has_evidence = "yes" in answer and "no" not in answer
    return has_evidence, {"simple_answer": content, "has_variant_evidence": has_evidence}


async def classify_async(
    sem: asyncio.Semaphore,
    text: str, title: str, lang: str,
    model: str, base_url: str, api_key: str,
) -> Tuple[bool, Dict[str, Any]]:
    async with sem:
        result = await asyncio.to_thread(classify_simple, text, title, lang, model, base_url, api_key)
        await asyncio.sleep(1)
        return result


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} {level: <8} {message}")

    report_data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    results = report_data["results"]

    pending = [
        r for r in results
        if r.get("tier") == 2 and r.get("llm_result") and "error" in r["llm_result"]
    ]
    logger.info(f"Found {len(pending)} papers to re-classify with simple prompt")

    model, base_url, api_key = load_llm_config()
    logger.info(f"LLM: model={model}, base_url={base_url}")

    if not model or not base_url:
        logger.error("LLM config missing")
        sys.exit(1)

    sem = asyncio.Semaphore(3)

    async def run_all():
        tasks = []
        for r in pending:
            pdf_path = Path(r["file_path"])
            if not pdf_path.exists():
                logger.warning(f"File not found: {pdf_path}")
                continue
            text = extract_text_full(pdf_path)
            title = Path(r["file_path"]).stem.replace("_", " ")[:80]
            tasks.append((r, pdf_path, text, title))

        kept = 0
        rejected = 0
        errors = 0
        rejected_unreadable = 0
        done = 0

        coros = []
        for r, pdf_path, text, title in tasks:
            if not text or len(text.strip()) < 30:
                r["llm_result"] = {"error": "unreadable_pdf", "action": "reject_unreadable"}
                r["action"] = "reject"
                r["reason"] = "unreadable_pdf_no_extractable_text"
                rejected += 1
                rejected_unreadable += 1
                done += 1

                src = pdf_path
                if src.exists():
                    rej_dir = DOWNLOADS_DIR / "rejected" / r["lang"]
                    rej_dir.mkdir(parents=True, exist_ok=True)
                    dest = rej_dir / src.name
                    shutil.move(str(src), str(dest))
                    r["file_path"] = str(dest)
                continue
            coro = classify_async(sem, text, title, r["lang"], model, base_url, api_key)
            coros.append((r, pdf_path, coro))

        for r, pdf_path, coro in coros:
            has_evidence, llm_obj = await coro
            done += 1
            if done % 20 == 0:
                logger.info(f"  Progress: {done}/{len(tasks)} (kept={kept}, rejected={rejected}, errors={errors})")

            r["llm_result"] = llm_obj

            if "error" in llm_obj and llm_obj.get("action") == "reject_unreadable":
                r["action"] = "reject"
                r["reason"] = "llm_empty_response_unreadable"
                rejected += 1
                rejected_unreadable += 1
            elif "error" in llm_obj:
                r["action"] = "reject"
                r["reason"] = f"llm_error_rejected: {llm_obj['error'][:60]}"
                rejected += 1
                errors += 1
            elif has_evidence:
                r["action"] = "keep"
                r["reason"] = f"llm_simple_confirmed: {llm_obj.get('simple_answer', '')}"
                kept += 1
            else:
                r["action"] = "reject"
                r["reason"] = f"llm_simple_rejected: {llm_obj.get('simple_answer', '')}"
                rejected += 1

            if r["action"] == "reject":
                src = pdf_path
                if src.exists():
                    rej_dir = DOWNLOADS_DIR / "rejected" / r["lang"]
                    rej_dir.mkdir(parents=True, exist_ok=True)
                    dest = rej_dir / src.name
                    if dest.exists():
                        dest = rej_dir / f"{src.stem}_{hash(str(src)) % 10000:04d}{src.suffix}"
                    shutil.move(str(src), str(dest))
                    r["file_path"] = str(dest)

        logger.info(
            f"Done: kept={kept}, rejected={rejected} "
            f"(unreadable={rejected_unreadable}, llm_errors={errors})"
        )

        # Recalculate totals
        by_lang: Dict[str, Dict[str, int]] = {}
        total_kept = 0
        total_rejected = 0
        tier2_kept = 0
        tier2_rejected = 0
        tier2_errors = 0

        for r in results:
            lang = r["lang"]
            if lang not in by_lang:
                by_lang[lang] = {"scanned": 0, "kept": 0, "rejected": 0, "errors": 0}
            by_lang[lang]["scanned"] += 1
            if r["action"] == "keep":
                by_lang[lang]["kept"] += 1
                total_kept += 1
            else:
                by_lang[lang]["rejected"] += 1
                total_rejected += 1
            if r.get("tier") == 2:
                if r["action"] == "keep":
                    tier2_kept += 1
                else:
                    tier2_rejected += 1
                if "error" in (r.get("llm_result") or {}) and "unreadable" not in str(r.get("reason", "")):
                    tier2_errors += 1
                    by_lang[lang]["errors"] += 1

        report_data["total_kept"] = total_kept
        report_data["total_rejected"] = total_rejected
        report_data["total_errors"] = tier2_errors
        report_data["tier2_kept"] = tier2_kept
        report_data["tier2_rejected"] = tier2_rejected
        report_data["tier2_errors"] = tier2_errors
        report_data["by_lang"] = by_lang

        REPORT_PATH.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Report updated: {REPORT_PATH}")

    asyncio.run(run_all())


if __name__ == "__main__":
    main()
