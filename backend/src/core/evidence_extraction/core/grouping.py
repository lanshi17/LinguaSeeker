"""Group assignment for variant-centered evidence grouping."""

from __future__ import annotations

import re


from ..contracts import (
    EvidenceItem,
    SpecialEvidenceRecord,
    TrackDocument,
)

_MISSING_GROUP_VALUE = "__missing__"


def normalize_group_token(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", "", text)
    return text or _MISSING_GROUP_VALUE


def make_group_id(gene: object, variant: object) -> str:
    return f"gene={normalize_group_token(gene)}|variant={normalize_group_token(variant)}"


class GroupAssigner:
    """Assigns deterministic variant-centered group ids to evidence."""

    _VARIANT_FIELDS = {"A.variant_hgvs_c", "A.variant_hgvs_p", "F.tested_variant"}
    _GENE_FIELD = "A.gene_symbol"

    def assign(
        self,
        document: TrackDocument,
        items: list[EvidenceItem],
        special_records: list[SpecialEvidenceRecord],
    ) -> tuple[list[EvidenceItem], list[SpecialEvidenceRecord]]:
        group_ids = self._build_group_ids(document, items)
        grouped_items = [
            item.model_copy(update={"group_id": self._assign_item_group(item, group_ids, items, document)})
            for item in items
        ]
        grouped_special = [
            record.model_copy(update={"group_id": self._assign_special_group(record, group_ids, grouped_items)})
            for record in special_records
        ]
        return grouped_items, grouped_special

    def _build_group_ids(self, document: TrackDocument, items: list[EvidenceItem]) -> list[str]:
        gene_items = [item for item in items if item.field_id == self._GENE_FIELD and item.value is not None]
        variant_items = [item for item in items if item.field_id in self._VARIANT_FIELDS and item.value is not None]

        group_ids: list[str] = []
        for variant_item in variant_items:
            gene_value = self._resolve_gene_for_variant(variant_item, gene_items, document)
            group_id = make_group_id(gene_value, variant_item.value)
            if group_id not in group_ids:
                group_ids.append(group_id)

        for gene_item in gene_items:
            has_variant_group = any(
                group_id.startswith(f"gene={normalize_group_token(gene_item.value)}|")
                and not group_id.endswith(f"variant={_MISSING_GROUP_VALUE}")
                for group_id in group_ids
            )
            group_id = make_group_id(gene_item.value, "")
            if not has_variant_group and group_id not in group_ids:
                group_ids.append(group_id)

        return sorted(group_ids)

    def _resolve_gene_for_variant(
        self,
        variant_item: EvidenceItem,
        gene_items: list[EvidenceItem],
        document: TrackDocument,
    ) -> object:
        variant_block = self._block_index_for_item(variant_item)
        if gene_items:
            same_block = [item for item in gene_items if self._block_index_for_item(item) == variant_block]
            if same_block:
                return same_block[0].value
            nearest_gene = min(
                gene_items,
                key=lambda item: (
                    abs(self._block_index_for_item(item) - variant_block),
                    normalize_group_token(item.value),
                ),
            )
            if nearest_gene.value:
                return nearest_gene.value

        text = self._document_block_text(document, variant_block)
        for gene_item in gene_items:
            gene_text = str(gene_item.value or "").strip()
            if gene_text and gene_text in text:
                return gene_text
        inferred_gene = self._infer_gene_from_text(text)
        if inferred_gene:
            return inferred_gene
        return ""

    def _assign_item_group(
        self,
        item: EvidenceItem,
        group_ids: list[str],
        items: list[EvidenceItem],
        document: TrackDocument,
    ) -> str:
        if item.field_id == self._GENE_FIELD:
            variant = self._match_variant_for_gene(item, items)
            return make_group_id(item.value, variant)
        if item.field_id in self._VARIANT_FIELDS:
            gene = self._resolve_gene_for_variant(
                item, [candidate for candidate in items if candidate.field_id == self._GENE_FIELD], document
            )
            return make_group_id(gene, item.value)

        matched = self._match_group_by_text(item, group_ids)
        if matched is not None:
            return matched
        return self._nearest_group(item, group_ids, items)

    def _assign_special_group(
        self,
        record: SpecialEvidenceRecord,
        group_ids: list[str],
        grouped_items: list[EvidenceItem],
    ) -> str:
        matched = self._match_group_by_text(record, group_ids)
        if matched is not None:
            return matched
        return self._nearest_group_for_block(self._block_index_for_special_record(record), group_ids, grouped_items)

    def _match_variant_for_gene(self, gene_item: EvidenceItem, items: list[EvidenceItem]) -> object:
        same_block_variants = [
            item
            for item in items
            if item.field_id in self._VARIANT_FIELDS
            and self._block_index_for_item(item) == self._block_index_for_item(gene_item)
        ]
        if same_block_variants:
            return same_block_variants[0].value
        nearest_variants = [item for item in items if item.field_id in self._VARIANT_FIELDS]
        if not nearest_variants:
            return ""
        nearest = min(
            nearest_variants,
            key=lambda item: (
                abs(self._block_index_for_item(item) - self._block_index_for_item(gene_item)),
                normalize_group_token(item.value),
            ),
        )
        return nearest.value

    def _match_group_by_text(self, obj: EvidenceItem | SpecialEvidenceRecord, group_ids: list[str]) -> str | None:
        haystacks = self._text_haystacks(obj)
        matches: list[str] = []
        for group_id in group_ids:
            gene_token, variant_token = self._parse_group_id(group_id)
            for haystack in haystacks:
                gene_ok = gene_token == _MISSING_GROUP_VALUE or gene_token in haystack
                variant_ok = variant_token == _MISSING_GROUP_VALUE or variant_token in haystack
                if gene_ok and variant_ok:
                    matches.append(group_id)
                    break
        if not matches:
            return None
        return sorted(matches, key=self._group_sort_key)[0]

    def _nearest_group(
        self,
        item: EvidenceItem,
        group_ids: list[str],
        items: list[EvidenceItem],
    ) -> str:
        return self._nearest_group_for_block(self._block_index_for_item(item), group_ids, items)

    def _nearest_group_for_block(
        self,
        block_index: int,
        group_ids: list[str],
        items: list[EvidenceItem],
    ) -> str:
        if not group_ids:
            return make_group_id("", "")
        anchors: dict[str, list[int]] = {group_id: [] for group_id in group_ids}
        for candidate in items:
            candidate_group = candidate.group_id
            if candidate_group in anchors:
                anchors[candidate_group].append(self._block_index_for_item(candidate))

        ranked = []
        for group_id in group_ids:
            distances = anchors.get(group_id) or []
            ranked.append(
                (
                    min(abs(block - block_index) for block in distances) if distances else float("inf"),
                    self._group_sort_key(group_id),
                    group_id,
                )
            )
        ranked.sort()
        return ranked[0][2]

    def _group_sort_key(self, group_id: str) -> tuple[int, str]:
        gene_token, variant_token = self._parse_group_id(group_id)
        complete = 0 if gene_token != _MISSING_GROUP_VALUE and variant_token != _MISSING_GROUP_VALUE else 1
        return (complete, group_id)

    @staticmethod
    def _parse_group_id(group_id: str) -> tuple[str, str]:
        parts = dict(part.split("=", maxsplit=1) for part in group_id.split("|"))
        return parts.get("gene", _MISSING_GROUP_VALUE), parts.get("variant", _MISSING_GROUP_VALUE)

    @staticmethod
    def _block_index_for_item(item: EvidenceItem) -> int:
        source = item.raw_source or item.source
        if source is None:
            return -1
        return source.block_index

    @staticmethod
    def _block_index_for_special_record(record: SpecialEvidenceRecord) -> int:
        source = record.raw_source or record.source
        if source is None:
            return -1
        return source.block_index

    @staticmethod
    def _document_block_text(document: TrackDocument, block_index: int) -> str:
        if block_index < 0 or block_index >= len(document.blocks):
            return document.formatted_text
        block = document.blocks[block_index]
        parts = [*block.table_caption, *block.image_caption, *block.chart_caption]
        for value in (block.text, block.content, block.table_body, block.code_body):
            if value.strip():
                parts.append(value.strip())
        if block.list_items:
            parts.extend(item.strip() for item in block.list_items if item.strip())
        return "\n".join(parts)

    @staticmethod
    def _text_haystacks(obj: EvidenceItem | SpecialEvidenceRecord) -> list[str]:
        haystacks: list[str] = []
        if isinstance(obj, EvidenceItem):
            for value in (obj.value, obj.notes):
                if value is not None:
                    haystacks.append(normalize_group_token(value))
            source = obj.raw_source or obj.source
            if source is not None:
                haystacks.append(normalize_group_token(source.text_snippet))
        else:
            haystacks.append(normalize_group_token(obj.description))
            source = obj.raw_source or obj.source
            if source is not None:
                haystacks.append(normalize_group_token(source.text_snippet))
        return haystacks

    @staticmethod
    def _infer_gene_from_text(text: str) -> str:
        match = re.search(r"\b([A-Z][A-Z0-9-]{1,})\b", text)
        return match.group(1) if match else ""
