"""Deterministic source grounding and quality validation."""
from __future__ import annotations

import re

from loguru import logger

from .contracts import (
    ContentBlock,
    EvidenceChain,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    SpecialEvidenceRecord,
    TrackDocument,
)

# Re-export from focused sub-modules (backward compatibility).
# New code should import directly from _normalization, _grouping, _quality.
from ._grouping import GroupAssigner, make_group_id, normalize_group_token  # noqa: F401
from ._normalization import (  # noqa: F401
    EvidenceItemNormalizer,
    FieldValueNormalizer,
    RawSourceNormalizer,
)
from ._quality import IntraTrackConflictChecker, QualityValidator, TargetEntityGuard  # noqa: F401

_MAX_SNIPPET_MATCHES = 50
_ELLIPSIS_PATTERN = re.compile(r"\.\.\.|…")
_MULTISPACE_PATTERN = re.compile(r"\s+")
_MISSING_GROUP_VALUE = "__missing__"
_FULLWIDTH_TO_HALFWIDTH = {
    full: half for full, half in zip(range(0xFF01, 0xFF5F), range(0x21, 0x7F))
}
_AA3_TO_1 = {
    "Ala": "A",
    "Arg": "R",
    "Asn": "N",
    "Asp": "D",
    "Cys": "C",
    "Gln": "Q",
    "Glu": "E",
    "Gly": "G",
    "His": "H",
    "Ile": "I",
    "Leu": "L",
    "Lys": "K",
    "Met": "M",
    "Phe": "F",
    "Pro": "P",
    "Ser": "S",
    "Thr": "T",
    "Trp": "W",
    "Tyr": "Y",
    "Val": "V",
}
_AA1_TO_3 = {value: key for key, value in _AA3_TO_1.items()}
_PROTEIN_3LETTER_SUB_RE = re.compile(r"p\.([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|Ter|\*|X|stop)")
_PROTEIN_1LETTER_SUB_RE = re.compile(r"p\.([A-Z])(\d+)([A-Z]|\*)")
_PROTEIN_3LETTER_FS_TER_RE = re.compile(r"p\.([A-Z][a-z]{2})(\d+)fsTer(\d+)")
_PROTEIN_1LETTER_FS_STAR_RE = re.compile(r"p\.([A-Z])(\d+)fs\*(\d+)")
"""Fullwidth ASCII variants (U+FF01–U+FF5E) → halfwidth ASCII (U+0021–U+007E).

A 1:1 character mapping, so it preserves index_map correspondence in
``_normalize_text_with_index_map`` and is safe to apply to both sides of a
fuzzy substring match without risking false positives.
"""

def _normalize_for_grounding(text: str) -> str:
    """Normalize text for fuzzy grounding: collapse whitespace, lowercase."""
    text = _MULTISPACE_PATTERN.sub(" ", text).strip()
    return text.lower()


def _fuzzy_ellipsis_match(snippet: str, doc_text: str) -> bool:
    """Check if an ellipsis-containing snippet matches the document.

    Splits on ellipsis and verifies each fragment appears in the document
    in order.  Returns True if all fragments are found sequentially.
    """
    fragments = _ELLIPSIS_PATTERN.split(snippet)
    fragments = [f.strip() for f in fragments if f.strip()]
    if not fragments:
        return False

    normalized_doc = _normalize_for_grounding(doc_text)
    last_pos = -1
    for frag in fragments:
        norm_frag = _normalize_for_grounding(frag)
        if not norm_frag:
            logger.debug("Skipping empty fragment after normalization in fuzzy ellipsis match")
            continue
        pos = normalized_doc.find(norm_frag, last_pos + 1)
        if pos == -1:
            return False
        last_pos = pos
    return True
