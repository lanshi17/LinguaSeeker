"""Special evidence pass — functional, case-control, authority, contradiction evidence."""
from __future__ import annotations

import asyncio

from loguru import logger
from pydantic import ValidationError

from ..chunking import (
    DEFAULT_INPUT_BUDGET_TOKENS,
    build_block_prompt_chunks,
    merge_special_evidence_records,
)
from ..contracts import EvidenceItem, SpecialEvidenceRecord, SpecialEvidenceResponse, TrackDocument
from ..core import RawSourceNormalizer, SpecialEvidenceValidator
from ..prompts import get_special_evidence_prompt
from ..providers import EvidenceModelTier, LangChainEvidenceProvider
from ...cross_lingual.format.segmenter import estimate_tokens

_DEFAULT_CHUNK_CONCURRENCY = 5


class SpecialEvidenceStage:
    def __init__(
        self,
        provider: LangChainEvidenceProvider,
        input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
    ):
        self._provider = provider
        self._input_budget_tokens = input_budget_tokens
        self._raw_source_normalizer = RawSourceNormalizer()
        self._validator = SpecialEvidenceValidator()

    def run(
        self,
        document: TrackDocument,
        current_items: list[EvidenceItem],
    ) -> list[SpecialEvidenceRecord]:
        summary = self._summarize_items(current_items)
        overhead = estimate_tokens(get_special_evidence_prompt(
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
        all_records: list[SpecialEvidenceRecord] = []
        for chunk in chunks:
            chunk_summary = summary
            if chunk.total > 1:
                chunk_summary = f"{summary}\nCurrent document chunk: {chunk.index}/{chunk.total}"
            prompt = get_special_evidence_prompt(
                document_id=document.document_id,
                track=document.track,
                text=chunk.text,
                current_items_summary=chunk_summary,
            )
            records = self._provider.invoke_structured(
                prompt=prompt,
                output_schema=SpecialEvidenceResponse,
                tier=EvidenceModelTier.STRONG,
                stage="special_evidence" if chunk.total == 1 else f"special_evidence/{chunk.index}",
                response_method="json_mode",
            )
            parsed = self._parse_records(records)
            parsed = self._raw_source_normalizer.normalize_special_records(parsed)
            all_records.extend(parsed)
        merged = merge_special_evidence_records(all_records)
        return self._validator.filter_records(merged, current_items, document)

    @staticmethod
    def _parse_records(records: object) -> list[SpecialEvidenceRecord]:
        if isinstance(records, SpecialEvidenceResponse):
            records = records.records
        elif isinstance(records, dict) and "records" in records:
            records = records["records"]
        if not isinstance(records, list):
            return []
        parsed: list[SpecialEvidenceRecord] = []
        for record in records:
            if isinstance(record, SpecialEvidenceRecord):
                parsed.append(record)
                continue
            if isinstance(record, dict):
                try:
                    parsed.append(SpecialEvidenceRecord(**record))
                except ValidationError:
                    continue
        return parsed

    async def run_async(
        self,
        document: TrackDocument,
        current_items: list[EvidenceItem],
    ) -> list[SpecialEvidenceRecord]:
        """Async version — runs chunk LLM calls concurrently with semaphore."""
        summary = self._summarize_items(current_items)
        overhead = estimate_tokens(get_special_evidence_prompt(
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
            chunk_summary = summary
            if chunk.total > 1:
                chunk_summary = f"{summary}\nCurrent document chunk: {chunk.index}/{chunk.total}"
            prompt = get_special_evidence_prompt(
                document_id=document.document_id,
                track=document.track,
                text=chunk.text,
                current_items_summary=chunk_summary,
            )
            async with sem:
                return await self._provider.ainvoke_structured(
                    prompt=prompt,
                    output_schema=SpecialEvidenceResponse,
                    tier=EvidenceModelTier.STRONG,
                    stage="special_evidence" if chunk.total == 1 else f"special_evidence/{chunk.index}",
                    response_method="json_mode",
                )

        results = await asyncio.gather(
            *[_extract_chunk(c) for c in chunks],
            return_exceptions=True,
        )
        all_records: list[SpecialEvidenceRecord] = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error("special_evidence chunk {}/{} failed: {}", i + 1, len(chunks), result)
                continue
            parsed = self._parse_records(result)
            parsed = self._raw_source_normalizer.normalize_special_records(parsed)
            all_records.extend(parsed)
        merged = merge_special_evidence_records(all_records)
        return self._validator.filter_records(merged, current_items, document)

    @staticmethod
    def _summarize_items(items: list[EvidenceItem]) -> str:
        found = [i for i in items if i.status.value == "found"]
        if not found:
            return "No evidence items extracted yet"
        lines = [f"{i.field_id}: {i.value}" for i in found[:20]]
        if len(found) > 20:
            lines.append(f"... and {len(found) - 20} more")
        return "\n".join(lines)
