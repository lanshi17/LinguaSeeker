"""Deterministic evidence support verification."""
from __future__ import annotations

import re

from .contracts import EvidenceVerificationInput, EvidenceVerificationResult, RelationshipLabel


_SPACE_RE = re.compile(r"\s+")
_CAUSAL_TERMS = (
    "cause",
    "causes",
    "caused by",
    "causal",
    "disease-causing",
    "pathogenic variant",
    "pathogenic variants",
    "biallelic",
    "loss-of-function",
    "deficiency",
)
_DIRECT_ASSOCIATION_TERMS = (
    "associated",
    "association",
    "linked",
    "linkage",
)
_SUSCEPTIBILITY_TERMS = (
    "risk",
    "susceptibility",
    "susceptible",
    "predispos",
)
_HEDGED_INFERENCE_TERMS = (
    "suggest",
    "suggests",
    "suggested",
    "may contribute",
    "may be involved",
    "may play a role",
    "may be due",
    "might be due",
    "could be due",
    "could contribute",
    "appears to",
    "appears",
    "implies",
    "implicated",
    "central to",
    "pathogenesis",
    "mediating",
    "involved in",
    "likely",
    "possibly",
    "possible",
    "predicted",
    "indicates",
    "indicate",
    "unclear",
    "remains unclear",
    "incidental finding",
    "pathogenic link",
    "preliminary association",
    "preliminary",
)
_REFUTATION_TERMS = (
    "no evidence",
    "not associated",
    "refuted",
    "refute",
    "conflicting",
)
_DISPUTED_TERMS = (
    "disputed",
    "conflicting",
    "conflict",
    "unresolved",
    "controversial",
    "predicted targets",
    "predicted target",
    "predicted genes",
    "predicted gene",
    "predicted",
    "computational prediction",
    "bioinformatic prediction",
)
_DISEASE_LIST_TERMS = (
    "influenza",
    "rsv",
    "covid-19",
    "crohn",
    "bacterial infection",
    "viral infection",
)


def score_candidate_support(item: EvidenceVerificationInput) -> EvidenceVerificationResult:
    """Score deterministic support for one candidate without external model calls."""
    snippet = _normalize(item.source_snippet)
    target_gene = _normalize(item.target_gene)
    target_aliases = tuple(_normalize(alias) for alias in item.disease_aliases if _normalize(alias))
    gene_present = bool(target_gene and target_gene in snippet)
    disease_present = any(alias in snippet for alias in target_aliases)
    target_specificity_score = _target_specificity(
        gene_present,
        disease_present,
        disease_field=item.field_id == "B.disease_diagnosis",
    )

    causal_score = _contains_any(snippet, _CAUSAL_TERMS)
    direct_association_score = _contains_any(snippet, _DIRECT_ASSOCIATION_TERMS)
    susceptibility_score = _contains_any(snippet, _SUSCEPTIBILITY_TERMS)
    hedged_inference_score = _contains_any(snippet, _HEDGED_INFERENCE_TERMS)
    refute_score = _contains_any(snippet, _REFUTATION_TERMS)
    disputed_score = _contains_any(snippet, _DISPUTED_TERMS)
    disease_list_penalty = _disease_list_penalty(snippet, target_aliases)

    recommended_value = _recommend_value(
        item.candidate_value,
        causal_score,
        direct_association_score,
        susceptibility_score,
        hedged_inference_score,
        refute_score,
        disputed_score,
    )
    support_score = _support_score(
        target_specificity_score=target_specificity_score,
        causal_score=causal_score,
        direct_association_score=direct_association_score,
        susceptibility_score=susceptibility_score,
        hedged_inference_score=hedged_inference_score,
        refute_score=refute_score,
        disputed_score=disputed_score,
        disease_list_penalty=disease_list_penalty,
    )
    contradiction_score = 0.8 if refute_score and not disputed_score else 0.0
    requires_review = (
        contradiction_score >= 0.7
        or target_specificity_score < 0.5
        or support_score < 0.6
    )
    rationale = _rationale(
        gene_present=gene_present,
        disease_present=disease_present,
        recommended_value=recommended_value,
        disease_list_penalty=disease_list_penalty,
    )
    return EvidenceVerificationResult(
        field_id=item.field_id,
        recommended_value=recommended_value,
        support_score=support_score,
        contradiction_score=contradiction_score,
        target_specificity_score=target_specificity_score,
        rationale=rationale,
        requires_review=requires_review,
    )


def _target_specificity(gene_present: bool, disease_present: bool, *, disease_field: bool) -> float:
    if disease_field and not disease_present:
        return 0.0
    if gene_present and disease_present:
        return 1.0
    if gene_present or disease_present:
        return 0.55
    return 0.0


def _recommend_value(
    candidate_value: str,
    causal_score: bool,
    direct_association_score: bool,
    susceptibility_score: bool,
    hedged_inference_score: bool,
    refute_score: bool,
    disputed_score: bool,
) -> str:
    if disputed_score and not refute_score:
        return "disputed"
    if refute_score:
        return RelationshipLabel.REFUTED.value
    if causal_score:
        return RelationshipLabel.CAUSATIVE.value
    if susceptibility_score:
        return RelationshipLabel.SUSCEPTIBILITY.value
    if hedged_inference_score:
        return RelationshipLabel.UNCERTAIN.value
    if direct_association_score and not hedged_inference_score:
        return RelationshipLabel.UNCERTAIN.value
    normalized = _normalize(candidate_value).replace(" ", "_")
    if normalized in {label.value for label in RelationshipLabel}:
        return normalized
    return RelationshipLabel.UNCERTAIN.value


def _support_score(
    *,
    target_specificity_score: float,
    causal_score: bool,
    direct_association_score: bool,
    susceptibility_score: bool,
    hedged_inference_score: bool,
    refute_score: bool,
    disputed_score: bool,
    disease_list_penalty: float,
) -> float:
    if disputed_score and not refute_score:
        cue_score = 0.15
    elif refute_score:
        cue_score = 0.0
    elif causal_score:
        cue_score = 0.45
    elif susceptibility_score:
        cue_score = 0.25
    elif direct_association_score:
        cue_score = 0.25
    elif hedged_inference_score:
        cue_score = 0.20
    else:
        cue_score = 0.0
    return max(0.0, min(1.0, round(0.65 * target_specificity_score + cue_score - disease_list_penalty, 4)))


def _disease_list_penalty(snippet: str, disease_aliases: tuple[str, ...]) -> float:
    list_hits = sum(1 for term in _DISEASE_LIST_TERMS if term in snippet)
    target_hit = any(alias in snippet for alias in disease_aliases)
    if target_hit:
        return 0.0
    if list_hits >= 3:
        return 0.35
    if list_hits >= 1:
        return 0.15
    return 0.0


def _rationale(
    *,
    gene_present: bool,
    disease_present: bool,
    recommended_value: str,
    disease_list_penalty: float,
) -> str:
    parts = [f"recommended={recommended_value}"]
    if gene_present:
        parts.append("target gene present")
    if disease_present:
        parts.append("target disease present")
    if disease_list_penalty > 0:
        parts.append("non-target disease-list penalty")
    return "; ".join(parts)


def _contains_any(snippet: str, terms: tuple[str, ...]) -> bool:
    return any(term in snippet for term in terms)


def _normalize(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip().casefold())
