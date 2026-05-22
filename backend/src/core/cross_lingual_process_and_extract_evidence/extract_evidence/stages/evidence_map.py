"""Evidence map stage — relevance scan and structure discovery."""
from __future__ import annotations

from ..contracts import DocumentEvidenceMap, TrackDocument
from ..prompts import get_evidence_map_prompt
from ..providers import EvidenceModelTier, LangChainEvidenceProvider


class EvidenceMapStage:
    def __init__(self, provider: LangChainEvidenceProvider):
        self._provider = provider

    def run(self, document: TrackDocument) -> DocumentEvidenceMap:
        prompt = get_evidence_map_prompt(
            document_id=document.document_id,
            track=document.track,
            text=document.formatted_text,
        )
        return self._provider.invoke_structured(
            prompt=prompt,
            output_schema=DocumentEvidenceMap,
            tier=EvidenceModelTier.FAST,
            stage="evidence_map",
            response_method="json_mode",
        )
