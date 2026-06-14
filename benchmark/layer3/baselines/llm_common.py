"""Common LLM helpers for layer-3 baseline extractors."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, ValidationError, field_validator

from benchmark.layer3.baselines.runner import BaselineEntry, BaselineEvidenceItem
from src.core.config import get_config
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.language_detector import (
    should_skip_translation,
)
from src.utils.llm_adapter import LLMPoolAdapter, create_llm_client
from src.utils.text import strip_json_fences


BaselineMode = Literal["naive", "translate_then_extract", "original_only", "rag", "single_agent_cot"]


class BaselineLLMEvidenceItem(BaseModel):
    """LLM evidence item response for baseline extraction."""

    field_id: str
    status: Literal["found", "not_found"] = "not_found"
    value: str | int | float | bool | list[str] | None = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: object) -> object:
        """Accept common LLM confidence labels in addition to numeric scores."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            label_scores = {
                "high": 0.9,
                "strong": 0.9,
                "medium": 0.6,
                "moderate": 0.6,
                "low": 0.3,
                "none": 0.0,
                "unknown": 0.0,
            }
            if normalized in label_scores:
                return label_scores[normalized]
            if normalized.endswith("%"):
                try:
                    return float(normalized[:-1]) / 100.0
                except ValueError:
                    return value
        return value


class BaselineLLMResponse(BaseModel):
    """Structured LLM response for a baseline run."""

    evidence_items: list[BaselineLLMEvidenceItem] = Field(default_factory=list)


@dataclass(frozen=True)
class LLMRuntimeConfig:
    """LLM runtime settings for one baseline."""

    model: str
    base_url: str
    api_keys: list[str]
    max_tokens: int
    timeout: int


class LLMBaselineExtractor:
    """Single-call and two-call LLM baselines for ClinGen evidence extraction."""

    def __init__(self, mode: BaselineMode):
        self._mode = mode
        runtime = _runtime_config(use_reasoning=mode == "single_agent_cot")
        self._client = create_llm_client(
            model=runtime.model,
            base_url=runtime.base_url,
            api_keys=runtime.api_keys,
            temperature=0.0,
            max_tokens=runtime.max_tokens,
            timeout=runtime.timeout,
        )

    async def extract(self, entry: BaselineEntry, source_text: str) -> list[BaselineEvidenceItem]:
        working_text = source_text
        if should_translate_before_extract(self._mode, source_text):
            working_text = await self._translate_to_english(source_text)
        if self._mode == "rag":
            working_text = _select_relevant_snippets(source_text, entry)

        prompt = _build_extraction_prompt(self._mode, entry, working_text)
        response = await _invoke_json(self._client, prompt)
        return [
            BaselineEvidenceItem(
                field_id=item.field_id,
                status=item.status,
                value=item.value,
                confidence=item.confidence,
            )
            for item in response.evidence_items
        ]

    async def _translate_to_english(self, source_text: str) -> str:
        prompt = (
            "Translate the following biomedical article text into English. "
            "Preserve gene symbols, disease names, variants, citations, and table-like facts. "
            "Return only the English translation.\n\n"
            f"{_truncate_text(source_text, max_chars=50000)}"
        )
        message = await self._client.ainvoke([HumanMessage(content=prompt)])
        if not isinstance(message.content, str):
            raise RuntimeError("translation baseline returned non-text content")
        return message.content


def make_extractor(mode: BaselineMode) -> LLMBaselineExtractor:
    """Create an LLM-backed baseline extractor."""
    return LLMBaselineExtractor(mode=mode)


def should_translate_before_extract(mode: BaselineMode, source_text: str) -> bool:
    """Return whether a baseline should translate before extraction."""
    return mode == "translate_then_extract" and not should_skip_translation(source_text)


