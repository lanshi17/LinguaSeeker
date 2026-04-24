from __future__ import annotations

from typing import Any, cast

from src.domain.enums import ProcessingState


def test_db_tool_reexports_legacy_clients() -> None:
    from src.infrastructure.neo4j import Neo4jClient as LegacyNeo4jClient
    from src.infrastructure.neo4j import get_neo4j_client as legacy_get_neo4j_client
    from src.infrastructure.postgres import PostgresClient as LegacyPostgresClient
    from src.infrastructure.postgres import get_postgres_client as legacy_get_postgres_client
    from src.infrastructure.qdrant import QdrantManager as LegacyQdrantManager
    from src.infrastructure.qdrant import get_qdrant_manager as legacy_get_qdrant_manager
    from src.tools.db.neo4j_tool import Neo4jClient, get_neo4j_client
    from src.tools.db.postgres_tool import PostgresClient, get_postgres_client
    from src.tools.db.qdrant_tool import QdrantManager, get_qdrant_manager

    assert PostgresClient is LegacyPostgresClient
    assert get_postgres_client is legacy_get_postgres_client
    assert Neo4jClient is LegacyNeo4jClient
    assert get_neo4j_client is legacy_get_neo4j_client
    assert QdrantManager is LegacyQdrantManager
    assert get_qdrant_manager is legacy_get_qdrant_manager


def test_file_tool_reexports_parser_and_storage_helpers() -> None:
    from src.infrastructure.minio import MinIOClient as LegacyMinIOClient
    from src.infrastructure.minio import get_minio_client as legacy_get_minio_client
    from src.domain.agent.document_parsing import DocumentParsingAgent as LegacyDocumentParsingAgent
    from src.domain.agent.document_parsing import collect_parsing_assets as legacy_collect_assets
    from src.domain.agent.document_parsing import (
        get_document_parsing_agent as legacy_get_document_parsing_agent,
    )
    from src.domain.mineru.component import MinerUComponent as LegacyMinerUComponent
    from src.domain.mineru.component import run_paddleocr_fallback as legacy_paddleocr_fallback
    from src.tools.file.minio_tool import MinIOClient, get_minio_client
    from src.tools.file.pdf_parser import (
        DocumentParsingAgent,
        MinerUComponent,
        collect_parsing_assets,
    )
    from src.tools.file.pdf_parser import get_document_parsing_agent, run_paddleocr_fallback

    assert MinIOClient is LegacyMinIOClient
    assert get_minio_client is legacy_get_minio_client
    assert DocumentParsingAgent is LegacyDocumentParsingAgent
    assert get_document_parsing_agent is legacy_get_document_parsing_agent
    assert collect_parsing_assets is legacy_collect_assets
    assert MinerUComponent is LegacyMinerUComponent
    assert run_paddleocr_fallback is legacy_paddleocr_fallback


def test_clinvar_tool_reexports_legacy_clients_and_services() -> None:
    from src.domain.variant import VariationDataService as LegacyVariationDataService
    from src.domain.variant import get_variation_data_service as legacy_get_variation_data_service
    from src.domain.variant.clinvar_client import ClinVarClient as LegacyClinVarClient
    from src.domain.variant.clinvar_client import (
        ClinVarVariantSummary as LegacyClinVarVariantSummary,
    )
    from src.tools.external.clinvar_tool import ClinVarClient, ClinVarVariantSummary
    from src.tools.external.clinvar_tool import VariationDataService, get_variation_data_service

    assert ClinVarClient is LegacyClinVarClient
    assert ClinVarVariantSummary is LegacyClinVarVariantSummary
    assert VariationDataService is LegacyVariationDataService
    assert get_variation_data_service is legacy_get_variation_data_service


def test_translation_tool_delegates_to_evidence_agent(monkeypatch) -> None:
    from src.agents.parsing import translation_tool

    class FakeEvidenceAgent:
        def translate_markdown(self, state: dict[str, Any]) -> dict[str, Any]:
            state["translated_md"] = "translated body"
            state["translation_review"] = "review ok"
            return state

    monkeypatch.setattr(translation_tool, "EvidenceAgent", FakeEvidenceAgent)

    state = cast(
        ProcessingState,
        cast(object, {"markdown_content": "原文", "translated_md": ""}),
    )
    result = translation_tool.translate_markdown(state)

    assert result["translated_md"] == "translated body"
    assert result["translation_review"] == "review ok"
    assert "医学 Markdown 内容翻译为英文" in translation_tool.get_translation_prompt("示例")


def test_validator_tool_exposes_hgvs_correction_and_variation_service() -> None:
    from src.domain.variant import VariationDataService as LegacyVariationDataService
    from src.tools.external.clinvar_tool import VariationDataService as ClinvarVariationDataService
    from src.agents.extraction.validator_tool import VariationDataService, attempt_hgvs_correction

    corrected, restored = attempt_hgvs_correction(
        "Variant noted as NM_000059.4:c.7790G>A.",
        "Variant noted as NM_000059.4:c.7790G>A.",
    )

    assert corrected == "Variant noted as NM_000059.4:c.7790G>A."
    assert restored is True
    assert VariationDataService is LegacyVariationDataService
    assert ClinvarVariationDataService is LegacyVariationDataService
