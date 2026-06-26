"""Experimental baseline: primary extraction followed by review-only validation."""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from benchmark.analysis.baselines.llm_common import (
    BaselineLLMResponse,
    RawOpenAICompatibleClient,
    _runtime_config,
    quote_to_source_span,
)
from benchmark.analysis.baselines.runner import BaselineEntry, BaselineEvidenceItem, run_baseline_cli
from src.utils.text import strip_json_fences


BASELINE_ID = "B8"
BASELINE_NAME = "Primary extraction plus review-track validation"

_PRIMARY_FIELD_LIST = (
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
    "- B.mode_of_inheritance_reported: inheritance pattern (e.g. autosomal dominant, autosomal recessive)\n"
    "- C.inheritance_source: where the inheritance info came from (e.g. explicit in text, ClinGen, OMIM)\n"
    "- B.clinical_phenotypes: clinical features or phenotypes mentioned\n"
    "Evidence strength fields:\n"
    "- C.de_novo_status: whether the variant was confirmed de novo\n"
    "- C.segregation: segregation evidence\n"
    "- C.functional_assay: functional assay evidence\n"
    "- C.recurrence: recurrence or independent family evidence\n"
    "- C.contradictory_evidence: contradictory evidence mentioned, or none\n"
    "- J.clinvar_assertion: ClinVar assertion if the article reports it\n"
)


class ReviewDecision(BaseModel):
    """Review-only decision for one primary extraction candidate."""

    field_id: str
    action: Literal["approve", "reject", "correct"]
    candidate_index: int | None = None
    value: str | int | float | bool | list[str] | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_quote: str = ""
    reason: str = ""


class ReviewResponse(BaseModel):
    """Structured response from the review track."""

    decisions: list[ReviewDecision] = Field(default_factory=list)


class MainReviewTrackExtractor:
    """Run a broad primary extraction, then review only those candidates."""

    def __init__(
        self,
        *,
        temperature: float = 0.0,
        max_tokens_override: int | None = None,
        input_max_chars: int = 50000,
        timeout_override: int | None = None,
    ) -> None:
        runtime = _runtime_config(use_reasoning=False)
        self._client = RawOpenAICompatibleClient(
            model=runtime.model,
            base_url=_raw_client_base_url(runtime.base_url),
            api_keys=runtime.api_keys,
            temperature=temperature,
            max_tokens=max_tokens_override or runtime.max_tokens,
            timeout=timeout_override or max(runtime.timeout, 180),
        )
        self._input_max_chars = input_max_chars

    async def extract(self, entry: BaselineEntry, source_text: str) -> list[BaselineEvidenceItem]:
        """Extract primary candidates and apply review-only decisions."""
        primary_response = await _invoke_baseline_response(
            self._client,
            _build_primary_prompt(entry, source_text, max_chars=self._input_max_chars),
        )
        primary_items = [
            BaselineEvidenceItem(
                field_id=item.field_id,
                status=item.status,
                value=item.value,
                confidence=item.confidence,
                source_span=(
                    quote_to_source_span(item.source_quote, source_text)
                    if item.status == "found"
                    else None
                ),
            )
            for item in primary_response.evidence_items
        ]
        if not any(item.status == "found" for item in primary_items):
            return primary_items

        review_response = await _invoke_review_response(
            self._client,
            _build_review_prompt(entry, source_text, primary_items, max_chars=self._input_max_chars),
        )
        return _apply_review_decisions(primary_items, review_response.decisions, source_text)


def _build_primary_prompt(entry: BaselineEntry, document_text: str, *, max_chars: int = 50000) -> str:
    """Build the high-recall primary extraction prompt."""
    return (
        "You are evaluating an experimental ACMG/ClinGen evidence extraction baseline.\n"
        "Use a single high-recall primary extraction pass. Do not validate or reconcile internally; "
        "prefer returning plausible field candidates when the document contains direct support.\n\n"
        "Target hypothesis:\n"
        f"- Gene: {entry.gene_symbol}\n"
        f"- Disease: {entry.disease_label}\n\n"
        "Return a JSON object with an evidence_items array. Include these field IDs when supported:\n"
        f"{_PRIMARY_FIELD_LIST}\n"
        "Each evidence item must have field_id, status (found or not_found), value, confidence, "
        "and source_quote. For found items, source_quote must be a verbatim contiguous excerpt "
        "from the document text, preferably <= 240 characters. For not_found items, source_quote "
        "must be an empty string.\n"
        "Return only JSON. Do not add Markdown fences or explanation.\n\n"
        "Document text:\n"
        f"{_truncate_text(document_text, max_chars=max_chars)}"
    )


