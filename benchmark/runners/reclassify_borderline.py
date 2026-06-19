"""Re-classify borderline papers that failed LLM in the first run.

Reads filter_report.json, finds tier-2 papers that got LLM errors,
re-runs LLM classification with fixed URL, moves rejected papers
from filtered/ to rejected/, and updates the report.

Usage:
    cd backend
    uv run python ../benchmark/runners/reclassify_borderline.py
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
    return model, base_url, api_key


def extract_text(pdf_path: Path, max_pages: int = 3, max_chars: int = 4000) -> str:
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


def classify_one(
    text: str, title: str, lang: str,
    model: str, base_url: str, api_key: str,
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

    for attempt in range(3):
        try:
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                resp = client.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload)
                if resp.status_code == 429:
                    wait = 5 * (2 ** attempt)
                    import time as _time
                    _time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
            content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
            break
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < 2:
                import time as _time
                _time.sleep(5 * (2 ** attempt))
                continue
            return False, {"error": str(exc)[:200]}
        except Exception as exc:
            return False, {"error": str(exc)[:200]}
    else:
        return False, {"error": "rate_limited_after_3_retries"}

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

    return bool(obj.get("has_variant_evidence", False)), obj


async def classify_async(
    sem: asyncio.Semaphore,
    text: str, title: str, lang: str,
    model: str, base_url: str, api_key: str,
) -> Tuple[bool, Dict[str, Any]]:
    async with sem:
        result = await asyncio.to_thread(classify_one, text, title, lang, model, base_url, api_key)
        await asyncio.sleep(1)
        return result


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} {level: <8} {message}")

    report_data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    results = report_data["results"]

    borderline = [
        r for r in results
        if r.get("tier") == 2 and r.get("llm_result") and "error" in r["llm_result"]
    ]
    logger.info(f"Found {len(borderline)} borderline papers to re-classify")

    model, base_url, api_key = load_llm_config()
    logger.info(f"LLM: model={model}, base_url={base_url}")

    if not model or not base_url:
        logger.error("LLM config missing")
        sys.exit(1)

    sem = asyncio.Semaphore(3)

    async def run_all():
        tasks = []
        for r in borderline:
            pdf_path = Path(r["file_path"])
            if not pdf_path.exists():
                logger.warning(f"File not found: {pdf_path}")
                continue
            text = extract_text(pdf_path)
            title = Path(r["file_path"]).stem.replace("_", " ")[:80]
            tasks.append((r, pdf_path, text, title))

        llm_kept = 0
        llm_rejected = 0
        llm_errors = 0
        done = 0

        coros = []
        for r, pdf_path, text, title in tasks:
            coro = classify_async(sem, text, title, r["lang"], model, base_url, api_key)
            coros.append((r, pdf_path, coro))

        for r, pdf_path, coro in coros:
            has_evidence, llm_obj = await coro
            done += 1
            if done % 50 == 0:
                logger.info(f"  Progress: {done}/{len(coros)} (kept={llm_kept}, rejected={llm_rejected}, errors={llm_errors})")

            r["llm_result"] = llm_obj
            if "error" in llm_obj:
                r["action"] = "keep"
                r["reason"] = f"llm_error_kept: {llm_obj['error'][:80]}"
                llm_errors += 1
            elif has_evidence:
                r["action"] = "keep"
                r["reason"] = f"llm_confirmed: {str(llm_obj.get('reason', ''))[:80]}"
                llm_kept += 1
            else:
                r["action"] = "reject"
                r["reason"] = f"llm_rejected: {str(llm_obj.get('reason', ''))[:80]}"
                llm_rejected += 1

                src = pdf_path
                if src.exists():
                    rejected_dir = DOWNLOADS_DIR / "rejected" / r["lang"]
                    rejected_dir.mkdir(parents=True, exist_ok=True)
                    dest = rejected_dir / src.name
                    if dest.exists():
                        dest = rejected_dir / f"{src.stem}_{hash(str(src)) % 10000:04d}{src.suffix}"
                    shutil.move(str(src), str(dest))
                    r["file_path"] = str(dest)

        logger.info(f"Done: kept={llm_kept}, rejected={llm_rejected}, errors={llm_errors}")

        report_data["tier2_kept"] = llm_kept
        report_data["tier2_rejected"] = llm_rejected
        report_data["tier2_errors"] = llm_errors
        report_data["total_kept"] = report_data["tier1_kept"] + llm_kept
        report_data["total_rejected"] = report_data["tier1_rejected"] + llm_rejected
        report_data["total_errors"] = llm_errors

        by_lang: Dict[str, Dict[str, int]] = {}
        for r in results:
            lang = r["lang"]
            if lang not in by_lang:
                by_lang[lang] = {"scanned": 0, "kept": 0, "rejected": 0, "errors": 0}
            by_lang[lang]["scanned"] += 1
            if r["action"] == "keep":
                by_lang[lang]["kept"] += 1
            elif r["action"] == "reject":
                by_lang[lang]["rejected"] += 1
            if "error" in (r.get("llm_result") or {}):
                by_lang[lang]["errors"] += 1
        report_data["by_lang"] = by_lang

        REPORT_PATH.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Report updated: {REPORT_PATH}")

    asyncio.run(run_all())


if __name__ == "__main__":
    main()
