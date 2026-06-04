#!/usr/bin/env python3
"""Check PDF relevance to Rett Syndrome using LLM, and remove irrelevant ones."""

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from openai import AsyncOpenAI

# Add backend to path for config import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
from src.core.config import get_config

# ── Config ──────────────────────────────────────────────────────────────────
RETT_DIR = Path(__file__).resolve().parent.parent / "literature_acquisition" / "downloads" / "rett"
MAX_PAGES = 3          # first N pages to extract
MAX_CHARS = 3000       # truncate extracted text
CONCURRENCY = 8        # parallel LLM calls
DRY_RUN = False        # set True to preview without deleting
# ────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a medical literature classifier. Your task is to determine whether a given PDF document is related to Rett Syndrome (RTT).

Rett Syndrome is a rare genetic neurological disorder that primarily affects girls, caused by mutations in the MECP2 gene. Related topics include:
- Rett Syndrome diagnosis, treatment, clinical features
- MECP2 gene mutations and their effects
- Atypical Rett Syndrome variants
- Rett Syndrome animal models
- Clinical case reports of Rett Syndrome patients
- Reviews or meta-analyses mentioning Rett Syndrome
- Related disorders: CDKL5 deficiency, FOXG1 syndrome, MECP2 duplication syndrome

NOT related (answer NO):
- Papers about other genetic disorders without Rett Syndrome context
- General neuroscience papers not mentioning Rett
- Papers about autism without Rett Syndrome connection
- Papers about epilepsy/seizures without Rett context
- Papers clearly about a different disease (e.g., Down syndrome, Fragile X, Angelman syndrome alone)

Reply with ONLY a JSON object (no markdown fences):
{"relevant": true/false, "reason": "brief explanation in English", "title": "paper title if identifiable, or empty string"}"""

USER_TEMPLATE = """Is this document related to Rett Syndrome?

Language: {lang}
Filename: {filename}
Extracted text (first {max_pages} pages):
---
{text}
---"""


@dataclass
class CheckResult:
    lang: str
    filename: str
    filepath: str
    relevant: bool = False
    reason: str = ""
    title: str = ""
    error: str = ""


@dataclass
class Stats:
    total: int = 0
    relevant: int = 0
    irrelevant: int = 0
    errors: int = 0
    deleted: int = 0
    by_lang: dict = field(default_factory=dict)

    def record(self, result: CheckResult):
        self.total += 1
        lang = result.lang
        if lang not in self.by_lang:
            self.by_lang[lang] = {"relevant": 0, "irrelevant": 0, "errors": 0}
        if result.error:
            self.errors += 1
            self.by_lang[lang]["errors"] += 1
        elif result.relevant:
            self.relevant += 1
            self.by_lang[lang]["relevant"] += 1
        else:
            self.irrelevant += 1
            self.by_lang[lang]["irrelevant"] += 1


def extract_text(pdf_path: Path, max_pages: int = MAX_PAGES) -> str:
    """Extract text from first N pages of a PDF."""
    try:
        doc = pymupdf.open(str(pdf_path))
        texts = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            texts.append(page.get_text())
        doc.close()
        return "\n".join(texts)[:MAX_CHARS]
    except Exception as e:
        return f"[ERROR reading PDF: {e}]"


def parse_llm_response(raw: str) -> dict:
    """Parse LLM JSON response, handling markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return json.loads(text)


async def check_one(
    client: AsyncOpenAI,
    sem: asyncio.Semaphore,
    pdf_path: Path,
    lang: str,
    stats: Stats,
    model: str,
) -> CheckResult:
    """Check a single PDF for Rett Syndrome relevance."""
    result = CheckResult(
        lang=lang,
        filename=pdf_path.name,
        filepath=str(pdf_path),
    )
    async with sem:
        try:
            text = await asyncio.to_thread(extract_text, pdf_path)
            if text.startswith("[ERROR"):
                result.error = text
                stats.record(result)
                return result

            user_msg = USER_TEMPLATE.format(
                lang=lang,
                filename=pdf_path.name,
                max_pages=MAX_PAGES,
                text=text,
            )
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=4096,
            )
            parsed = parse_llm_response(resp.choices[0].message.content)
            result.relevant = bool(parsed.get("relevant", False))
            result.reason = parsed.get("reason", "")
            result.title = parsed.get("title", "")
        except json.JSONDecodeError as e:
            result.error = f"JSON parse error: {e}"
        except Exception as e:
            result.error = str(e)

        stats.record(result)
        return result