def _runtime_config(use_reasoning: bool) -> LLMRuntimeConfig:
    cfg = get_config()
    llm_cfg = cfg.reasoning if use_reasoning else cfg.llm
    fallback = cfg.llm
    api_keys = [key for key in llm_cfg.all_api_keys if key.strip()]
    if not api_keys and llm_cfg.api_key.strip():
        api_keys = [llm_cfg.api_key.strip()]
    if not api_keys and use_reasoning:
        api_keys = [key for key in fallback.all_api_keys if key.strip()]
        if not api_keys and fallback.api_key.strip():
            api_keys = [fallback.api_key.strip()]
    if not api_keys:
        raise RuntimeError("LLM API key is not configured for baseline extraction")

    model = llm_cfg.model or fallback.model
    base_url = llm_cfg.base_url or fallback.base_url
    if not model or not base_url:
        raise RuntimeError("LLM model/base_url is not configured for baseline extraction")

    return LLMRuntimeConfig(
        model=model,
        base_url=base_url,
        api_keys=api_keys,
        max_tokens=llm_cfg.max_tokens or fallback.max_tokens or 8192,
        timeout=llm_cfg.timeout or fallback.timeout or 180,
    )


async def _invoke_json(client: LLMPoolAdapter, prompt: str) -> BaselineLLMResponse:
    message = await client.ainvoke([HumanMessage(content=prompt)])
    if not isinstance(message.content, str):
        raise RuntimeError("baseline extractor returned non-text content")
    json_text = strip_json_fences(message.content)
    try:
        return BaselineLLMResponse.model_validate_json(json_text)
    except (ValidationError, ValueError):
        match = re.search(r"\{.*\}", json_text, flags=re.DOTALL)
        if not match:
            raise
        return BaselineLLMResponse.model_validate(json.loads(match.group(0)))


def _build_extraction_prompt(mode: BaselineMode, entry: BaselineEntry, document_text: str) -> str:
    mode_instruction = {
        "naive": "Use one direct extraction pass. Do not perform multi-stage validation.",
        "translate_then_extract": "The document has already been translated to English. Extract from this translation only.",
        "original_only": "Extract from the original-language document only. Do not translate first.",
        "rag": "Extract only from the retrieved snippets below.",
        "single_agent_cot": (
            "Think through the evidence internally as a single agent, but return only the final JSON object. "
            "Do not expose reasoning text."
        ),
    }[mode]
    return (
        "You are evaluating a baseline for ACMG/ClinGen gene-disease evidence extraction.\n"
        f"{mode_instruction}\n\n"
        "Target hypothesis:\n"
        f"- Gene: {entry.gene_symbol}\n"
        f"- Disease: {entry.disease_label}\n\n"
        "Return a JSON object with an evidence_items array. Include exactly these field IDs:\n"
        "- A.gene_symbol: the target gene symbol if supported\n"
        "- B.disease_diagnosis: the target disease or phenotype if supported\n"
        "- A.gene_disease_relationship: one of causative, disputed, refuted, uncertain, or not_found\n\n"
        "Each evidence item must have field_id, status (found or not_found), value, and confidence.\n"
        "Return only JSON. Do not add Markdown fences or explanation.\n\n"
        "Document text:\n"
        f"{_truncate_text(document_text, max_chars=50000)}"
    )


def _select_relevant_snippets(source_text: str, entry: BaselineEntry, max_chars: int = 12000) -> str:
    terms = _keyword_terms(entry)
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", source_text) if part.strip()]
    scored: list[tuple[int, int, str]] = []
    for idx, paragraph in enumerate(paragraphs):
        haystack = paragraph.casefold()
        score = sum(1 for term in terms if term and term in haystack)
        if score > 0:
            scored.append((score, -idx, paragraph))
    if not scored:
        return _truncate_text(source_text, max_chars=max_chars)
    selected: list[str] = []
    total = 0
    for _score, _neg_idx, paragraph in sorted(scored, reverse=True):
        if total + len(paragraph) > max_chars and selected:
            break
        selected.append(paragraph)
        total += len(paragraph)
    return "\n\n".join(selected)


def _keyword_terms(entry: BaselineEntry) -> list[str]:
    terms = [entry.gene_symbol.casefold(), entry.disease_label.casefold()]
    terms.extend(
        token.casefold()
        for token in re.split(r"[^A-Za-z0-9]+", entry.disease_label)
        if len(token) >= 4
    )
    return list(dict.fromkeys(terms))


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n\n[...TRUNCATED...]\n\n{tail}"
