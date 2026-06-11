"""Catalog extraction stage — structured field extraction using the 10-category catalog.

Uses parallel catalog groups to reduce per-call output tokens: the 138-field
catalog is split into 2 balanced groups (~63 and ~75 fields) that are extracted
concurrently per chunk, cutting output token demand roughly in half.
"""
from __future__ import annotations

import asyncio

from loguru import logger

from ..catalog import CATALOG_GROUPS, EVIDENCE_FIELD_SPECS
from ..chunking import (
    STRONG_TIER_INPUT_BUDGET_TOKENS,
    build_block_prompt_chunks,
    merge_sparse_evidence_items,
)
from ..contracts import DocumentEvidenceMap, EvidenceItem, ExtractionTarget, Track, TrackDocument
from ..core import FieldValueNormalizer, RawSourceNormalizer
from ..prompts import get_catalog_extraction_prompt
from ..providers import EvidenceModelTier, LangChainEvidenceProvider
from ...cross_lingual.format.segmenter import estimate_tokens

_DEFAULT_CHUNK_CONCURRENCY = 5


class CatalogExtractionError(Exception):
    """Raised when all catalog extraction chunks fail."""


class CatalogExtractionStage:
    def __init__(
        self,
        provider: LangChainEvidenceProvider,
        input_budget_tokens: int = STRONG_TIER_INPUT_BUDGET_TOKENS,
    ):
        self._provider = provider
        self._input_budget_tokens = input_budget_tokens
        self._raw_source_normalizer = RawSourceNormalizer()
        # Use catalog groups for parallel extraction; fall back to full catalog
        self._catalog_groups: dict[str, tuple] = dict(CATALOG_GROUPS) if CATALOG_GROUPS else {"full": EVIDENCE_FIELD_SPECS}

    def _max_group_overhead(self, summary: str, extraction_target: ExtractionTarget | None) -> int:
        """Estimate the maximum prompt overhead across all catalog groups."""
        max_overhead = 0
        for catalog in self._catalog_groups.values():
            overhead = estimate_tokens(get_catalog_extraction_prompt(
                document_id="", track=Track.ORIGINAL, text="",
                catalog=catalog, evidence_map_summary=summary,
                extraction_target=extraction_target,
            ))
            max_overhead = max(max_overhead, overhead)
        return max_overhead

    def run(
        self,
        document: TrackDocument,
        evidence_map: DocumentEvidenceMap,
    ) -> list[EvidenceItem]:
        summary = self._summarize_map(evidence_map)
        overhead = self._max_group_overhead(summary, document.extraction_target)
        chunks = build_block_prompt_chunks(
            document,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=overhead,
        )
        extracted: list[EvidenceItem] = []
        for chunk in chunks:
            chunk_summary = self._chunk_summary(summary, chunk)
            for group_name, catalog in self._catalog_groups.items():
                prompt = get_catalog_extraction_prompt(
                    document_id=document.document_id,
                    track=document.track,
                    text=chunk.text,
                    catalog=catalog,
                    evidence_map_summary=chunk_summary,
                    extraction_target=document.extraction_target,
                )
                stage = self._stage_name(chunk, group_name)
                items = self._provider.invoke_structured(
                    prompt=prompt,
                    output_schema=list[EvidenceItem],
                    tier=EvidenceModelTier.STRONG,
                    stage=stage,
                )
                if isinstance(items, list):
                    normalized = self._raw_source_normalizer.normalize_items(items)
                    extracted.extend(FieldValueNormalizer.normalize_items(normalized))
        return merge_sparse_evidence_items(extracted)

    async def run_async(
        self,
        document: TrackDocument,
        evidence_map: DocumentEvidenceMap,
    ) -> list[EvidenceItem]:
        summary = self._summarize_map(evidence_map)
        overhead = self._max_group_overhead(summary, document.extraction_target)
        chunks = build_block_prompt_chunks(
            document,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=overhead,
        )
        sem = asyncio.Semaphore(_DEFAULT_CHUNK_CONCURRENCY)
        num_tasks = len(chunks) * len(self._catalog_groups)

        async def _extract_group(chunk, group_name: str, catalog: tuple):  # noqa: ANN001
            chunk_summary = self._chunk_summary(summary, chunk)
            prompt = get_catalog_extraction_prompt(
                document_id=document.document_id,
                track=document.track,
                text=chunk.text,
                catalog=catalog,
                evidence_map_summary=chunk_summary,
                extraction_target=document.extraction_target,
            )
            stage = self._stage_name(chunk, group_name)
            async with sem:
                return await self._provider.ainvoke_structured(
                    prompt=prompt,
                    output_schema=list[EvidenceItem],
                    tier=EvidenceModelTier.STRONG,
                    stage=stage,
                )

        # Build all tasks: chunk × group
        tasks = [
            _extract_group(chunk, group_name, catalog)
            for chunk in chunks
            for group_name, catalog in self._catalog_groups.items()
        ]
        logger.info(
            "catalog_extraction: {} chunks × {} groups = {} tasks",
            len(chunks), len(self._catalog_groups), num_tasks,
        )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        extracted: list[EvidenceItem] = []
        failed = 0
        last_error: BaseException | None = None
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error("catalog_extraction task {}/{} failed: {}", i + 1, num_tasks, result)
                failed += 1
                last_error = result
            elif isinstance(result, list):
                normalized = self._raw_source_normalizer.normalize_items(result)
                extracted.extend(FieldValueNormalizer.normalize_items(normalized))

        # Escalate based on failure rate
        if num_tasks:
            failure_rate = failed / num_tasks
            if failure_rate == 1.0:
                raise CatalogExtractionError(
                    f"All {num_tasks} extraction tasks failed, last error: {last_error}"
                ) from last_error
            if failure_rate > 0.5:
                logger.warning(
                    "catalog_extraction: {}/{} tasks failed, result is partial",
                    failed, num_tasks,
                )

        return merge_sparse_evidence_items(extracted)

    @staticmethod
    def _chunk_summary(summary: str, chunk: object) -> str:  # noqa: ANN001
        if chunk.total > 1:
            return f"{summary}\nCurrent document chunk: {chunk.index}/{chunk.total}"
        return summary

    @staticmethod
    def _stage_name(chunk: object, group_name: str) -> str:  # noqa: ANN001
        base = f"catalog_extraction/{group_name}"
        if chunk.total > 1:
            base = f"catalog_extraction/{group_name}/{chunk.index}"
        return base

    @staticmethod
    def _summarize_map(emap: DocumentEvidenceMap) -> str:
        parts: list[str] = []
        if emap.disease_terms:
            parts.append(f"Diseases: {', '.join(emap.disease_terms)}")
        if emap.gene_terms:
            parts.append(f"Genes: {', '.join(emap.gene_terms)}")
        if emap.variant_terms:
            parts.append(f"Variants: {', '.join(emap.variant_terms)}")
        if emap.case_references:
            parts.append(f"Cases: {', '.join(emap.case_references)}")
        return "; ".join(parts) if parts else "No specific entities identified"
