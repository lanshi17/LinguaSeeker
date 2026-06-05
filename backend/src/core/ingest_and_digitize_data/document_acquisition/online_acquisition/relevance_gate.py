"""Phase 3: LLM-based relevance gate for downloaded PDFs.

After download, each PDF's content is checked against the original query
topic. Irrelevant files are removed from results and optionally deleted
from disk.

Usage::

    from .relevance_gate import run_relevance_gate

    gate_result = await run_relevance_gate(
        query="Rett syndrome MECP2 mutation",
        downloads=download_results,
    )
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

import fitz
from loguru import logger
from openai import AsyncOpenAI

from src.core.config import get_config

# ── Prompt templates ──────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a medical literature relevance classifier.

Given a search query/topic and an excerpt from a downloaded PDF, determine \
whether the document is genuinely relevant to the query topic.

A document is RELEVANT if:
- Its primary subject matches the query topic
- It contains substantive discussion, data, or analysis about the topic
- It is a case report, review, or study directly about the topic

A document is NOT RELEVANT if:
- It only mentions the topic in passing or as a comparison
- It is primarily about a different disease/topic
- It is a general reference work, editorial, or organizational document
- The content does not match the query topic at all

Reply with ONLY JSON (no markdown fences):
{"relevant": true/false, "reason": "brief explanation in English"}"""

_USER_PROMPT = """Search query/topic: {query}

Document language: {lang}
Document title: {title}
PDF excerpt (first {max_pages} pages):
---
{text}
---

Is this document relevant to the search query?"""


# ── Config defaults ───────────────────────────────────────────────────────

_DEFAULT_MAX_PAGES = 3
_DEFAULT_MAX_CHARS = 3000
_DEFAULT_CONCURRENCY = 6
_DEFAULT_MAX_TOKENS = 4096


# ── Result types ──────────────────────────────────────────────────────────

@dataclass
class RelevanceJudgment:
    """Result of relevance check for a single PDF."""
    file_path: str
    relevant: bool = False
    reason: str = ""
    error: str = ""


@dataclass
class RelevanceGateResult:
    """Aggregated result of the relevance gate."""
    total: int = 0
    relevant: int = 0
    irrelevant: int = 0
    errors: int = 0
    judgments: List[RelevanceJudgment] = field(default_factory=list)
    removed_paths: List[str] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────

def _extract_text(
    pdf_path: str,
    max_pages: int = _DEFAULT_MAX_PAGES,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> str:
    """Extract plain text from the first pages of a PDF."""
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return ""

    chunks: List[str] = []
    try:
        for i in range(min(max_pages, len(doc))):
            txt = doc[i].get_text("text") or ""
            if txt:
                chunks.append(txt)
            if sum(len(c) for c in chunks) >= max_chars:
                break
    finally:
        doc.close()

    return "\n".join(chunks)[:max_chars]


def _parse_response(raw: str) -> Tuple[bool, str]:
    """Parse LLM JSON response into (relevant, reason)."""
    text = raw.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        obj = json.loads(text)
        return bool(obj.get("relevant", False)), str(obj.get("reason", ""))
    except json.JSONDecodeError:
        return False, "json_parse_error"


# ── Core ──────────────────────────────────────────────────────────────────

async def _check_one(
    client: AsyncOpenAI,
    sem: asyncio.Semaphore,
    model: str,
    query: str,
    download: Dict[str, Any],
    max_pages: int,
    max_chars: int,
) -> RelevanceJudgment:
    """Check a single downloaded PDF for relevance to the query."""
    file_path = download.get("file_path") or ""
    lang = download.get("lang", "")
    title = download.get("title", "")

    if not file_path or not Path(file_path).exists():
        return RelevanceJudgment(file_path=file_path, error="file_not_found")

    text = await asyncio.to_thread(_extract_text, file_path, max_pages, max_chars)
    if not text or len(text.strip()) < 30:
        return RelevanceJudgment(file_path=file_path, error="empty_text")

    user_msg = _USER_PROMPT.format(
        query=query,
        lang=lang,
        title=title,
        max_pages=max_pages,
        text=text,
    )

    async with sem:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=_DEFAULT_MAX_TOKENS,
            )
            raw = (resp.choices[0].message.content or "").strip()
            relevant, reason = _parse_response(raw)
            return RelevanceJudgment(
                file_path=file_path,
                relevant=relevant,
                reason=reason,
            )
        except Exception as exc:
            return RelevanceJudgment(
                file_path=file_path,
                error=str(exc)[:200],
            )


async def run_relevance_gate(
    *,
    query: str,
    downloads: List[Dict[str, Any]],
    delete_files: bool = True,
    concurrency: int = _DEFAULT_CONCURRENCY,
    max_pages: int = _DEFAULT_MAX_PAGES,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> RelevanceGateResult:
    """Run LLM relevance gate on downloaded PDFs.

    Args:
        query: Original search query/topic for relevance comparison.
        downloads: List of download dicts (must have ``file_path``).
        delete_files: If True, delete irrelevant PDFs from disk.
        concurrency: Max parallel LLM calls.
        max_pages: Pages to extract per PDF.
        max_chars: Max chars per PDF excerpt.

    Returns:
        RelevanceGateResult with filtered download list and statistics.
    """
    if not downloads:
        return RelevanceGateResult()

    cfg = get_config()
    model = (cfg.llm.model or "").strip()
    base_url = (cfg.llm.base_url or "").strip().rstrip("/")
    api_key = (cfg.llm.api_key or "").strip()

    if not model or not base_url:
        logger.warning("relevance_gate skipped: missing LLM config")
        return RelevanceGateResult(
            total=len(downloads),
            relevant=len(downloads),
        )

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    sem = asyncio.Semaphore(concurrency)

    logger.info(f"relevance_gate: checking {len(downloads)} downloads against query: {query[:80]}")

    tasks = [
        _check_one(client, sem, model, query, dl, max_pages, max_chars)
        for dl in downloads
    ]

    result = RelevanceGateResult(total=len(downloads))

    for coro in asyncio.as_completed(tasks):
        judgment = await coro
        result.judgments.append(judgment)

        if judgment.error:
            result.errors += 1
            # Treat errored files as relevant (keep them)
            logger.debug(f"relevance_gate error: {judgment.file_path}: {judgment.error}")
        elif judgment.relevant:
            result.relevant += 1
        else:
            result.irrelevant += 1
            result.removed_paths.append(judgment.file_path)
            logger.info(
                f"relevance_gate: removing {Path(judgment.file_path).name} "
                f"— {judgment.reason[:80]}"
            )

    # Delete irrelevant files from disk
    if delete_files and result.removed_paths:
        for fp in result.removed_paths:
            try:
                os.unlink(fp)
                logger.debug(f"relevance_gate: deleted {fp}")
            except FileNotFoundError:
                pass
            except Exception as exc:
                logger.warning(f"relevance_gate: failed to delete {fp}: {exc}")

    logger.info(
        f"relevance_gate: total={result.total} "
        f"relevant={result.relevant} irrelevant={result.irrelevant} errors={result.errors}"
    )

    return result
