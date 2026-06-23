"""Common LLM helpers for layer-3 baseline extractors."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

import httpx
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from benchmark.analysis.baselines.runner import BaselineEntry, BaselineEvidenceItem
from src.core.config import get_config
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.language_detector import (
    should_skip_translation,
)
from src.utils.llm_adapter import LLMPoolAdapter, create_llm_client
from src.utils.text import strip_json_fences


BaselineMode = Literal[
    "naive",
    "translate_then_extract",
    "original_only",
    "rag",
    "single_agent_cot",
    "citation_required",
    "direct_json",
    "expanded",
]


class BaselineLLMEvidenceItem(BaseModel):
    """LLM evidence item response for baseline extraction."""

    field_id: str
    status: Literal["found", "not_found"] = "not_found"
    value: str | int | float | bool | list[str] | None = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_quote: str = ""

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> object:
        """Accept common prompt-only schema drift in status values."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"", "none", "unknown", "not found", "not_found"}:
                return "not_found"
            if normalized not in {"found", "not_found"}:
                return "found"
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: object) -> object:
        """Accept common LLM confidence labels in addition to numeric scores."""
        if value is None:
            return 0.0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                return 0.0
            if normalized in {"n/a", "na", "not applicable", "not_applicable"}:
                return 0.0
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
                    return 0.0
            try:
                return float(normalized)
            except ValueError:
                return 0.0
        return value


class BaselineLLMResponse(BaseModel):
    """Structured LLM response for a baseline run."""

    evidence_items: list[BaselineLLMEvidenceItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_evidence_items(cls, value: object) -> object:
        """Accept field-keyed evidence maps from prompt-only LLM baselines."""
        if not isinstance(value, dict):
            return value
        raw_items = value.get("evidence_items")
        if isinstance(raw_items, dict):
            value = dict(value)
            value["evidence_items"] = [_field_keyed_item(field_id, item) for field_id, item in raw_items.items()]
            return value
        if isinstance(raw_items, list):
            normalized_items: list[object] = []
            changed = False
            for raw_item in raw_items:
                normalized_item = _normalize_field_keyed_list_item(raw_item)
                changed = changed or normalized_item is not raw_item
                if isinstance(normalized_item, list):
                    normalized_items.extend(normalized_item)
                else:
                    normalized_items.append(normalized_item)
            if changed:
                value = dict(value)
                value["evidence_items"] = normalized_items
        return value


def _normalize_field_keyed_list_item(raw_item: object) -> object | list[object]:
    if not isinstance(raw_item, dict) or "field_id" in raw_item:
        return raw_item
    if not raw_item or not all(_looks_like_field_id(field_id) for field_id in raw_item):
        return raw_item
    return [_field_keyed_item(field_id, item) for field_id, item in raw_item.items()]


def _field_keyed_item(field_id: str, item: object) -> object:
    if not isinstance(item, dict):
        return {"field_id": field_id, "value": item, "status": "found" if item not in (None, "") else "not_found"}
    normalized = dict(item)
    normalized.setdefault("field_id", field_id)
    return normalized


def _looks_like_field_id(value: object) -> bool:
    return isinstance(value, str) and re.match(r"^[A-Z]\.[A-Za-z0-9_]+$", value) is not None


@dataclass(frozen=True)
class LLMRuntimeConfig:
    """LLM runtime settings for one baseline."""

    model: str
    base_url: str
    api_keys: list[str]
    max_tokens: int
    timeout: int


@dataclass
class RawOpenAICompatibleClient:
    """Minimal OpenAI-compatible chat client for provider aliases LangChain cannot parse."""

    model: str
    base_url: str
    api_keys: list[str]
    temperature: float
    max_tokens: int
    timeout: int
    _next_key_index: int = 0

    def request_payload(self, prompt: str) -> dict[str, object]:
        """Build the OpenAI-compatible chat completion payload."""
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    async def ainvoke_json_text(self, prompt: str) -> str:
        """Invoke chat completions and return the assistant text content."""
        key = self._next_api_key()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=self.request_payload(prompt),
            )
        response.raise_for_status()
        return _extract_chat_content(response.json())

    def _next_api_key(self) -> str:
        if not self.api_keys:
            return ""
        key = self.api_keys[self._next_key_index % len(self.api_keys)]
        self._next_key_index += 1
        return key