class SourceGrounder:
    """Validates and repairs source spans against the document."""

    def ground_items(
        self,
        document: TrackDocument,
        items: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        grounded: list[EvidenceItem] = []
        for item in items:
            source = self._raw_input_source(item)
            if item.status == EvidenceStatus.FOUND and source is None and item.field_id == "B.case_count":
                grounded.append(item.model_copy(update={"status": EvidenceStatus.TABLE_UNGROUNDED}))
                continue
            if item.status != EvidenceStatus.FOUND or source is None:
                grounded.append(item)
                continue
            grounded.append(self._ground_one(document, item, source))
        return grounded

    def ground_special_records(
        self,
        document: TrackDocument,
        records: list[SpecialEvidenceRecord],
    ) -> list[SpecialEvidenceRecord]:
        grounded: list[SpecialEvidenceRecord] = []
        for record in records:
            source = record.raw_source or record.source
            if source is None:
                grounded.append(record)
                continue
            grounded_source = self._ground_source(document, source)
            if grounded_source is None:
                grounded.append(record.model_copy(update={"source": None}))
                continue
            grounded.append(record.model_copy(update={"source": grounded_source, "raw_source": source}))
        return grounded

    def _ground_one(
        self,
        document: TrackDocument,
        item: EvidenceItem,
        source: SourceLocation,
    ) -> EvidenceItem:
        snippet = source.text_snippet

        if self._snippet_has_ellipsis(snippet):
            # Try fuzzy match: split on ellipsis, verify each fragment in order
            block = self._block_for_index(document, source.block_index)
            block_text = self._block_readable_text(block) if block is not None else ""
            if _fuzzy_ellipsis_match(snippet, block_text):
                logger.debug("Snippet matched via fuzzy grounding (ellipsis fragments found in order)")
            else:
                logger.warning("Snippet '{}' contains ellipsis and not found via fuzzy match, marking SOURCE_INVALID", snippet)
                return item.model_copy(update={
                    "status": EvidenceStatus.SOURCE_INVALID,
                    "raw_source": source,
                    "source": None,
                    "assigned_acmg_codes": [],
                    "assigned_clingen_modules": [],
                })


        grounded_source = self._ground_source(document, source, item.field_id)
        if grounded_source is None:
            block = self._block_for_index(document, source.block_index)
            mapped_type = self._map_block_type(block.type) if block is not None else source.block_type
            if mapped_type == "table":
                logger.warning("Snippet '{}' not found in table source, marking TABLE_UNGROUNDED", snippet)
                return item.model_copy(update={
                    "status": EvidenceStatus.TABLE_UNGROUNDED,
                    "raw_source": source,
                    "source": None,
                    "assigned_acmg_codes": [],
                    "assigned_clingen_modules": [],
                })
            if mapped_type in {"image", "figure"}:
                logger.warning("Snippet '{}' not found in document image/table source, marking OCR_GAP", snippet)
                return item.model_copy(update={
                    "status": EvidenceStatus.OCR_GAP,
                    "raw_source": source,
                    "source": None,
                    "assigned_acmg_codes": [],
                    "assigned_clingen_modules": [],
                })
            logger.warning("Snippet '{}' not found in document, marking SOURCE_INVALID", snippet)
            return item.model_copy(update={
                "status": EvidenceStatus.SOURCE_INVALID,
                "raw_source": source,
                "source": None,
                "assigned_acmg_codes": [],
                "assigned_clingen_modules": [],
            })

        return item.model_copy(update={"source": grounded_source, "raw_source": source})

    def _ground_source(self, document: TrackDocument, source: SourceLocation, field_id: str = "") -> SourceLocation | None:
        block = self._block_for_index(document, source.block_index)
        if block is not None:
            block_text = self._block_readable_text(block)
            if source.text_snippet and source.text_snippet in block_text:
                return self._build_source_from_text(document, source, source.text_snippet, block_index=source.block_index, block=block)

        if self._is_exact_match(document, source):
            block_match = self._find_block_for_offsets(document, source.start_offset, source.end_offset)
            if block_match is None:
                return source.model_copy(update={"block_index": -1, "bbox": [], "source_precision": SourcePrecision.EXACT})
            block_index, matched_block = block_match
            return source.model_copy(update={
                "block_index": block_index,
                "bbox": matched_block.bbox,
                "block_type": self._map_block_type(matched_block.type),
                "source_precision": SourcePrecision.EXACT,
            })

        corrected = self._search_snippet(document, source, source.text_snippet, field_id)
        if corrected is None:
            return None
        if len(corrected) > 1:
            logger.info("Snippet '{}' found {} times, marking ambiguous", source.text_snippet, len(corrected))
            corrected_source = corrected[0].model_copy(update={"source_precision": SourcePrecision.AMBIGUOUS})
        else:
            corrected_source = corrected[0].model_copy(update={"source_precision": SourcePrecision.CORRECTED})

        block_match = self._find_block_for_offsets(document, corrected_source.start_offset, corrected_source.end_offset)
        if block_match is None:
            return corrected_source.model_copy(update={"block_index": -1, "bbox": []})
        block_index, matched_block = block_match
        return corrected_source.model_copy(update={
            "block_index": block_index,
            "bbox": matched_block.bbox,
            "block_type": self._map_block_type(matched_block.type),
        })

    @staticmethod
    def _raw_input_source(item: EvidenceItem) -> SourceLocation | None:
        return item.raw_source or item.source

    @staticmethod
    def _block_for_index(document: TrackDocument, block_index: int) -> ContentBlock | None:
        if block_index < 0 or block_index >= len(document.blocks):
            return None
        return document.blocks[block_index]

    @staticmethod
    def _block_readable_text(block: ContentBlock) -> str:
        parts = [*block.table_caption, *block.image_caption, *block.chart_caption]
        for value in (block.text, block.content, block.table_body, block.code_body):
            if value.strip():
                parts.append(value.strip())
        if block.list_items:
            parts.extend(item.strip() for item in block.list_items if item.strip())
        return "\n".join(parts).strip()

    # Class-level constant — immutable, safe to share across instances/subclasses.
    _KNOWN_CONTEXT_TYPES = frozenset({
        "text", "table", "figure", "supplementary", "caption",
        "abstract", "introduction", "methods", "results", "discussion",
        "conclusion", "background",
    })

    @staticmethod
    def _map_block_type(block_type: str) -> str:
        mapping = {"chart": "figure", "image": "figure", "table": "table"}
        mapped = mapping.get(block_type, block_type)
        return mapped if mapped in SourceGrounder._KNOWN_CONTEXT_TYPES else "text"

    def _find_block_for_offsets(
        self,
        document: TrackDocument,
        start: int,
        end: int,
    ) -> tuple[int, ContentBlock] | None:
        if not document.blocks:
            return None
        for index, block in enumerate(document.blocks):
            block_text = self._block_readable_text(block)
            if not block_text:
                continue
            pos = document.formatted_text.find(block_text)
            if pos == -1:
                continue
            block_end = pos + len(block_text)
            if pos <= start and end <= block_end:
                return index, block
        return None

    def _build_source_from_text(
        self,
        document: TrackDocument,
        source: SourceLocation,
        text_snippet: str,
        block_index: int,
        block: ContentBlock,
    ) -> SourceLocation | None:
        start = document.formatted_text.find(text_snippet)
        if start >= 0:
            end = start + len(text_snippet)
            span = self._find_span(document.page_spans, start, end)
            if span is None:
                return None
            return SourceLocation(
                span_id=span.span_id,
                page=span.page,
                start_offset=start,
                end_offset=end,
                context_type=source.context_type,
                context_ref=source.context_ref,
                text_snippet=text_snippet,
                block_index=block_index,
                bbox=block.bbox,
                block_type=self._map_block_type(block.type),
                source_precision=SourcePrecision.EXACT,
            )

        block_text = self._block_readable_text(block)
        snippet_offset = block_text.find(text_snippet)
        span = self._find_span(document.page_spans, 0, len(document.formatted_text))
        if span is None:
            span = PageSpan(
                span_id=f"{document.track.value}-p{block.page_idx + 1}",
                page=block.page_idx + 1,
                start_offset=0,
                end_offset=max(len(document.formatted_text), 0),
            )
        return SourceLocation(
            span_id=span.span_id,
            page=span.page,
            start_offset=span.start_offset + max(snippet_offset, 0),
            end_offset=span.start_offset + max(snippet_offset, 0) + len(text_snippet),
            context_type=source.context_type,
            context_ref=source.context_ref,
            text_snippet=text_snippet,
            block_index=block_index,
            bbox=block.bbox,
            block_type=self._map_block_type(block.type),
            source_precision=SourcePrecision.EXACT,
        )

    def _is_exact_match(self, document: TrackDocument, source: SourceLocation) -> bool:
        text = document.formatted_text
        start = source.start_offset
        end = source.end_offset

        if start < 0 or end > len(text):
            return False

        actual = text[start:end]
        return actual == source.text_snippet

    def _search_snippet(
        self,
        document: TrackDocument,
        source: SourceLocation,
        snippet: str,
        field_id: str,
    ) -> list[SourceLocation] | None:
        text = document.formatted_text
        spans = document.page_spans
        direct_results = self._find_snippet_occurrences(text, spans, snippet, source)
        if direct_results:
            return direct_results

        normalized_snippet = self._normalize_snippet_for_search(snippet)
        if normalized_snippet:
            # Run even when the snippet itself is unchanged: the document
            # text may still differ (fullwidth/halfwidth, case) and only
            # become matchable after both sides are normalized.
            normalized_results = self._find_normalized_occurrences(text, spans, normalized_snippet, source)
            if normalized_results:
                return normalized_results

        for alias in self._grounding_aliases(field_id, snippet):
            alias_results = self._find_snippet_occurrences(text, spans, alias, source)
            if alias_results:
                return alias_results
            normalized_alias = self._normalize_snippet_for_search(alias)
            if not normalized_alias:
                continue
            normalized_alias_results = self._find_normalized_occurrences(text, spans, normalized_alias, source)
            if normalized_alias_results:
                return normalized_alias_results

        return None

    @classmethod
    def _grounding_aliases(cls, field_id: str, snippet: str) -> list[str]:
        """Return strict source-search aliases for known notation drift."""
        if field_id != "A.variant_hgvs_p":
            return []
        aliases: list[str] = []

        def _add(value: str) -> None:
            value = value.strip()
            if value and value != snippet and value not in aliases:
                aliases.append(value)

        compact_parentheses = re.sub(r"\s*([()])\s*", r"\1", snippet)
        _add(compact_parentheses)
        if compact_parentheses.startswith("p."):
            _add(compact_parentheses[2:])

        for source_text in (snippet, compact_parentheses):
            converted = cls._protein_3letter_to_1letter(source_text)
            if converted is not None:
                _add(converted)
                if converted.startswith("p."):
                    _add(converted[2:])
            expanded = cls._protein_1letter_to_3letter(source_text)
            if expanded is not None:
                _add(expanded)

        return aliases

    @staticmethod
    def _protein_3letter_to_1letter(value: str) -> str | None:
        fs_match = _PROTEIN_3LETTER_FS_TER_RE.search(value)
        if fs_match is not None:
            ref = _AA3_TO_1.get(fs_match.group(1))
            if ref is None:
                return None
            return f"p.{ref}{fs_match.group(2)}fs*{fs_match.group(3)}"

        match = _PROTEIN_3LETTER_SUB_RE.search(value)
        if match is None:
            return None
        ref = _AA3_TO_1.get(match.group(1))
        if ref is None:
            return None
        alt_text = match.group(3)
        if alt_text in {"Ter", "*", "X", "stop"}:
            alt = "*"
        else:
            alt = _AA3_TO_1.get(alt_text)
        if alt is None:
            return None
        return f"p.{ref}{match.group(2)}{alt}"

    @staticmethod
    def _protein_1letter_to_3letter(value: str) -> str | None:
        fs_match = _PROTEIN_1LETTER_FS_STAR_RE.search(value)
        if fs_match is not None:
            ref = _AA1_TO_3.get(fs_match.group(1))
            if ref is None:
                return None
            return f"p.{ref}{fs_match.group(2)}fsTer{fs_match.group(3)}"

        match = _PROTEIN_1LETTER_SUB_RE.search(value)
        if match is None:
            return None
        ref = _AA1_TO_3.get(match.group(1))
        if ref is None:
            return None
        alt_text = match.group(3)
        alt = "Ter" if alt_text == "*" else _AA1_TO_3.get(alt_text)
        if alt is None:
            return None
        return f"p.{ref}{match.group(2)}{alt}"

    @staticmethod
    def _snippet_has_ellipsis(snippet: str) -> bool:
        return bool(_ELLIPSIS_PATTERN.search(snippet))

    def _find_snippet_occurrences(
        self,
        text: str,
        spans: list[PageSpan],
        snippet: str,
        source: SourceLocation,
    ) -> list[SourceLocation]:
        results: list[SourceLocation] = []

        idx = 0
        while True:
            if len(results) >= _MAX_SNIPPET_MATCHES:
                logger.warning("Snippet '{}' found >{} times, truncating", snippet, _MAX_SNIPPET_MATCHES)
                break
            pos = text.find(snippet, idx)
            if pos == -1:
                break
            end_pos = pos + len(snippet)
            span = self._find_span(spans, pos, end_pos)
            if span:
                results.append(SourceLocation(
                    span_id=span.span_id,
                    page=span.page,
                    start_offset=pos,
                    end_offset=end_pos,
                    context_type=source.context_type,
                    context_ref=source.context_ref,
                    text_snippet=snippet,
                    block_index=source.block_index,
                    bbox=source.bbox,
                    block_type=source.block_type,
                    source_precision=SourcePrecision.EXACT,
                ))
            else:
                # Fallback: snippet is in the text but no page span covers it.
                # Create a grounded SourceLocation with best-effort metadata so
                # B8 items (block_index=-1, sparse page_spans) are not silently
                # dropped as SOURCE_INVALID.
                results.append(SourceLocation(
                    span_id=f"grounded-{pos}",
                    page=1,
                    start_offset=pos,
                    end_offset=end_pos,
                    context_type=source.context_type,
                    context_ref=source.context_ref,
                    text_snippet=snippet,
                    block_index=-1,
                    bbox=[],
                    block_type="text",
                    source_precision=SourcePrecision.CORRECTED,
                ))
            idx = pos + 1

        return results

    def _find_normalized_occurrences(
        self,
        text: str,
        spans: list[PageSpan],
        normalized_snippet: str,
        source: SourceLocation,
    ) -> list[SourceLocation]:
        normalized_text, index_map = self._normalize_text_with_index_map(text)
        results: list[SourceLocation] = []
        idx = 0
        while True:
            if len(results) >= _MAX_SNIPPET_MATCHES:
                logger.warning("Normalized snippet '{}' found >{} times, truncating", normalized_snippet, _MAX_SNIPPET_MATCHES)
                break
            pos = normalized_text.find(normalized_snippet, idx)
            if pos == -1:
                break
            end_pos = pos + len(normalized_snippet)
            actual_start = index_map[pos]
            actual_end = index_map[end_pos - 1] + 1
            span = self._find_span(spans, actual_start, actual_end)
            if span:
                results.append(SourceLocation(
                    span_id=span.span_id,
                    page=span.page,
                    start_offset=actual_start,
                    end_offset=actual_end,
                    context_type=source.context_type,
                    context_ref=source.context_ref,
                    text_snippet=text[actual_start:actual_end],
                    block_index=source.block_index,
                    bbox=source.bbox,
                    block_type=source.block_type,
                    source_precision=SourcePrecision.EXACT,
                ))
            else:
                # Fallback: normalized snippet found but no page span covers it.
                results.append(SourceLocation(
                    span_id=f"grounded-{actual_start}",
                    page=1,
                    start_offset=actual_start,
                    end_offset=actual_end,
                    context_type=source.context_type,
                    context_ref=source.context_ref,
                    text_snippet=text[actual_start:actual_end],
                    block_index=-1,
                    bbox=[],
                    block_type="text",
                    source_precision=SourcePrecision.CORRECTED,
                ))
            idx = pos + 1
        return results

    @staticmethod
    def _normalize_snippet_for_search(snippet: str) -> str:
        value = _ELLIPSIS_PATTERN.sub("", snippet)
        value = value.replace("[REDACTED]", "")
        value = value.replace("...", "")
        value = value.replace("（ ）", "")
        value = value.replace("( )", "")
        # Mirror _normalize_text_with_index_map exactly: keep a space only
        # when both neighbours are ASCII (Latin word boundaries) and drop
        # spaces adjacent to CJK (OCR artefacts).  Apply the same
        # fullwidth→halfwidth + lowercase mapping per kept character so the
        # snippet and document normalisations stay byte-consistent.
        chars: list[str] = []
        previous_kept = ""
        for index, char in enumerate(value):
            if char.isspace():
                if (
                    previous_kept
                    and previous_kept.isascii()
                    and index + 1 < len(value)
                    and value[index + 1].isascii()
                ):
                    if chars and chars[-1] != " ":
                        chars.append(" ")
                        previous_kept = " "
                continue
            mapped = chr(_FULLWIDTH_TO_HALFWIDTH.get(ord(char), ord(char))).lower()
            chars.append(mapped)
            previous_kept = mapped
        return "".join(chars)

    @staticmethod
    def _normalize_text_with_index_map(text: str) -> tuple[str, list[int]]:
        chars: list[str] = []
        index_map: list[int] = []
        previous_kept = ""
        for index, char in enumerate(text):
            if char.isspace():
                if previous_kept and previous_kept.isascii() and index + 1 < len(text) and text[index + 1].isascii():
                    if chars and chars[-1] != " ":
                        chars.append(" ")
                        index_map.append(index)
                        previous_kept = " "
                continue
            mapped = chr(_FULLWIDTH_TO_HALFWIDTH.get(ord(char), ord(char))).lower()
            chars.append(mapped)
            index_map.append(index)
            previous_kept = mapped
        return "".join(chars), index_map

    def _find_span(
        self,
        spans: list[PageSpan],
        start: int,
        end: int,
    ) -> PageSpan | None:
        for span in spans:
            if span.start_offset <= start and end <= span.end_offset:
                return span
        return None
class EvidenceChainBuilder:
    """Builds variant-centered identity chains from grounded grouped evidence."""

    def build(
        self,
        items: list[EvidenceItem],
        special_records: list[SpecialEvidenceRecord],
    ) -> list[EvidenceChain]:
        grouped_items: dict[str, list[EvidenceItem]] = {}
        for item in items:
            if not self._is_valid_grounded(item):
                continue
            group_id = item.group_id
            if not group_id:
                continue
            grouped_items.setdefault(group_id, []).append(item)

        chains: list[EvidenceChain] = []
        for group_id, group_items in grouped_items.items():
            by_field: dict[str, list[EvidenceItem]] = {}
            for item in group_items:
                by_field.setdefault(item.field_id, []).append(item)

            gene = self._first_value(by_field, "A.gene_symbol")
            disease = self._first_value(by_field, "B.disease_diagnosis")
            variant = self._first_value(by_field, "A.variant_hgvs_c") or self._first_value(by_field, "A.variant_hgvs_p")

            core_count = sum(1 for value in (gene, disease, variant) if value is not None)
            if core_count == 0:
                continue
            if core_count == 3:
                chain_level = "full"
            elif core_count == 2:
                chain_level = "partial"
            else:
                chain_level = "singleton"

            case_ids = sorted({
                str(item.value)
                for item in by_field.get("B.case_id", [])
                if item.value is not None
            })
            special_indices = [
                index for index, record in enumerate(special_records)
                if record.group_id == group_id
            ]
            contradictions = [
                record.description
                for record in special_records
                if record.group_id == group_id and record.record_type == "contradiction"
            ]

            chains.append(EvidenceChain(
                chain_id=group_id,
                chain_level=chain_level,
                gene_text=str(gene.value) if gene is not None and gene.value is not None else "",
                disease_text=str(disease.value) if disease is not None and disease.value is not None else "",
                variant_text=str(variant.value) if variant is not None and variant.value is not None else "",
                case_ids=case_ids,
                special_evidence_ids=[f"special-{index}" for index in special_indices],
                evidence_field_ids=sorted({item.field_id for item in group_items}),
                contradictions=contradictions,
            ))
        return sorted(chains, key=lambda chain: chain.chain_id)

    @staticmethod
    def _is_valid_grounded(item: EvidenceItem) -> bool:
        return (
            item.status == EvidenceStatus.FOUND
            and item.value is not None
            and item.source is not None
            and item.source.source_precision != SourcePrecision.AMBIGUOUS
        )

    @staticmethod
    def _first_value(by_field: dict[str, list[EvidenceItem]], field_id: str) -> EvidenceItem | None:
        values = by_field.get(field_id, [])
        return values[0] if values else None
class SpecialEvidenceValidator:
    """Filters special evidence records that are not safe to consume."""

    def filter_records(
        self,
        records: list[SpecialEvidenceRecord],
        current_items: list[EvidenceItem],
        document: TrackDocument,
    ) -> list[SpecialEvidenceRecord]:
        valid_field_ids = {
            item.field_id
            for item in current_items
            if item.status == EvidenceStatus.FOUND and (item.source is not None or item.raw_source is not None)
        }
        return [
            record for record in records
            if self._is_valid_record(record, valid_field_ids, document)
        ]

    def _is_valid_record(
        self,
        record: SpecialEvidenceRecord,
        valid_field_ids: set[str],
        document: TrackDocument,
    ) -> bool:
        source = record.source or record.raw_source
        if source is None:
            return False
        if (
            source.start_offset == source.end_offset
            and not self._source_is_traceable(source, document)
        ):
            return False
        if not self._source_is_traceable(source, document):
            return False
        if any(field_id not in valid_field_ids for field_id in record.evidence_field_ids):
            return False
        if record.record_type == "case_control":
            combined_text = f"{record.description} {source.text_snippet}"
            if "[REDACTED]" in combined_text:
                return False
        return True

    @staticmethod
    def _source_is_traceable(source: SourceLocation, document: TrackDocument) -> bool:
        if 0 <= source.block_index < len(document.blocks):
            block = document.blocks[source.block_index]
            block_text_parts = [*block.table_caption, *block.image_caption, *block.chart_caption]
            for value in (block.text, block.content, block.table_body, block.code_body):
                if value.strip():
                    block_text_parts.append(value.strip())
            if block.list_items:
                block_text_parts.extend(
                    item.strip() for item in block.list_items if item.strip()
                )
            if source.text_snippet in "\n".join(block_text_parts):
                return True
        text = document.formatted_text
        if source.start_offset >= source.end_offset and len(source.text_snippet) < 8:
            return False
        if source.start_offset >= 0 and source.end_offset <= len(text):
            if text[source.start_offset:source.end_offset] == source.text_snippet:
                return True
        if len(source.text_snippet) < 8:
            return False
        return source.text_snippet in text