def _build_review_prompt(
    entry: BaselineEntry,
    document_text: str,
    primary_items: list[BaselineEvidenceItem],
    *,
    max_chars: int = 50000,
) -> str:
    """Build a prompt that reviews primary candidates without adding new ones."""
    candidates = [
        {
            "candidate_index": index,
            "field_id": item.field_id,
            "status": item.status,
            "value": item.value,
            "confidence": item.confidence,
            "source_span": item.source_span,
        }
        for index, item in enumerate(primary_items)
        if item.status == "found"
    ]
    return (
        "You are the review track for an ACMG/ClinGen extraction experiment.\n"
        "Your job is to approve, reject, or correct only the primary extraction candidates below. "
        "Do not add new field IDs, do not create new candidates, and do not perform a second full extraction.\n\n"
        "Decision policy:\n"
        "- approve: the candidate is directly supported by the document.\n"
        "- reject: the candidate is not directly supported, is inferred too weakly, or belongs to another context.\n"
        "- correct: the candidate field is relevant but the value or source_quote should be fixed.\n\n"
        "Target hypothesis:\n"
        f"- Gene: {entry.gene_symbol}\n"
        f"- Disease: {entry.disease_label}\n\n"
        "Primary candidates JSON:\n"
        f"{json.dumps(candidates, ensure_ascii=False, indent=2)}\n\n"
        "Return JSON with this schema: "
        '{"decisions":[{"candidate_index":0,"field_id":"A.gene_symbol","action":"approve|reject|correct",'
        '"value":"","confidence":0.0,"source_quote":"","reason":""}]}.\n'
        "For approve, value may repeat the candidate value. For reject, value and source_quote may be empty. "
        "For correct, include the corrected value and a verbatim contiguous source_quote.\n"
        "Return only JSON. Do not add Markdown fences or explanation.\n\n"
        "Document text:\n"
        f"{_truncate_text(document_text, max_chars=max_chars)}"
    )


def _apply_review_decisions(
    primary_items: list[BaselineEvidenceItem],
    decisions: list[ReviewDecision],
    source_text: str,
) -> list[BaselineEvidenceItem]:
    """Apply review decisions while preserving the primary candidate set."""
    decisions_by_index = {
        decision.candidate_index: decision
        for decision in decisions
        if decision.candidate_index is not None
    }
    decisions_by_field: dict[str, ReviewDecision] = {}
    for decision in decisions:
        if decision.candidate_index is None and decision.field_id not in decisions_by_field:
            decisions_by_field[decision.field_id] = decision

    reviewed: list[BaselineEvidenceItem] = []
    for index, item in enumerate(primary_items):
        decision = decisions_by_index.get(index)
        if decision is None:
            decision = decisions_by_field.get(item.field_id)
        if decision is None or decision.field_id != item.field_id:
            reviewed.append(item)
            continue
        if decision.action == "reject":
            reviewed.append(
                BaselineEvidenceItem(
                    field_id=item.field_id,
                    status="not_found",
                    value="",
                    confidence=0.0,
                )
            )
            continue
        if decision.action == "correct":
            reviewed.append(
                BaselineEvidenceItem(
                    field_id=item.field_id,
                    status="found" if decision.value not in (None, "") else "not_found",
                    value=decision.value if decision.value is not None else "",
                    confidence=decision.confidence,
                    source_span=quote_to_source_span(decision.source_quote, source_text),
                )
            )
            continue
        reviewed.append(item)
    return reviewed


async def extract(entry: BaselineEntry, source_text: str) -> list[BaselineEvidenceItem]:
    """Module-level extractor used by baseline runner."""
    extractor = MainReviewTrackExtractor()
    return await extractor.extract(entry, source_text)


def main() -> None:
    run_baseline_cli(BASELINE_ID, BASELINE_NAME, extract)


async def _invoke_baseline_response(client: RawOpenAICompatibleClient, prompt: str) -> BaselineLLMResponse:
    json_text = strip_json_fences(await client.ainvoke_json_text(prompt))
    try:
        return BaselineLLMResponse.model_validate_json(json_text)
    except (ValidationError, ValueError):
        match = re.search(r"\{.*\}", json_text, flags=re.DOTALL)
        if not match:
            raise
        return BaselineLLMResponse.model_validate(json.loads(match.group(0)))


async def _invoke_review_response(client: RawOpenAICompatibleClient, prompt: str) -> ReviewResponse:
    json_text = strip_json_fences(await client.ainvoke_json_text(prompt))
    try:
        return ReviewResponse.model_validate_json(json_text)
    except (ValidationError, ValueError):
        match = re.search(r"\{.*\}", json_text, flags=re.DOTALL)
        if not match:
            raise
        return ReviewResponse.model_validate(json.loads(match.group(0)))


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n\n[...TRUNCATED...]\n\n{tail}"


def _raw_client_base_url(base_url: str) -> str:
    """Normalize OpenAI-compatible base URL for RawOpenAICompatibleClient."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized[:-3]
    return normalized


if __name__ == "__main__":
    main()
