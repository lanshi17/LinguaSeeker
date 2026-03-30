from __future__ import annotations

import importlib
import typing

import src.domain.enums as domain_enums
import src.domain.models as domain_models


PACKAGE_IMPORTS = [
    "src.state",
    "src.agents",
    "src.agents.interaction",
    "src.agents.acquisition",
    "src.agents.parsing",
    "src.agents.extraction",
    "src.agents.arbitration",
    "src.agents.reasoning",
    "src.tools",
    "src.tools.db",
    "src.tools.file",
    "src.tools.external",
    "src.knowledge",
    "src.knowledge.prompts",
]

SCHEMA_EXPORTS = [
    "DocumentParsingArtifact",
    "DocumentParsingResult",
    "EvidenceOutput",
    "EvidenceStrengthClassification",
    "ExtractedEvidenceFields",
    "PipelineFiles",
    "PipelineResult",
    "GeneInfo",
    "TranscriptInfo",
    "ReferenceGenomeInfo",
    "ExperimentData",
    "DiseaseInfo",
    "SpeciesInfo",
    "PhenotypeInfo",
    "VariantInfo",
    "ControlInfo",
    "PedigreeInfo",
]


def test_wave1_packages_are_importable() -> None:
    for module_name in PACKAGE_IMPORTS:
        assert importlib.import_module(module_name) is not None


def test_schema_reexports_are_identity() -> None:
    import src.state.schemas as state_schemas

    for name in SCHEMA_EXPORTS:
        assert getattr(state_schemas, name) is getattr(domain_models, name)

    assert state_schemas.ProcessingState is domain_enums.ProcessingState


def test_state_package_exports_key_symbols() -> None:
    import src.state as state_pkg
    from src.state.global_state import SupervisorState

    assert state_pkg.SupervisorState is SupervisorState
    assert state_pkg.EvidenceOutput is domain_models.EvidenceOutput
    assert state_pkg.PipelineResult is domain_models.PipelineResult


def test_supervisor_state_is_valid_typed_dict() -> None:
    from src.state.global_state import SupervisorState

    expected_keys = [
        "request_id",
        "paper_task_id",
        "document_id",
        "celery_task_id",
        "source",
        "file_paths",
        "urls",
        "pmids",
        "current_node",
        "workflow_status",
        "processing_steps",
        "node_trace",
        "retries",
        "warnings",
        "errors",
        "requires_human_review",
        "parsing_result",
        "parser_backend",
        "markdown_content",
        "image_paths",
        "image_inputs",
        "sentence_alignments",
        "translated_markdown",
        "image_descriptions",
        "evidence_output",
        "extracted_fields",
        "arbitration_confidence",
        "final_evidence_strength",
        "acmg_result",
        "graph_context",
        "evidence_sources",
        "output_files",
        "final_result",
        "_inner_processing_state",
        "user_input",
        "user_response",
        "session_id",
        "question",
        "task_form",
        "interaction_ready",
        "goal",
        "disease",
        "country",
        "language",
    ]

    assert typing.is_typeddict(SupervisorState)
    assert list(SupervisorState.__annotations__) == expected_keys
    assert typing.get_type_hints(SupervisorState)
