"""Catalog extraction stage — structured field extraction over the 166-field A–K catalog.

Sends only the LLM-extractable groups to the per-document model:
  - high_signal (62 fields, A/B/D/E/J)
  - supporting  (81 fields, C/F/G/H/I)
The curation group (23 fields, K) is cross-paper GDV metadata and is filtered
out here; it is filled by the downstream gene-disease validity pipeline.
Groups run concurrently per chunk via asyncio.Semaphore (see _DEFAULT_CHUNK_CONCURRENCY).
"""

from __future__ import annotations

import asyncio

from loguru import logger

from ..domain.catalog import CATALOG_GROUPS
from ..domain.channel_contracts import DocumentChannelClassification
from ..domain.field_profile import build_profiled_catalog
from ..infrastructure.chunking import (
    STRONG_TIER_INPUT_BUDGET_TOKENS,
    build_block_prompt_chunks,
    merge_sparse_evidence_items,
)
from ..contracts import DocumentEvidenceMap, EvidenceItem, EvidenceStatus, ExtractionTarget, Track, TrackDocument
from ..core.normalization import FieldValueNormalizer, RawSourceNormalizer
from ..domain.field_eligibility import FieldEligibilityPolicy
from ..prompts import get_catalog_extraction_prompt, get_core_identity_retry_prompt
from ..providers import EvidenceModelTier, LangChainEvidenceProvider
from .block_selection import select_recall_first_blocks
from src.core.cross_lingual_translation.format.segmenter import estimate_tokens

_DEFAULT_CHUNK_CONCURRENCY = 5

# Core identity fields whose absence triggers a focused retry.
_CORE_IDENTITY_FIELD_IDS: frozenset[str] = frozenset(
    {
        "A.gene_symbol",
        "B.disease_diagnosis",
    }
)

# All fields accepted from the core identity retry (trigger + bonus).
_RETRY_ACCEPT_FIELD_IDS: frozenset[str] = frozenset(
    {
        "A.gene_symbol",
        "B.disease_diagnosis",
        "A.variant_hgvs_c",
        "A.variant_hgvs_p",
    }
)


class CatalogExtractionError(Exception):
    """Raised when all catalog extraction chunks fail."""