async def main():
    if not RETT_DIR.exists():
        print(f"ERROR: Directory not found: {RETT_DIR}")
        sys.exit(1)

    # Collect all PDFs
    all_pdfs: list[tuple[str, Path]] = []
    for lang_dir in sorted(RETT_DIR.iterdir()):
        if not lang_dir.is_dir():
            continue
        lang = lang_dir.name
        for pdf in sorted(lang_dir.glob("*.pdf")):
            all_pdfs.append((lang, pdf))

    print(f"Found {len(all_pdfs)} PDFs across {len(set(l for l, _ in all_pdfs))} languages")
    if DRY_RUN:
        print("DRY RUN mode — no files will be deleted")
    print()

    cfg = get_config()
    client = AsyncOpenAI(base_url=cfg.llm.base_url, api_key=cfg.llm.api_key)
    print(f"LLM: {cfg.llm.base_url} / {cfg.llm.model}")
    sem = asyncio.Semaphore(CONCURRENCY)
    stats = Stats()

    # Process all PDFs
    tasks = []
    for lang, pdf_path in all_pdfs:
        tasks.append(check_one(client, sem, pdf_path, lang, stats, cfg.llm.model))

    results: list[CheckResult] = []
    for i, coro in enumerate(asyncio.as_completed(tasks), 1):
        result = await coro
        results.append(result)
        status = "✓ REL" if result.relevant else ("✗ DEL" if not result.error else "? ERR")
        print(f"[{i:>3}/{len(all_pdfs)}] {result.lang}/{result.filename[:50]:<50s} {status}  {result.reason[:60]}")

    # Delete irrelevant PDFs
    to_delete = [r for r in results if not r.relevant and not r.error]
    if to_delete and not DRY_RUN:
        print(f"\nDeleting {len(to_delete)} irrelevant PDFs...")
        for r in to_delete:
            try:
                Path(r.filepath).unlink()
                stats.deleted += 1
            except Exception as e:
                print(f"  Failed to delete {r.filepath}: {e}")
    elif to_delete:
        print(f"\nWould delete {len(to_delete)} irrelevant PDFs (dry run)")

    # Save detailed report
    report_path = RETT_DIR / f"relevance_check_{int(time.time())}.json"
    report = {
        "stats": {
            "total": stats.total,
            "relevant": stats.relevant,
            "irrelevant": stats.irrelevant,
            "errors": stats.errors,
            "deleted": stats.deleted,
            "by_lang": stats.by_lang,
        },
        "removed": [
            {"lang": r.lang, "filename": r.filename, "reason": r.reason, "title": r.title}
            for r in to_delete
        ],
        "errors": [
            {"lang": r.lang, "filename": r.filename, "error": r.error}
            for r in results
            if r.error
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nDetailed report saved to: {report_path}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Language':<10} {'Total':>6} {'Relevant':>10} {'Irrelevant':>12} {'Errors':>8}")
    print("-" * 60)
    for lang in sorted(stats.by_lang):
        d = stats.by_lang[lang]
        print(f"{lang:<10} {d['relevant']+d['irrelevant']+d['errors']:>6} {d['relevant']:>10} {d['irrelevant']:>12} {d['errors']:>8}")
    print("-" * 60)
    print(f"{'TOTAL':<10} {stats.total:>6} {stats.relevant:>10} {stats.irrelevant:>12} {stats.errors:>8}")
    print(f"\nDeleted: {stats.deleted} files")


if __name__ == "__main__":
    asyncio.run(main())
