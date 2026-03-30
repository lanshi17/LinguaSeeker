from __future__ import annotations

import logging
from typing import Any, Optional, cast

from src.state.global_state import SupervisorState

logger = logging.getLogger(__name__)


def _extract_gene_symbol(state: SupervisorState) -> Optional[str]:
    fields = state.get("extracted_fields")
    if fields and hasattr(fields, "gene") and fields.gene:
        return fields.gene.symbol
    evidence = state.get("evidence_output")
    if isinstance(evidence, dict):
        gene_info = evidence.get("gene")
        if isinstance(gene_info, dict):
            return gene_info.get("symbol")
    return None


def _extract_variant_hgvs(state: SupervisorState) -> Optional[str]:
    fields = state.get("extracted_fields")
    if fields and hasattr(fields, "variant") and fields.variant:
        return fields.variant.hgvs_c
    evidence = state.get("evidence_output")
    if isinstance(evidence, dict):
        variant_info = evidence.get("variant")
        if isinstance(variant_info, dict):
            return variant_info.get("hgvs_c")
    return None


def _extract_protein_change(state: SupervisorState) -> Optional[str]:
    fields = state.get("extracted_fields")
    if fields and hasattr(fields, "variant") and fields.variant:
        return fields.variant.hgvs_p
    evidence = state.get("evidence_output")
    if isinstance(evidence, dict):
        variant_info = evidence.get("variant")
        if isinstance(variant_info, dict):
            return variant_info.get("hgvs_p")
    return None


def _query_knowledge_graph_sync(
    gene: Optional[str], variant: Optional[str], protein: Optional[str]
) -> Optional[dict[str, Any]]:
    if not gene and not variant and not protein:
        return None

    try:
        from src.infrastructure.neo4j import get_neo4j_client

        client = get_neo4j_client()
    except Exception as e:
        logger.warning("Neo4j client unavailable, skipping knowledge graph query: %s", e)
        return None

    context: dict[str, Any] = {
        "gene_symbol": gene,
        "variant_hgvs_c": variant,
        "protein_change": protein,
        "variant_evidence": [],
        "gene_variants": [],
        "multi_doc_evidence": [],
    }

    try:
        if variant:
            context["variant_evidence"] = client.find_variant_evidence_graph(
                variant_hgvs_c=variant, variation_id=None
            )
    except Exception as e:
        logger.warning("find_variant_evidence_graph failed: %s", e)

    try:
        if gene:
            context["gene_variants"] = client.find_gene_related_variants(gene)
    except Exception as e:
        logger.warning("find_gene_related_variants failed: %s", e)

    try:
        if gene or variant or protein:
            context["multi_doc_evidence"] = client.find_multi_document_evidence(
                gene_symbol=gene, variant_hgvs_c=variant, protein_change=protein
            )
    except Exception as e:
        logger.warning("find_multi_document_evidence failed: %s", e)

    has_data = any(
        context.get(k) for k in ("variant_evidence", "gene_variants", "multi_doc_evidence")
    )
    return context if has_data else None


def _build_reasoning_summary(graph_context: dict[str, Any]) -> str:
    lines: list[str] = []

    gene = graph_context.get("gene_symbol")
    variant = graph_context.get("variant_hgvs_c")
    protein = graph_context.get("protein_change")

    header_parts = [p for p in [gene, variant, protein] if p]
    if header_parts:
        lines.append(f"Knowledge Graph Context for: {', '.join(header_parts)}")
        lines.append("")

    variant_ev = graph_context.get("variant_evidence", [])
    if variant_ev:
        lines.append(f"Variant Evidence ({len(variant_ev)} records):")
        for rec in variant_ev[:5]:
            lines.append(f"  - {rec}")
        if len(variant_ev) > 5:
            lines.append(f"  ... and {len(variant_ev) - 5} more")
        lines.append("")

    gene_vars = graph_context.get("gene_variants", [])
    if gene_vars:
        lines.append(f"Related Variants in Same Gene ({len(gene_vars)} records):")
        for rec in gene_vars[:5]:
            lines.append(f"  - {rec}")
        if len(gene_vars) > 5:
            lines.append(f"  ... and {len(gene_vars) - 5} more")
        lines.append("")

    multi_doc = graph_context.get("multi_doc_evidence", [])
    if multi_doc:
        lines.append(f"Multi-Document Evidence ({len(multi_doc)} records):")
        for rec in multi_doc[:5]:
            lines.append(f"  - {rec}")
        if len(multi_doc) > 5:
            lines.append(f"  ... and {len(multi_doc) - 5} more")

    return "\n".join(lines)


def run_reasoning_node(state: SupervisorState) -> SupervisorState:
    updated = dict(state)
    updated["current_node"] = "reasoning"

    gene = _extract_gene_symbol(state)
    variant = _extract_variant_hgvs(state)
    protein = _extract_protein_change(state)

    logger.info(
        "Reasoning node: gene=%s, variant=%s, protein=%s",
        gene,
        variant,
        protein,
    )

    graph_context = _query_knowledge_graph_sync(gene, variant, protein)

    if graph_context:
        graph_context["reasoning_summary"] = _build_reasoning_summary(graph_context)
        logger.info("Knowledge graph context retrieved successfully")
    else:
        logger.info("No knowledge graph context available")

    updated["graph_context"] = graph_context
    return cast(SupervisorState, cast(object, updated))
