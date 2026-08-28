"""Translate fused benchmark source.md files into zh/ja/ko using LLM.

Uses the same LLM config as the pipeline's translation module.
Splits long articles by sections to stay within context limits.
Saves translated files as source_{lang}.md alongside source.md.

Usage:
    PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.translate_to_multilingual
    PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.translate_to_multilingual --limit 5
    PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.translate_to_multilingual --langs zh ja
"""
from __future__ import annotations

import asyncio
import json
import os
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
    llms: list,
    chunk: str,
    lang_code: str,
    lang_name: str,
    sem: asyncio.Semaphore,
) -> str:
    messages = [
        SystemMessage(content=_build_system_prompt(lang_name)),
        HumanMessage(content=chunk),
    ]
    async with sem:
        for llm in llms:
            try:
                result = await llm.ainvoke(messages)
                return str(result.content) if hasattr(result, "content") else str(result)
            except Exception as e:
                logger.warning("Provider failed ({}), trying next: {}", type(e).__name__, str(e)[:80])
                continue
        logger.error("All providers failed for lang={}", lang_code)
        return f"[TRANSLATION FAILED: all providers]\n\n{chunk}"


async def translate_article(
    llms: list,
    entry_id: str,
    source_text: str,
    lang_code: str,
    lang_name: str,
    sem: asyncio.Semaphore,
) -> str | None:
    sections = _split_into_sections(source_text)

    if len(sections) <= 1:
        return await translate_chunk(llms, source_text, lang_code, lang_name, sem)

    translated_sections: list[str] = []
    for i, section in enumerate(sections):
        logger.debug("[{}] section {}/{} ({})", entry_id, i + 1, len(sections), lang_code)
        translated = await translate_chunk(llms, section, lang_code, lang_name, sem)
        translated_sections.append(translated)

    return "\n\n".join(translated_sections)


async def translate_all(
    target_langs: list[str] | None = None,
    limit: int | None = None,
    entry_ids: list[str] | None = None,
    providers: list[dict[str, str]] | None = None,
) -> None:
    from src.utils.llm_adapter import create_llm_client

    if not providers:
        from src.core.config import get_config
        cfg = get_config()
        llm_cfg = cfg.llm
        providers = [{
            "base_url": llm_cfg.base_url,
            "api_key": llm_cfg.api_key,
            "model": llm_cfg.model,
        }]

    llms: list = []
    for p in providers:
        logger.info("Provider: {} model={}", p["base_url"], p["model"])
        llms.append(create_llm_client(
            model=p["model"],
            api_key=p["api_key"],
            base_url=p["base_url"],
            temperature=0.1,
            max_tokens=8192,
            timeout=120,
        ))

    logger.info("LLM providers: {}", len(llms))

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
                llms, entry_id, source_text, lang_code, lang_name, sem
            )

            if translated:
                output_path.write_text(translated, encoding="utf-8")
                logger.info("[{}] {} saved ({:.1f} KB)", entry_id, lang_code, len(translated) / 1024)
            else:
                logger.error("[{}] {} translation returned None", entry_id, lang_code)

            completed += 1
            logger.info("Progress: {}/{}", completed, total_tasks)

    logger.info("Done. {}/{} translations completed", completed, total_tasks)


def _build_providers() -> list[dict[str, str]]:
    """Build multi-provider config from environment variables.

    Provider config is loaded from BENCHMARK_TRANSLATE_PROVIDERS env var as a
    JSON array of {base_url, api_key, model} objects.  If unset, falls back to
    a single provider using the standard FAST_LLM_* env vars.

    NEVER hardcode API keys in source code — use environment variables or
    vault-backed configuration instead.
    """
    raw = os.environ.get("BENCHMARK_TRANSLATE_PROVIDERS", "")
    if raw:
        import json as _json
        return _json.loads(raw)

    # Fallback: use the main FAST_LLM_* config if available
    base_url = os.environ.get("FAST_LLM_BASE_URL", "")
    api_key = os.environ.get("FAST_LLM_API_KEY", "")
    model = os.environ.get("FAST_LLM_MODEL", "")
    if base_url and api_key and model:
        return [{"base_url": base_url, "api_key": api_key, "model": model}]

    raise RuntimeError(
        "No translation providers configured. "
        "Set BENCHMARK_TRANSLATE_PROVIDERS (JSON array) or "
        "FAST_LLM_BASE_URL / FAST_LLM_API_KEY / FAST_LLM_MODEL env vars."
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Translate fused benchmark to multilingual")
    parser.add_argument("--langs", nargs="+", default=None, help="Target languages (zh ja ko)")
    parser.add_argument("--limit", type=int, default=None, help="Max entries to translate")
    parser.add_argument("--entries", nargs="+", default=None, help="Specific entry IDs")
    parser.add_argument("--providers", type=int, default=None, help="Number of providers to use (default: all)")
    args = parser.parse_args()

    providers = _build_providers()
    if args.providers:
        providers = providers[: args.providers]

    asyncio.run(translate_all(
        target_langs=args.langs,
        limit=args.limit,
        entry_ids=args.entries,
        providers=providers,
    ))
