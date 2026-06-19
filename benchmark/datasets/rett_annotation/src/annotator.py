"""LLM-driven annotation generation for Rett syndrome articles."""
from __future__ import annotations

import re

from loguru import logger

from .catalog_annotation import build_catalog_prompt, build_expected_json, load_literature_catalog, parse_llm_json
from .config import Config
from .models import RettExpectedJson

def _split_into_sections(text: str, chunk_size: int = 12000) -> list[str]:
    """Split markdown text into sections by headings, merging small sections."""
    sections = re.split(r"(?=^#{1,3}\s)", text, flags=re.MULTILINE)
    chunks: list[str] = []
    current = ""
    for section in sections:
        if len(current) + len(section) > chunk_size and current:
            chunks.append(current)
            current = section
        else:
            current += section
    if current:
        chunks.append(current)
    return chunks


async def annotate_article(
    source_md: str,
    entry_id: str,
    language: str,
    config: Config,
) -> RettExpectedJson:
    """Generate annotation for a single article using LLM."""
    from langchain_core.messages import HumanMessage, SystemMessage

    client = config.build_llm_client()
    fallback = config.build_fallback_client()

    chunks = _split_into_sections(source_md, config.annotation.chunk_size)
    combined_text = source_md if len(source_md) <= config.annotation.chunk_size * 2 else "\n\n---\n\n".join(chunks[:3])

    fields = load_literature_catalog()
    messages = [
        SystemMessage(content=build_catalog_prompt(fields)),
        HumanMessage(content=f"Article language: {language}\n\nArticle text:\n\n{combined_text}"),
    ]

    parsed: dict | None = None
    for llm in [client, fallback]:
        if llm is None:
            continue
        try:
            response = await llm.ainvoke(messages)
            parsed = parse_llm_json(str(response.content))
            if parsed is not None:
                break
        except Exception as e:
            logger.warning("LLM call failed with {}: {}", type(llm).__name__, e)

    if parsed is None:
        logger.error("All LLM providers failed for {}", entry_id)
        return RettExpectedJson(entry_id=entry_id, source_language=language)

    return build_expected_json(
        entry_id=entry_id,
        language=language,
        parsed=parsed,
        fields=fields,
    )