class LLMBaselineExtractor:
    """Single-call and two-call LLM baselines for ClinGen evidence extraction."""

    def __init__(
        self,
        mode: BaselineMode,
        *,
        model_override: str | None = None,
        temperature: float = 0.0,
        max_tokens_override: int | None = None,
        input_max_chars: int = 50000,
        use_raw_client: bool = False,
    ):
        self._mode = mode
        self._input_max_chars = input_max_chars
        runtime = _runtime_config(use_reasoning=mode == "single_agent_cot")
        model = model_override or runtime.model
        max_tokens = max_tokens_override or runtime.max_tokens
        self._raw_client: RawOpenAICompatibleClient | None = None
        self._client: LLMPoolAdapter | None = None
        if use_raw_client:
            self._raw_client = RawOpenAICompatibleClient(
                model=model,
                base_url=runtime.base_url,
                api_keys=runtime.api_keys,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=runtime.timeout,
            )
        else:
            self._client = create_llm_client(
                model=model,
                base_url=runtime.base_url,
                api_keys=runtime.api_keys,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=runtime.timeout,
            )

    async def extract(self, entry: BaselineEntry, source_text: str) -> list[BaselineEvidenceItem]:
        working_text = source_text
        if should_translate_before_extract(self._mode, source_text):
            working_text = await self._translate_to_english(source_text)
        if self._mode == "rag":
            working_text = _select_relevant_snippets(source_text, entry)

        prompt = _build_extraction_prompt(self._mode, entry, working_text, max_chars=self._input_max_chars)
        if self._raw_client is not None:
            response = await _invoke_json_raw(self._raw_client, prompt)
        elif self._client is not None:
            response = await _invoke_json(self._client, prompt)
        else:
            raise RuntimeError("baseline LLM client is not configured")
        return [
            BaselineEvidenceItem(
                field_id=item.field_id,
                status=item.status,
                value=item.value,
                confidence=item.confidence,
                source_span=(
                    quote_to_source_span(item.source_quote, source_text)
                    if self._mode == "citation_required" and item.status == "found"
                    else None
                ),
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
        if self._client is None:
            raise RuntimeError("translation baseline requires the LangChain client")
        message = await self._client.ainvoke([HumanMessage(content=prompt)])
        if not isinstance(message.content, str):
            raise RuntimeError("translation baseline returned non-text content")
        return message.content


def make_extractor(
    mode: BaselineMode,
    *,
    model_override: str | None = None,
    temperature: float = 0.0,
    max_tokens_override: int | None = None,
    input_max_chars: int = 50000,
    use_raw_client: bool = False,
) -> LLMBaselineExtractor:
    """Create an LLM-backed baseline extractor."""
    return LLMBaselineExtractor(
        mode=mode,
        model_override=model_override,
        temperature=temperature,
        max_tokens_override=max_tokens_override,
        input_max_chars=input_max_chars,
        use_raw_client=use_raw_client,
    )


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


async def _invoke_json_raw(client: RawOpenAICompatibleClient, prompt: str) -> BaselineLLMResponse:
    json_text = strip_json_fences(await client.ainvoke_json_text(prompt))
    try:
        return BaselineLLMResponse.model_validate_json(json_text)
    except (ValidationError, ValueError):
        match = re.search(r"\{.*\}", json_text, flags=re.DOTALL)
        if not match:
            raise
        return BaselineLLMResponse.model_validate(json.loads(match.group(0)))


def _extract_chat_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise RuntimeError("raw baseline response is not a JSON object")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("raw baseline response missing choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("raw baseline first choice is not an object")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("raw baseline response missing message")
    content = message.get("content")
    if not isinstance(content, str):
        raise RuntimeError("raw baseline response content is not text")
    return content


def _build_extraction_prompt(
    mode: BaselineMode,
    entry: BaselineEntry,
    document_text: str,
    *,
    max_chars: int = 50000,
) -> str:
    mode_instruction = {
        "naive": "Use one direct extraction pass. Do not perform multi-stage validation.",
        "translate_then_extract": "The document has already been translated to English. Extract from this translation only.",
        "original_only": "Extract from the original-language document only. Do not translate first.",
        "rag": "Extract only from the retrieved snippets below.",
        "single_agent_cot": (
            "Think through the evidence internally as a single agent, but return only the final JSON object. "
            "Do not expose reasoning text."
        ),
        "citation_required": (
            "Use one direct prompt-only extraction pass. Do not use tools, retrieval, multi-agent validation, "
            "evidence graphs, or reconciliation. For each found field, include source_quote as a verbatim "
            "contiguous quote from the document text."
        ),
        "direct_json": "Use one direct extraction pass. Do not perform multi-stage validation.",
        "expanded": (
            "Use one direct extraction pass. Do not use tools, retrieval, multi-agent validation, "
            "evidence graphs, reconciliation, or any multi-stage pipeline. "
            "Extract all fields listed below in a single call."
        ),
    }[mode]
    citation_instruction = (
        "Each evidence item must have field_id, status (found or not_found), value, confidence, "
        "and source_quote. For found items, source_quote must be a verbatim contiguous excerpt "
        "from the document text, preferably <= 240 characters. For not_found items, source_quote "
        "must be an empty string.\n"
        if mode == "citation_required"
        else "Each evidence item must have field_id, status (found or not_found), value, and confidence.\n"
    )
    if mode == "expanded":
        field_list = (
            "Return a JSON object with an evidence_items array. Include all of the following field IDs "
            "(use status=not_found for any field not mentioned in the document):\n"
            "Simple factual fields:\n"
            "- A.gene_symbol: the target gene symbol if supported\n"
            "- B.disease_diagnosis: the target disease or phenotype if supported\n"
            "- A.gene_disease_relationship: one of causative, disputed, refuted, uncertain, or not_found\n"
            "- A.variant_hgvs_c: the HGVS coding-level variant notation (e.g. c.473C>T)\n"
            "- A.variant_hgvs_p: the HGVS protein-level variant notation (e.g. p.T158M)\n"
            "- A.variant_type: the variant type (e.g. SNV, deletion, insertion, CNV, frameshift)\n"
            "- A.variant_consequence_class: the consequence class (e.g. missense, nonsense, frameshift, splice-site)\n"
            "Contextual fields:\n"
            "- B.sex: patient sex (male, female, mixed, unknown)\n"
            "- B.age_of_onset: age of onset as reported (e.g. '2 years', 'infancy', 'adult-onset')\n"
            "- B.mode_of_inheritance_reported: inheritance pattern (e.g. autosomal dominant, autosomal recessive, X-linked dominant, de novo)\n"
            "- C.inheritance_source: where the inheritance info came from (e.g. 'explicit in text', 'ClinGen', 'OMIM')\n"
            "- B.clinical_phenotypes: clinical features or phenotypes mentioned (free text)\n"
            "Evidence strength fields:\n"
            "- C.de_novo_status: whether the variant was confirmed de novo (de novo, not de novo, unknown)\n"
            "- C.segregation: segregation evidence (e.g. 'cosegregation in family', 'not reported')\n"
            "- C.functional_assay: functional assay evidence (e.g. 'loss of function shown', 'not reported')\n"
            "- C.recurrence: recurrence or independent family evidence (e.g. 'multiple unrelated families', 'not reported')\n"
            "- C.contradictory_evidence: any contradictory evidence mentioned (free text or 'none')\n\n"
        )
    else:
        field_list = (
            "Return a JSON object with an evidence_items array. Include exactly these field IDs:\n"
            "- A.gene_symbol: the target gene symbol if supported\n"
            "- B.disease_diagnosis: the target disease or phenotype if supported\n"
            "- A.gene_disease_relationship: one of causative, disputed, refuted, uncertain, or not_found\n\n"
        )
    return (
        "You are evaluating a baseline for ACMG/ClinGen gene-disease evidence extraction.\n"
        f"{mode_instruction}\n\n"
        "Target hypothesis:\n"
        f"- Gene: {entry.gene_symbol}\n"
        f"- Disease: {entry.disease_label}\n\n"
        f"{field_list}"
        f"{citation_instruction}"
        "Return only JSON. Do not add Markdown fences or explanation.\n\n"
        "Document text:\n"
        f"{_truncate_text(document_text, max_chars=max_chars)}"
    )


def quote_to_source_span(source_quote: str, source_text: str) -> dict[str, object]:
    """Map an LLM-provided quote to canonical source text for measurement only."""
    quote = source_quote.strip()
    if not quote:
        return {
            "span_id": "llm-quote",
            "start_offset": -1,
            "end_offset": -1,
            "text_snippet": "",
            "source_precision": "llm_quote_missing",
        }
    start = source_text.find(quote)
    if start >= 0:
        return {
            "span_id": "llm-quote",
            "start_offset": start,
            "end_offset": start + len(quote),
            "text_snippet": quote,
            "source_precision": "llm_quote_exact",
        }
    return {
        "span_id": "llm-quote",
        "start_offset": -1,
        "end_offset": -1,
        "text_snippet": quote,
        "source_precision": "llm_quote_unmapped",
    }


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
