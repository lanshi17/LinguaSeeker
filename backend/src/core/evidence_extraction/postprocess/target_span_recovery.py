"""Deterministic recovery of high-signal fields from already selected target spans."""

from __future__ import annotations

import re

from ..domain.catalog import get_field_spec
from ..contracts import EvidenceItem, EvidenceStatus, SourceLocation, TrackDocument
from ..core.grouping import make_group_id


class TargetSpanFieldRecovery:
    """Recover high-value fields from source snippets already selected by extraction."""

    def recover(self, document: TrackDocument, items: list[EvidenceItem]) -> list[EvidenceItem]:
        target = document.extraction_target
        if target is None:
            return items
        snippets = tuple(_selected_target_snippets(items))
        if not snippets:
            return items

        recovered = list(items)
        group_id = _target_group_id(document, items)
        missing_field_ids = _missing_field_ids(recovered)
        for field_id, value, snippet in self._candidate_recoveries(document, snippets):
            if field_id not in missing_field_ids:
                continue
            recovered.append(_recovered_item(field_id, value, snippet, group_id, document))
            missing_field_ids.remove(field_id)
        return recovered

    def _candidate_recoveries(
        self,
        document: TrackDocument,
        snippets: tuple[str, ...],
    ) -> tuple[tuple[str, str, str], ...]:
        candidates: list[tuple[str, str, str]] = []
        for snippet in snippets:
            normalized = _normalize(snippet)
            if _supports_causative_relationship(document, normalized):
                candidates.append(("A.gene_disease_relationship", "causative", snippet))
            inheritance = _inheritance_value(normalized)
            if inheritance:
                candidates.append(("B.mode_of_inheritance_reported", inheritance, snippet))
            variant_type = _variant_type_value(document, normalized)
            if variant_type:
                candidates.append(("A.variant_type", variant_type, snippet))
            assertion = _clinvar_assertion_value(normalized)
            if assertion:
                candidates.append(("J.clinvar_assertion", assertion, snippet))
        return tuple(candidates)


def _selected_target_snippets(items: list[EvidenceItem]) -> tuple[str, ...]:
    snippets: list[str] = []
    for item in items:
        if item.status != EvidenceStatus.FOUND:
            continue
        source = item.raw_source or item.source
        if source is not None and source.text_snippet.strip():
            snippets.append(source.text_snippet.strip())
    return tuple(dict.fromkeys(snippets))


def _missing_field_ids(items: list[EvidenceItem]) -> set[str]:
    present = {item.field_id for item in items if item.status == EvidenceStatus.FOUND and _has_value(item.value)}
    return {
        "A.gene_disease_relationship",
        "A.variant_type",
        "B.mode_of_inheritance_reported",
        "J.clinvar_assertion",
    } - present


def _has_value(value: str | int | float | bool | list[str] | None) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return True


def _supports_causative_relationship(document: TrackDocument, normalized: str) -> bool:
    target = document.extraction_target
    if target is None:
        return False
    gene = target.gene_symbol.casefold()
    disease = target.disease_name.casefold()
    has_target = gene in normalized and _disease_token_hit(disease, normalized)
    if not has_target:
        return False
    return any(
        phrase in normalized
        for phrase in (
            "cause ",
            "causes ",
            "caused by",
            "result from",
            "results from",
            "resulting from",
            "biallelic pathogenic variants",
            "pathogenic variants in",
            "mutations in",
        )
    )


def _disease_token_hit(disease: str, normalized: str) -> bool:
    tokens = [token for token in re.split(r"[^a-z0-9]+", disease.casefold()) if len(token) >= 4]
    return bool(tokens) and any(token in normalized for token in tokens)


def _inheritance_value(normalized: str) -> str:
    if (
        "autosomal recessive" in normalized
        or "biallelic" in normalized
        or "compound heterozyg" in normalized
        or "homozyg" in normalized
    ):
        return "AR"
    if "autosomal dominant" in normalized or "de novo" in normalized:
        return "AD"
    return ""


def _variant_type_value(document: TrackDocument, normalized: str) -> str:
    target = document.extraction_target
    variant = target.variant_hgvs_p if target else ""
    if "missense" in normalized:
        return "missense"
    if "nonsense" in normalized:
        return "nonsense"
    if "frameshift" in normalized:
        return "frameshift"
    if "deletion" in normalized or " del" in normalized or "del" in variant.casefold():
        return "deletion"
    if "duplication" in normalized or " dup" in normalized or "dup" in variant.casefold():
        return "duplication"
    return ""


def _clinvar_assertion_value(normalized: str) -> str:
    if "pathogenic" not in normalized:
        return ""
    if "likely pathogenic" in normalized or re.search(r"\blp\b", normalized):
        return "Likely pathogenic"
    if "pathogenic" in normalized:
        return "Pathogenic"
    return ""


def _target_group_id(document: TrackDocument, items: list[EvidenceItem]) -> str:
    for item in items:
        if item.group_id:
            return item.group_id
    target = document.extraction_target
    if target is None:
        return make_group_id("", "")
    return make_group_id(target.gene_symbol, target.variant_hgvs_p)


def _recovered_item(
    field_id: str,
    value: str,
    snippet: str,
    group_id: str,
    document: TrackDocument,
) -> EvidenceItem:
    spec = get_field_spec(field_id)
    target = document.extraction_target
    return EvidenceItem(
        field_id=field_id,
        category=spec.category_id,
        field_name=spec.field_name,
        status=EvidenceStatus.FOUND,
        value=value,
        assigned_acmg_codes=list(spec.acmg_codes),
        assigned_clingen_modules=list(spec.clingen_modules),
        source=SourceLocation(
            context_type="text",
            context_ref="target_span_recovery",
            text_snippet=snippet,
        ),
        confidence=0.72,
        group_id=group_id,
        notes="target_span_recovery",
        inference_basis=["Recovered deterministically from already selected target span."],
        target_gene=target.gene_symbol if target else "",
        target_disease=target.disease_name if target else "",
        target_variant=target.variant_hgvs_p if target else "",
    )


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
