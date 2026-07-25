"""Special evidence validator: filters unsafe special evidence records."""

from __future__ import annotations

from ..contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceRecord,
    TrackDocument,
)


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
        return [record for record in records if self._is_valid_record(record, valid_field_ids, document)]

    def _is_valid_record(
        self,
        record: SpecialEvidenceRecord,
        valid_field_ids: set[str],
        document: TrackDocument,
    ) -> bool:
        source = record.source or record.raw_source
        if source is None:
            return False
        if source.start_offset == source.end_offset and not self._source_is_traceable(source, document):
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
                block_text_parts.extend(item.strip() for item in block.list_items if item.strip())
            if source.text_snippet in "\n".join(block_text_parts):
                return True
        text = document.formatted_text
        if source.start_offset >= source.end_offset and len(source.text_snippet) < 8:
            return False
        if source.start_offset >= 0 and source.end_offset <= len(text):
            if text[source.start_offset : source.end_offset] == source.text_snippet:
                return True
        if len(source.text_snippet) < 8:
            return False
        return source.text_snippet in text
