"""Evidence map stage — relevance scan and document channel classification."""

from __future__ import annotations

import asyncio

from loguru import logger

from ..channel_contracts import (
    DocumentChannelClassification,
    RelevanceScanResult,
    merge_channel_classifications,
    parse_channel_classification,
)
from ..chunking import DEFAULT_INPUT_BUDGET_TOKENS, build_text_prompt_chunks, merge_evidence_maps
from ..contracts import RelevanceScanOutput, TrackDocument
from ..prompts import get_evidence_map_prompt
from ..providers import EvidenceModelTier, LangChainEvidenceProvider
from ...cross_lingual.format.segmenter import estimate_tokens

_DEFAULT_CHUNK_CONCURRENCY = 5


class RelevanceScanStage:
    def __init__(
        self,
        provider: LangChainEvidenceProvider,
        input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
    ):
        self._provider = provider
        self._input_budget_tokens = input_budget_tokens

    @staticmethod
    def _extract_classification(output: object) -> DocumentChannelClassification:
        """Extract a channel classification from a chunk LLM output.

        Uses ``getattr`` so that plain ``DocumentEvidenceMap`` objects (e.g.
        from older mocks that do not carry channel fields) gracefully fall
        back to ``UNKNOWN`` instead of raising ``AttributeError``.
        """
        return parse_channel_classification(
            getattr(output, "selected_channels", None),
            getattr(output, "confidence", None),
            getattr(output, "rationale", None),
            getattr(output, "supporting_block_ids", None),
        )

    def run(self, document: TrackDocument) -> RelevanceScanResult:
        overhead = estimate_tokens(
            get_evidence_map_prompt(
                document_id=document.document_id,
                track=document.track,
                text="",
            )
        )
        chunks = build_text_prompt_chunks(
            document.formatted_text,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=overhead,
        )
        outputs: list[RelevanceScanOutput] = []
        for chunk in chunks:
            chunk_note = f"\n\nCHUNK {chunk.index}/{chunk.total}\n"
            prompt = get_evidence_map_prompt(
                document_id=document.document_id,
                track=document.track,
                text=f"{chunk_note}{chunk.text}",
            )
            outputs.append(
                self._provider.invoke_structured(
                    prompt=prompt,
                    output_schema=RelevanceScanOutput,
                    tier=EvidenceModelTier.FAST,
                    stage="relevance_scan" if chunk.total == 1 else f"relevance_scan/{chunk.index}",
                    response_method="json_mode",
                )
            )
        merged_map = merge_evidence_maps(outputs)
        classifications = [self._extract_classification(o) for o in outputs]
        merged_cls = merge_channel_classifications(classifications)
        logger.debug(
            "Relevance scan: doc_id={}, track={}, relevant={}, disease={}, gene={}, variant={}, channels={}",
            document.document_id,
            document.track.value,
            merged_map.relevant,
            len(merged_map.disease_terms),
            len(merged_map.gene_terms),
            len(merged_map.variant_terms),
            [ch.value for ch in merged_cls.selected_channels],
        )
        return RelevanceScanResult(evidence_map=merged_map, channel_classification=merged_cls)

    async def run_async(self, document: TrackDocument) -> RelevanceScanResult:
        """Async version — runs chunk LLM calls concurrently with semaphore."""
        overhead = estimate_tokens(
            get_evidence_map_prompt(
                document_id=document.document_id,
                track=document.track,
                text="",
            )
        )
        chunks = build_text_prompt_chunks(
            document.formatted_text,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=overhead,
        )
        sem = asyncio.Semaphore(_DEFAULT_CHUNK_CONCURRENCY)

        async def _extract_chunk(chunk):  # noqa: ANN001
            chunk_note = f"\n\nCHUNK {chunk.index}/{chunk.total}\n"
            prompt = get_evidence_map_prompt(
                document_id=document.document_id,
                track=document.track,
                text=f"{chunk_note}{chunk.text}",
            )
            async with sem:
                return await self._provider.ainvoke_structured(
                    prompt=prompt,
                    output_schema=RelevanceScanOutput,
                    tier=EvidenceModelTier.FAST,
                    stage="relevance_scan" if chunk.total == 1 else f"relevance_scan/{chunk.index}",
                    response_method="json_mode",
                )

        results = await asyncio.gather(
            *[_extract_chunk(c) for c in chunks],
            return_exceptions=True,
        )
        outputs: list[RelevanceScanOutput] = []
        errors: list[BaseException] = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error("relevance_scan chunk {}/{} failed: {}", i + 1, len(chunks), result)
                errors.append(result)
                continue
            outputs.append(result)
        if not outputs and errors:
            raise RuntimeError(f"Relevance scan failed for all {len(chunks)} chunks: {errors[0]}")
        merged_map = merge_evidence_maps(outputs)
        classifications = [self._extract_classification(o) for o in outputs]
        merged_cls = merge_channel_classifications(classifications)
        logger.debug(
            "Relevance scan: doc_id={}, track={}, relevant={}, disease={}, gene={}, variant={}, channels={}",
            document.document_id,
            document.track.value,
            merged_map.relevant,
            len(merged_map.disease_terms),
            len(merged_map.gene_terms),
            len(merged_map.variant_terms),
            [ch.value for ch in merged_cls.selected_channels],
        )
        return RelevanceScanResult(evidence_map=merged_map, channel_classification=merged_cls)
