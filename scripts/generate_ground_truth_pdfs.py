"""Generate PDFs from ground_truth literature for pipeline benchmark.

Reads source.md from each ground_truth entry, translates to 6 languages,
generates PDFs using weasyprint, and organizes into benchmark input directory.

Usage:
    cd backend
    uv run python ../scripts/generate_ground_truth_pdfs.py
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx
from loguru import logger

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GROUND_TRUTH_DIR = PROJECT_ROOT / "benchmark" / "layer3" / "ground_truth"
OUTPUT_DIR = PROJECT_ROOT / "benchmark" / "pipeline" / "input" / "ground_truth"
SELECTION_JSON = GROUND_TRUTH_DIR / "selection.json"

# Target languages (non-English)
TARGET_LANGS = ["zh", "ja", "ko", "fr", "de", "es"]
LANG_NAMES = {
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
}

# LLM config
LLM_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
LLM_MODEL = "mimo-v2.5"
LLM_CONCURRENCY = 4  # concurrent translation requests

# Weasyprint CSS for CJK support
WEASYPRINT_CSS = """
@page {
    size: A4;
    margin: 2cm;
}
body {
    font-family: "Noto Sans", "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK KR",
                 "Source Han Sans", "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB",
                 "Meiryo", "Malgun Gothic", sans-serif;
    font-size: 11pt;
    line-height: 1.6;
}
h1 { font-size: 18pt; margin-top: 0; }
h2 { font-size: 14pt; margin-top: 1em; }
h3 { font-size: 12pt; margin-top: 1em; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; font-size: 10pt; }
th { background: #f5f5f5; }
code { font-family: monospace; font-size: 10pt; }
"""


def load_selection() -> list[dict]:
    """Load selection.json to get all ground_truth entries."""
    with open(SELECTION_JSON, encoding="utf-8") as f:
        return json.load(f)


def markdown_to_html(md_content: str) -> str:
    """Convert markdown to HTML (basic conversion for weasyprint)."""
    # Use markdown library if available, otherwise basic regex
    try:
        import markdown
        return markdown.markdown(md_content, extensions=["tables", "fenced_code"])
    except ImportError:
        # Basic fallback
        html = md_content
        # Headers
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        # Bold
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        # Italic
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
        # Paragraphs
        html = re.sub(r"\n\n+", "</p><p>", html)
        html = f"<p>{html}</p>"
        return html


def build_html_document(content: str, title: str = "") -> str:
    """Build a complete HTML document from markdown content."""
    html_body = markdown_to_html(content)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{WEASYPRINT_CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""


async def translate_with_llm(
    client: httpx.AsyncClient,
    text: str,
    target_lang: str,
    api_keys: list[str],
    semaphore: asyncio.Semaphore,
) -> str:
    """Translate text to target language using LLM API."""
    lang_name = LANG_NAMES[target_lang]

    prompt = f"""Translate the following academic/medical text to {lang_name}.
Preserve the markdown formatting (headers, tables, lists).
Keep technical terms, gene names, and proper nouns in their original form where appropriate.
Output ONLY the translated text, no explanations.

---
{text}"""

    # Rotate API keys
    key = api_keys[hash(text + target_lang) % len(api_keys)]

    async with semaphore:
        for attempt in range(3):
            try:
                logger.info(f"Sending translation request for {target_lang} (attempt {attempt+1})...")
                resp = await client.post(
                    f"{LLM_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 8192,
                    },
                    timeout=180.0,  # 3 minute timeout per request
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                logger.info(f"Translation completed for {target_lang} ({len(content)} chars)")
                return content
            except httpx.TimeoutException as e:
                logger.warning(f"Translation timeout for {target_lang} (attempt {attempt+1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
            except Exception as e:
                logger.warning(f"Translation attempt {attempt+1} failed for {target_lang}: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise


def generate_pdf(html_content: str, output_path: Path) -> None:
    """Generate PDF from HTML using weasyprint."""
    import weasyprint

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = weasyprint.HTML(string=html_content)
    doc.write_pdf(str(output_path))
    logger.info(f"Generated PDF: {output_path}")


async def process_entry(
    entry_id: str,
    source_md: str,
    api_keys: list[str],
    semaphore: asyncio.Semaphore,
) -> dict[str, Path]:
    """Process a single ground_truth entry: translate and generate PDFs."""
    results = {}

    # Extract title from source.md (first h1 header)
    title_match = re.search(r"^# (.+)$", source_md, re.MULTILINE)
    title = title_match.group(1) if title_match else entry_id

    # Sanitize filename
    safe_id = entry_id.replace("/", "_")

    # 1. English original PDF (skip if exists)
    en_pdf_path = OUTPUT_DIR / "en" / "case_report" / f"{safe_id}.pdf"
    if en_pdf_path.exists():
        logger.info(f"Skipping English PDF (already exists): {en_pdf_path.name}")
        results["en"] = en_pdf_path
    else:
        en_html = build_html_document(source_md, title)
        generate_pdf(en_html, en_pdf_path)
        results["en"] = en_pdf_path

    # 2. Translate to each target language (skip existing)
    langs_to_translate = []
    for lang in TARGET_LANGS:
        lang_pdf_path = OUTPUT_DIR / lang / "case_report" / f"{safe_id}.pdf"
        if lang_pdf_path.exists():
            logger.info(f"Skipping {lang} translation (already exists): {lang_pdf_path.name}")
            results[lang] = lang_pdf_path
        else:
            langs_to_translate.append(lang)

    if not langs_to_translate:
        logger.info(f"All translations already exist for {entry_id}")
        return results

    logger.info(f"Translating {entry_id} to {len(langs_to_translate)} languages: {langs_to_translate}")

    async with httpx.AsyncClient() as client:
        tasks = [
            translate_with_llm(client, source_md, lang, api_keys, semaphore)
            for lang in langs_to_translate
        ]
        translations = await asyncio.gather(*tasks, return_exceptions=True)

    for lang, translation in zip(langs_to_translate, translations):
        if isinstance(translation, Exception):
            logger.error(f"Translation failed for {entry_id}/{lang}: {translation}")
            continue

        lang_html = build_html_document(translation, title)
        lang_pdf_path = OUTPUT_DIR / lang / "case_report" / f"{safe_id}.pdf"
        generate_pdf(lang_html, lang_pdf_path)
        results[lang] = lang_pdf_path

    return results


async def main():
    """Main entry point."""
    from src.core.config import get_config

    # Load config
    cfg = get_config()
    api_keys = cfg.fast_llm_api_keys
    if not api_keys:
        raise RuntimeError("No LLM API keys configured")

    logger.info(f"Using {len(api_keys)} API keys for translation")

    # Load selection
    entries = load_selection()
    logger.info(f"Found {len(entries)} ground_truth entries")

    # Create output directories
    for lang in ["en"] + TARGET_LANGS:
        (OUTPUT_DIR / lang / "case_report").mkdir(parents=True, exist_ok=True)

    # Process entries with concurrency limit
    semaphore = asyncio.Semaphore(LLM_CONCURRENCY)
    all_results = {}

    for entry in entries:
        entry_id = entry["entry_id"]
        source_path = GROUND_TRUTH_DIR / entry_id / "source.md"

        if not source_path.exists():
            logger.warning(f"source.md not found for {entry_id}, skipping")
            continue

        logger.info(f"Processing {entry_id}...")
        source_md = source_path.read_text(encoding="utf-8")

        try:
            results = await process_entry(entry_id, source_md, api_keys, semaphore)
            all_results[entry_id] = results
            logger.info(f"Completed {entry_id}: {len(results)} PDFs generated")
        except Exception as e:
            logger.error(f"Failed to process {entry_id}: {e}")

    # Summary
    total_pdfs = sum(len(r) for r in all_results.values())
    logger.info(f"Done! Generated {total_pdfs} PDFs for {len(all_results)} entries")
    logger.info(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
