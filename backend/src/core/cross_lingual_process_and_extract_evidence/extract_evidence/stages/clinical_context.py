"""Clinical context supplement pass — phenotype, sex, age, inheritance fields.

Targets 6 medium-contextual fields that the main catalog_extraction stage
consistently marks as ``not_found`` due to attention dilution across 62+
fields.  This focused pass uses a small field set (≤10) with explicit
extraction guidance per field.
"""
from __future__ import annotations

import asyncio

from loguru import logger

from ..chunking import (
    STRONG_TIER_INPUT_BUDGET_TOKENS,
    build_block_prompt_chunks,
)
from ..contracts import (
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    TrackDocument,
)
from ..prompts import get_clinical_context_prompt
from ..providers import EvidenceModelTier, LangChainEvidenceProvider
from ...cross_lingual.format.segmenter import estimate_tokens

# Fields targeted by this supplement pass.
CLINICAL_CONTEXT_FIELDS: tuple[str, ...] = (
    "B.clinical_phenotypes",
    "B.sex",
    "B.age_of_onset",
    "B.mode_of_inheritance_reported",
    "C.inheritance_source",
    "C.de_novo_status",
)

_DEFAULT_CHUNK_CONCURRENCY = 5


class ClinicalContextStage:
    """Focused LLM pass for clinical-context fields only."""

    def __init__(
        self,
        provider: LangChainEvidenceProvider,
        input_budget_tokens: int = STRONG_TIER_INPUT_BUDGET_TOKENS,
    ):
        self._provider = provider
        self._input_budget_tokens = input_budget_tokens

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        document: TrackDocument,
        current_items: list[EvidenceItem],
        evidence_map: DocumentEvidenceMap | None = None,
    ) -> list[EvidenceItem]:
        """Run clinical context extraction and return *new* items to merge."""
        summary = self._summarize_items(current_items)
        overhead = estimate_tokens(get_clinical_context_prompt(
            document_id=document.document_id,
            track=document.track,
            text="",
            current_items_summary=summary,
        ))
        chunks = build_block_prompt_chunks(
            document,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=overhead,
        )
        all_new: list[EvidenceItem] = []
        for chunk in chunks:
            chunk_summary = self._chunk_summary(summary, chunk)
            try:
                prompt = get_clinical_context_prompt(
                    document_id=document.document_id,
                    track=document.track,
                    text=chunk.text,
                    current_items_summary=chunk_summary,
                )
                stage = "clinical_context" if chunk.total == 1 else f"clinical_context/{chunk.index}"
                items = self._provider.invoke_structured(
                    prompt=prompt,
                    output_schema=list[EvidenceItem],
                    tier=EvidenceModelTier.STRONG,
                    stage=stage,
                )
                if isinstance(items, list):
                    all_new.extend(items)
            except Exception:
                logger.warning(
                    "clinical_context chunk {}/{} failed, skipping",
                    chunk.index, chunk.total,
                )
        return self._merge(all_new, current_items)

    async def run_async(
        self,
        document: TrackDocument,
        current_items: list[EvidenceItem],
        evidence_map: DocumentEvidenceMap | None = None,
    ) -> list[EvidenceItem]:
        """Async variant with concurrent chunk execution."""
        summary = self._summarize_items(current_items)
        overhead = estimate_tokens(get_clinical_context_prompt(
            document_id=document.document_id,
            track=document.track,
            text="",
            current_items_summary=summary,
        ))
        chunks = build_block_prompt_chunks(
            document,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=overhead,
        )
        sem = asyncio.Semaphore(_DEFAULT_CHUNK_CONCURRENCY)

        async def _extract_chunk(chunk):  # noqa: ANN001
            chunk_summary = self._chunk_summary(summary, chunk)
            prompt = get_clinical_context_prompt(
                document_id=document.document_id,
                track=document.track,
                text=chunk.text,
                current_items_summary=chunk_summary,
            )
            stage = "clinical_context" if chunk.total == 1 else f"clinical_context/{chunk.index}"
            async with sem:
                return await self._provider.ainvoke_structured(
                    prompt=prompt,
                    output_schema=list[EvidenceItem],
                    tier=EvidenceModelTier.STRONG,
                    stage=stage,
                )

        results = await asyncio.gather(
            *[_extract_chunk(c) for c in chunks],
            return_exceptions=True,
        )
        all_new: list[EvidenceItem] = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.warning("clinical_context chunk {}/{} failed: {}", i + 1, len(chunks), result)
                continue
            if isinstance(result, list):
                all_new.extend(result)
        return self._merge(all_new, current_items)

    # ------------------------------------------------------------------
    # Merge logic
    # ------------------------------------------------------------------

    @staticmethod
    def _merge(
        new_items: list[EvidenceItem],
        existing_items: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        """Return *supplementary* items that should be added to evidence_items.

        Rules:
        - Only consider items whose field_id is in CLINICAL_CONTEXT_FIELDS.
        - Skip items with status != FOUND.
        - If existing has a FOUND item for the same field_id with equal or
          higher confidence, skip.
        - If existing has the same value for the same field_id, skip (dedup).
        """
        target_fields = set(CLINICAL_CONTEXT_FIELDS)
        existing_by_field: dict[str, list[EvidenceItem]] = {}
        for item in existing_items:
            if item.field_id in target_fields:
                existing_by_field.setdefault(item.field_id, []).append(item)

        to_add: list[EvidenceItem] = []
        for item in new_items:
            if item.field_id not in target_fields:
                continue
            if item.status != EvidenceStatus.FOUND:
                continue

            existing_for_field = existing_by_field.get(item.field_id, [])

            # Check: is there an existing FOUND item with >= confidence?
            best_existing_confidence = max(
                (e.confidence for e in existing_for_field if e.status == EvidenceStatus.FOUND),
                default=-1.0,
            )
            if best_existing_confidence >= item.confidence:
                continue

            # Check: duplicate value
            new_value = str(item.value).strip().casefold()
            if any(str(e.value).strip().casefold() == new_value for e in existing_for_field):
                continue

            to_add.append(item)
        return to_add

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize_items(items: list[EvidenceItem]) -> str:
        found = [i for i in items if i.status == EvidenceStatus.FOUND]
        if not found:
            return "No evidence items extracted yet"
        lines = [f"{i.field_id}: {i.value}" for i in found[:20]]
        if len(found) > 20:
            lines.append(f"... and {len(found) - 20} more")
        return "\n".join(lines)

    @staticmethod
    def _chunk_summary(summary: str, chunk: object) -> str:  # noqa: ANN001
        if chunk.total > 1:
            return f"{summary}\nCurrent document chunk: {chunk.index}/{chunk.total}"
        return summary
