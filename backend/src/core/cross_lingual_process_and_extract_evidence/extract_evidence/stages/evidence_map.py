"""Evidence map stage — relevance scan and structure discovery."""
from __future__ import annotations

import asyncio

from loguru import logger

from ..chunking import DEFAULT_INPUT_BUDGET_TOKENS, build_text_prompt_chunks, merge_evidence_maps
from ..contracts import DocumentEvidenceMap, TrackDocument
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

    def run(self, document: TrackDocument) -> DocumentEvidenceMap:
        overhead = estimate_tokens(get_evidence_map_prompt(
            document_id=document.document_id,
            track=document.track,
            text="",
        ))
        chunks = build_text_prompt_chunks(
            document.formatted_text,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=overhead,
        )
        maps: list[DocumentEvidenceMap] = []
        for chunk in chunks:
            chunk_note = f"\n\nCHUNK {chunk.index}/{chunk.total}\n"
            prompt = get_evidence_map_prompt(
                document_id=document.document_id,
                track=document.track,
                text=f"{chunk_note}{chunk.text}",
            )
            maps.append(self._provider.invoke_structured(
                prompt=prompt,
                output_schema=DocumentEvidenceMap,
                tier=EvidenceModelTier.FAST,
                stage="relevance_scan" if chunk.total == 1 else f"relevance_scan/{chunk.index}",
                response_method="json_mode",
            ))
        merged = merge_evidence_maps(maps)
        logger.debug(
            "Relevance scan: doc_id={}, track={}, relevant={}, disease={}, gene={}, variant={}",
            document.document_id, document.track.value,
            merged.relevant,
            len(merged.disease_terms), len(merged.gene_terms), len(merged.variant_terms),
        )
        return merged

    async def run_async(self, document: TrackDocument) -> DocumentEvidenceMap:
        """Async version — runs chunk LLM calls concurrently with semaphore."""
        overhead = estimate_tokens(get_evidence_map_prompt(
            document_id=document.document_id,
            track=document.track,
            text="",
        ))
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
            stage_name = "relevance_scan" if chunk.total == 1 else f"relevance_scan/{chunk.index}"
            try:
                async with sem:
                    result = await self._provider.ainvoke_structured(
                        prompt=prompt,
                        output_schema=DocumentEvidenceMap,
                        tier=EvidenceModelTier.FAST,
                        stage=stage_name,
                        response_method="json_mode",
                    )
                    if result is None:
                        raise RuntimeError(f"Stage {stage_name} returned None")
                    return result
            except Exception:
                import traceback
                logger.error("relevance_scan chunk {}/{} full traceback:\n{}", chunk.index, chunk.total, traceback.format_exc())
                raise

        results = await asyncio.gather(
            *[_extract_chunk(c) for c in chunks],
            return_exceptions=True,
        )
        maps: list[DocumentEvidenceMap] = []
        errors: list[BaseException] = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error("relevance_scan chunk {}/{} failed: {}", i + 1, len(chunks), result)
                errors.append(result)
                continue
            maps.append(result)
        if not maps and errors:
            raise RuntimeError(
                f"Relevance scan failed for all {len(chunks)} chunks: {errors[0]}"
            )
        merged = merge_evidence_maps(maps)
        logger.debug(
            "Relevance scan: doc_id={}, track={}, relevant={}, disease={}, gene={}, variant={}",
            document.document_id, document.track.value,
            merged.relevant,
            len(merged.disease_terms), len(merged.gene_terms), len(merged.variant_terms),
        )
        return merged
