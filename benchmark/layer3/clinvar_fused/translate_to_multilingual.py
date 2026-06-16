"""Translate fused benchmark source.md files into zh/ja/ko using LLM.

Uses the same LLM config as the pipeline's translation module.
Splits long articles by sections to stay within context limits.
Saves translated files as source_{lang}.md alongside source.md.

Usage:
    PYTHONPATH=.:backend uv run --project backend python -m benchmark.layer3.clinvar_fused.translate_to_multilingual
    PYTHONPATH=.:backend uv run --project backend python -m benchmark.layer3.clinvar_fused.translate_to_multilingual --limit 5
    PYTHONPATH=.:backend uv run --project backend python -m benchmark.layer3.clinvar_fused.translate_to_multilingual --langs zh ja
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

GROUND_TRUTH_DIR = Path(__file__).resolve().parent / "ground_truth"

TARGET_LANGUAGES = {
    "zh": "简体中文（Simplified Chinese）",
    "ja": "日本語（Japanese）",
    "ko": "한국어（Korean）",
}

_MAX_CHUNK_CHARS = 12000
_TRANSLATE_CONCURRENCY = 3


def _split_into_sections(text: str) -> list[str]:
    """Split markdown by ## headings, merge small sections."""
    lines = text.split("\n")
    sections: list[str] = []
    current: list[str] = []

    for line in lines:
        if line.startswith("## ") and current:
            sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))

    merged: list[str] = []
    buffer = ""
    for section in sections:
        if len(buffer) + len(section) < _MAX_CHUNK_CHARS:
            buffer = (buffer + "\n\n" + section).strip()
        else:
            if buffer:
                merged.append(buffer)
            buffer = section
    if buffer:
        merged.append(buffer)

    return merged


def _build_system_prompt(lang_name: str) -> str:
    return f"""You are a professional medical/scientific translator. Translate the following English text into {lang_name}.

Rules:
1. Translate ALL text accurately, preserving medical terminology
2. Keep gene symbols (e.g. BRCA1, CFTR) in their original form — do NOT translate them
3. Keep variant notation (e.g. c.5266dupC, p.Gln1756ProfsTer74) in its original form
4. Keep database IDs (e.g. MONDO:0009061, HGNC:1884) in their original form
5. Keep citation numbers [1], [2] in their original form
6. Keep table formatting (markdown tables) intact
7. Keep heading markers (# ## ### etc.) intact
8. Translate disease names naturally into the target language, but include the English name in parentheses on first occurrence
9. Translate abbreviations on first use, then keep the English abbreviation
10. Output ONLY the translated text, no explanations or notes"""


async def translate_chunk(
    llm: object,
    chunk: str,
    lang_code: str,
    lang_name: str,
    sem: asyncio.Semaphore,
) -> str:
    async with sem:
        try:
            messages = [
                SystemMessage(content=_build_system_prompt(lang_name)),
                HumanMessage(content=chunk),
            ]
            result = await llm.ainvoke(messages)
            return str(result.content) if hasattr(result, "content") else str(result)
        except Exception as e:
            logger.error("Translation failed for lang={}: {}", lang_code, e)
            return f"[TRANSLATION FAILED: {e}]\n\n{chunk}"


async def translate_article(
    llm: object,
    entry_id: str,
    source_text: str,
    lang_code: str,
    lang_name: str,
    sem: asyncio.Semaphore,
) -> str | None:
    sections = _split_into_sections(source_text)

    if len(sections) <= 1:
        return await translate_chunk(llm, source_text, lang_code, lang_name, sem)

    translated_sections: list[str] = []
    for i, section in enumerate(sections):
        logger.debug("[{}] section {}/{} ({})", entry_id, i + 1, len(sections), lang_code)
        translated = await translate_chunk(llm, section, lang_code, lang_name, sem)
        translated_sections.append(translated)

    return "\n\n".join(translated_sections)


