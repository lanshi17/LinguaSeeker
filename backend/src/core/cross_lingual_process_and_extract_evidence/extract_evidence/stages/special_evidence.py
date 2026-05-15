"""Special evidence pass — functional, case-control, authority, contradiction evidence."""
from __future__ import annotations

from ..contracts import EvidenceItem, SpecialEvidenceRecord, TrackDocument
from ..prompts import get_special_evidence_prompt
from ..providers import EvidenceModelTier, LangChainEvidenceProvider


class SpecialEvidenceStage:
    def __init__(self, provider: LangChainEvidenceProvider):
        self._provider = provider

    def run(
        self,
        document: TrackDocument,
        current_items: list[EvidenceItem],
    ) -> list[SpecialEvidenceRecord]:
        summary = self._summarize_items(current_items)
        prompt = get_special_evidence_prompt(
            document_id=document.document_id,
            track=document.track,
            text=document.formatted_text,
            current_items_summary=summary,
        )
        records = self._provider.invoke_structured(
            prompt=prompt,
            output_schema=list[SpecialEvidenceRecord],
            tier=EvidenceModelTier.STRONG,
            stage="special_evidence",
        )
        return records if isinstance(records, list) else []

    @staticmethod
    def _summarize_items(items: list[EvidenceItem]) -> str:
        found = [i for i in items if i.status.value == "found"]
        if not found:
            return "No evidence items extracted yet"
        lines = [f"{i.field_id}: {i.value}" for i in found[:20]]
        if len(found) > 20:
            lines.append(f"... and {len(found) - 20} more")
        return "\n".join(lines)
