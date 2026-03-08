from __future__ import annotations


def test_src_main_reexports_root_app() -> None:
    from main import app as root_app
    from src.main import app

    assert app is root_app


def test_report_generator_exposes_legacy_report_surfaces() -> None:
    from src.domain.evidence.aggregator import AggregationReport as LegacyAggregationReport
    from src.domain.evidence.aggregator import EvidenceAggregationEngine as LegacyAggregationEngine
    from src.domain.evidence.dtos import AssociationReport as LegacyAssociationReport
    from src.domain.graph.association_service import (
        EntityAssociationAnalyzer as LegacyEntityAssociationAnalyzer,
    )
    from src.services.report_generator import AggregationReport, AssociationReport
    from src.services.report_generator import EvidenceAggregationEngine, EntityAssociationAnalyzer

    assert AggregationReport is LegacyAggregationReport
    assert EvidenceAggregationEngine is LegacyAggregationEngine
    assert AssociationReport is LegacyAssociationReport
    assert EntityAssociationAnalyzer is LegacyEntityAssociationAnalyzer


def test_stream_route_scaffold_is_importable() -> None:
    from src.api.routes.stream import router

    assert router.prefix == "/stream"
    assert "Stream" in router.tags


def test_system_prompt_bundle_matches_interaction_prompt() -> None:
    from src.agents.interaction.prompts import INTERACTION_SYSTEM_PROMPT
    from src.knowledge.prompts.loader import load_prompt_bundle

    bundle = load_prompt_bundle("system")

    assert bundle["interaction_system_prompt"] == INTERACTION_SYSTEM_PROMPT


def test_knowledge_ontologies_package_importable() -> None:
    import src.knowledge.ontologies as ontologies

    assert ontologies is not None