async def translate_all(
    target_langs: list[str] | None = None,
    limit: int | None = None,
    entry_ids: list[str] | None = None,
    llm_base_url: str | None = None,
    llm_api_key: str | None = None,
    llm_model: str | None = None,
) -> None:
    from src.utils.llm_adapter import create_llm_client

    if llm_base_url and llm_api_key and llm_model:
        base_url = llm_base_url
        api_key = llm_api_key
        model = llm_model
        api_keys: list[str] = []
        timeout = 120
    else:
        from src.core.config import get_config
        cfg = get_config()
        llm_cfg = cfg.llm
        base_url = llm_cfg.base_url
        api_key = llm_cfg.api_key
        model = llm_cfg.model
        api_keys = llm_cfg.all_api_keys
        timeout = llm_cfg.timeout

    logger.info("LLM: model={} base_url={}", model, base_url)

    llm = create_llm_client(
        model=model,
        api_key=api_key,
        base_url=base_url,
        api_keys=api_keys,
        temperature=0.1,
        max_tokens=8192,
        timeout=timeout,
    )

    langs = target_langs or list(TARGET_LANGUAGES.keys())
    logger.info("Target languages: {}", langs)

    selection_path = GROUND_TRUTH_DIR / "selection.json"
    entries = json.loads(selection_path.read_text(encoding="utf-8"))
    if entry_ids:
        entries = [e for e in entries if e["entry_id"] in set(entry_ids)]
    if limit:
        entries = entries[:limit]

    entries_with_source = []
    for e in entries:
        source_path = GROUND_TRUTH_DIR / e["entry_id"] / "source.md"
        if source_path.exists() and source_path.stat().st_size > 200:
            entries_with_source.append(e)
        else:
            logger.warning("[{}] no source.md, skipping", e["entry_id"])

    logger.info("Translating {} entries to {} languages", len(entries_with_source), len(langs))

    sem = asyncio.Semaphore(_TRANSLATE_CONCURRENCY)
    total_tasks = len(entries_with_source) * len(langs)
    completed = 0

    for entry in entries_with_source:
        entry_id = entry["entry_id"]
        source_path = GROUND_TRUTH_DIR / entry_id / "source.md"
        source_text = source_path.read_text(encoding="utf-8")

        for lang_code in langs:
            if lang_code not in TARGET_LANGUAGES:
                logger.warning("Unknown language: {}", lang_code)
                continue

            lang_name = TARGET_LANGUAGES[lang_code]
            output_path = GROUND_TRUTH_DIR / entry_id / f"source_{lang_code}.md"

            if output_path.exists() and output_path.stat().st_size > 200:
                logger.info("[{}] {} already exists, skipping", entry_id, lang_code)
                completed += 1
                continue

            logger.info("[{}] translating to {}...", entry_id, lang_code)
            translated = await translate_article(
                llm, entry_id, source_text, lang_code, lang_name, sem
            )

            if translated:
                output_path.write_text(translated, encoding="utf-8")
                logger.info("[{}] {} saved ({:.1f} KB)", entry_id, lang_code, len(translated) / 1024)
            else:
                logger.error("[{}] {} translation returned None", entry_id, lang_code)

            completed += 1
            logger.info("Progress: {}/{}", completed, total_tasks)

    logger.info("Done. {}/{} translations completed", completed, total_tasks)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Translate fused benchmark to multilingual")
    parser.add_argument("--langs", nargs="+", default=None, help="Target languages (zh ja ko)")
    parser.add_argument("--limit", type=int, default=None, help="Max entries to translate")
    parser.add_argument("--entries", nargs="+", default=None, help="Specific entry IDs")
    parser.add_argument("--base-url", default=None, help="LLM API base URL")
    parser.add_argument("--api-key", default=None, help="LLM API key")
    parser.add_argument("--model", default=None, help="LLM model name")
    args = parser.parse_args()

    asyncio.run(translate_all(
        target_langs=args.langs,
        limit=args.limit,
        entry_ids=args.entries,
        llm_base_url=args.base_url,
        llm_api_key=args.api_key,
        llm_model=args.model,
    ))
