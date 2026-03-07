from __future__ import annotations

from typing import Any, Optional, TypedDict

from src.domain.enums import ProcessingState
from src.domain.models import (
    EvidenceOutput,
    EvidenceStrengthClassification,
    ExtractedEvidenceFields,
    PipelineFiles,
)


class SupervisorState(TypedDict):
    request_id: str
    paper_task_id: int
    document_id: int
    celery_task_id: str
    source: str
    file_paths: list[str]
    urls: list[str]
    pmids: list[str]
    current_node: str
    workflow_status: str
    processing_steps: dict[str, dict[str, Any]]
    node_trace: dict[str, Any]
    retries: dict[str, int]
    warnings: list[str]
    errors: list[str]
    requires_human_review: bool
    parsing_result: Optional[dict[str, Any]]
    parser_backend: Optional[str]
    markdown_content: Optional[str]
    image_paths: list[str]
    sentence_alignments: Optional[list[dict[str, Any]]]
    translated_markdown: Optional[str]
    image_descriptions: Optional[str]
    evidence_output: Optional[EvidenceOutput]
    extracted_fields: Optional[ExtractedEvidenceFields]
    arbitration_confidence: Optional[float]
    final_evidence_strength: Optional[str]
    acmg_result: Optional[EvidenceStrengthClassification]
    evidence_sources: list[dict[str, Any]]
    output_files: Optional[PipelineFiles]
    final_result: Optional[dict[str, Any]]
    _inner_processing_state: Optional[ProcessingState]


__all__ = ["SupervisorState"]