class CatalogExtractionStage:
    def __init__(
        self,
        provider: LangChainEvidenceProvider,
        input_budget_tokens: int = STRONG_TIER_INPUT_BUDGET_TOKENS,
        field_profile: frozenset[str] | None = None,
    ):
        self._provider = provider
        self._input_budget_tokens = input_budget_tokens
        self._raw_source_normalizer = RawSourceNormalizer()
        self._field_eligibility_policy = FieldEligibilityPolicy()
        # Curation (K) is cross-paper GDV metadata, filled outside this stage.
        if field_profile is not None:
            self._catalog_groups = build_profiled_catalog(field_profile)
        else:
            self._catalog_groups = {name: catalog for name, catalog in CATALOG_GROUPS.items() if name != "curation"}
        self.last_eligibility_decision = None

    def _max_group_overhead(self, summary: str, extraction_target: ExtractionTarget | None) -> int:
        """Estimate the maximum prompt overhead across all catalog groups."""
        max_overhead = 0
        for catalog in self._catalog_groups.values():
            overhead = estimate_tokens(
                get_catalog_extraction_prompt(
                    document_id="",
                    track=Track.ORIGINAL,
                    text="",
                    catalog=catalog,
                    evidence_map_summary=summary,
                    extraction_target=extraction_target,
                )
            )
            max_overhead = max(max_overhead, overhead)
        return max_overhead

    def run(
        self,
        document: TrackDocument,
        evidence_map: DocumentEvidenceMap,
        channel_classification: DocumentChannelClassification | None = None,
        graph_context: str = "",
    ) -> list[EvidenceItem]:
        summary = self._summarize_map(evidence_map)
        overhead = self._max_group_overhead(summary, document.extraction_target)
        chunks = build_block_prompt_chunks(
            document,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=overhead,
            block_indices=self._recall_first_block_indices(document),
        )
        catalog_groups = self._eligible_catalog_groups(
            document,
            evidence_map,
            chunks,
            channel_classification,
        )
        extracted: list[EvidenceItem] = []
        for chunk in chunks:
            chunk_summary = self._chunk_summary(summary, chunk)
            for group_name, catalog in catalog_groups.items():
                prompt = get_catalog_extraction_prompt(
                    document_id=document.document_id,
                    track=document.track,
                    text=chunk.text,
                    catalog=catalog,
                    evidence_map_summary=chunk_summary,
                    extraction_target=document.extraction_target,
                    channel_classification=channel_classification,
                    graph_context=graph_context,
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
        merged = merge_sparse_evidence_items(extracted)
        return self._maybe_retry_core_identity(document, merged)

    async def run_async(
        self,
        document: TrackDocument,
        evidence_map: DocumentEvidenceMap,
        channel_classification: DocumentChannelClassification | None = None,
        graph_context: str = "",
    ) -> list[EvidenceItem]:
        summary = self._summarize_map(evidence_map)
        overhead = self._max_group_overhead(summary, document.extraction_target)
        chunks = build_block_prompt_chunks(
            document,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=overhead,
            block_indices=self._recall_first_block_indices(document),
        )
        catalog_groups = self._eligible_catalog_groups(
            document,
            evidence_map,
            chunks,
            channel_classification,
        )
        sem = asyncio.Semaphore(_DEFAULT_CHUNK_CONCURRENCY)
        num_tasks = len(chunks) * len(catalog_groups)

        async def _extract_group(chunk, group_name: str, catalog: tuple):  # noqa: ANN001
            chunk_summary = self._chunk_summary(summary, chunk)
            prompt = get_catalog_extraction_prompt(
                document_id=document.document_id,
                track=document.track,
                text=chunk.text,
                catalog=catalog,
                evidence_map_summary=chunk_summary,
                extraction_target=document.extraction_target,
                channel_classification=channel_classification,
                graph_context=graph_context,
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
            for group_name, catalog in catalog_groups.items()
        ]
        logger.info(
            "catalog_extraction: {} chunks × {} groups = {} tasks",
            len(chunks),
            len(catalog_groups),
            num_tasks,
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
                    failed,
                    num_tasks,
                )

        merged = merge_sparse_evidence_items(extracted)
        return await self._maybe_retry_core_identity_async(document, merged)

    # ── Core identity retry ──────────────────────────────────────────

    @staticmethod
    def _missing_core_fields(items: list[EvidenceItem]) -> frozenset[str]:
        """Return the set of core identity field_ids that are not FOUND."""
        found_ids = frozenset(i.field_id for i in items if i.status == EvidenceStatus.FOUND)
        return frozenset(fid for fid in _CORE_IDENTITY_FIELD_IDS if fid not in found_ids)

    def _maybe_retry_core_identity(
        self,
        document: TrackDocument,
        items: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        """Run a focused retry if core identity fields are missing."""
        if document.extraction_target is None:
            return items
        missing = self._missing_core_fields(items)
        if not missing:
            return items
        return self._run_core_identity_retry(document, items, missing)

    async def _maybe_retry_core_identity_async(
        self,
        document: TrackDocument,
        items: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        """Async variant of core identity retry."""
        if document.extraction_target is None:
            return items
        missing = self._missing_core_fields(items)
        if not missing:
            return items
        return await self._run_core_identity_retry_async(document, items, missing)

    def _run_core_identity_retry(
        self,
        document: TrackDocument,
        existing: list[EvidenceItem],
        missing: frozenset[str],
    ) -> list[EvidenceItem]:
        """Execute one focused retry for core identity fields and merge."""
        logger.info(
            "core_identity_retry: missing {}, running focused extraction",
            ", ".join(sorted(missing)),
        )
        target = document.extraction_target
        assert target is not None  # caller guards
        block_indices = self._recall_first_block_indices(document)
        chunks = build_block_prompt_chunks(
            document,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=0,
            block_indices=block_indices,
        )
        if not chunks:
            return existing
        # Use the first chunk only — core identity fields should be in the richest block
        chunk = chunks[0]
        prompt = get_core_identity_retry_prompt(
            document_id=document.document_id,
            track=document.track,
            text=chunk.text,
            extraction_target=target,
        )
        try:
            items = self._provider.invoke_structured(
                prompt=prompt,
                output_schema=list[EvidenceItem],
                tier=EvidenceModelTier.STRONG,
                stage="catalog_extraction/core_identity_retry",
            )
        except Exception as exc:
            logger.warning("core_identity_retry failed: {}", exc)
            return existing
        if not isinstance(items, list):
            return existing
        normalized = self._raw_source_normalizer.normalize_items(items)
        normalized = FieldValueNormalizer.normalize_items(normalized)
        rescued = self._merge_retry_items(existing, normalized)
        if rescued:
            logger.info("core_identity_retry: rescued {}", ", ".join(rescued))
        return existing + [item for item in normalized if item.field_id in rescued]

    async def _run_core_identity_retry_async(
        self,
        document: TrackDocument,
        existing: list[EvidenceItem],
        missing: frozenset[str],
    ) -> list[EvidenceItem]:
        """Async variant of core identity retry."""
        logger.info(
            "core_identity_retry: missing {}, running focused extraction",
            ", ".join(sorted(missing)),
        )
        target = document.extraction_target
        assert target is not None
        block_indices = self._recall_first_block_indices(document)
        chunks = build_block_prompt_chunks(
            document,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=0,
            block_indices=block_indices,
        )
        if not chunks:
            return existing
        chunk = chunks[0]
        prompt = get_core_identity_retry_prompt(
            document_id=document.document_id,
            track=document.track,
            text=chunk.text,
            extraction_target=target,
        )
        try:
            items = await self._provider.ainvoke_structured(
                prompt=prompt,
                output_schema=list[EvidenceItem],
                tier=EvidenceModelTier.STRONG,
                stage="catalog_extraction/core_identity_retry",
            )
        except Exception as exc:
            logger.warning("core_identity_retry failed: {}", exc)
            return existing
        if not isinstance(items, list):
            return existing
        normalized = self._raw_source_normalizer.normalize_items(items)
        normalized = FieldValueNormalizer.normalize_items(normalized)
        rescued = self._merge_retry_items(existing, normalized)
        if rescued:
            logger.info("core_identity_retry: rescued {}", ", ".join(rescued))
        return existing + [item for item in normalized if item.field_id in rescued]

    def _merge_retry_items(
        self,
        existing: list[EvidenceItem],
        retry_items: list[EvidenceItem],
    ) -> set[str]:
        """Return the set of field_ids rescued by retry.

        A retry item is accepted only when:
        - Its field_id is one of the four retry-accepted fields.
        - Its status is FOUND.
        - No existing FOUND item has >= confidence for the same field_id.
        """
        existing_best: dict[str, float] = {}
        for item in existing:
            if item.status == EvidenceStatus.FOUND:
                cur = existing_best.get(item.field_id, -1.0)
                if item.confidence > cur:
                    existing_best[item.field_id] = item.confidence

        rescued: set[str] = set()
        for item in retry_items:
            if item.field_id not in _RETRY_ACCEPT_FIELD_IDS:
                continue
            if item.status != EvidenceStatus.FOUND:
                continue
            best = existing_best.get(item.field_id, -1.0)
            if item.confidence > best:
                rescued.add(item.field_id)
        return rescued

    def _eligible_catalog_groups(
        self,
        document: TrackDocument,
        evidence_map: DocumentEvidenceMap,
        chunks: list[object],
        channel_classification: DocumentChannelClassification | None = None,
    ) -> dict[str, tuple]:
        """Filter catalog groups to target/channel-eligible fields and skip empty groups.

        The field set is the intersection of the existing target/source
        eligibility (:meth:`FieldEligibilityPolicy.decide`) and the
        document-channel field matrix.  ``channel_classification is None``
        is permissive — only target/source eligibility applies.

        The eligibility decision is stored as :attr:`last_eligibility_decision`
        so the workflow can access the excluded field IDs after calling
        :meth:`run` or :meth:`run_async`.
        """
        selected_text = "\n\n".join(str(getattr(chunk, "text", "")) for chunk in chunks)
        decision = self._field_eligibility_policy.decide_with_channels(
            extraction_target=document.extraction_target,
            evidence_map=evidence_map,
            selected_text=selected_text,
            channel_classification=channel_classification,
        )
        self.last_eligibility_decision = decision
        return {
            group_name: eligible_catalog
            for group_name, catalog in self._catalog_groups.items()
            if (eligible_catalog := tuple(spec for spec in catalog if spec.field_id in decision.allowed_field_ids))
        }

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
    def _recall_first_block_indices(document: TrackDocument) -> tuple[int, ...] | None:
        if document.extraction_target is None:
            return None
        selected = select_recall_first_blocks(document)
        if not selected:
            return None
        return tuple(block.index for block in selected)

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
