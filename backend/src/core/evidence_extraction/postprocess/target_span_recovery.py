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
        windows = _target_variant_windows(document)
        if not snippets and not windows:
            return items

        recovered = list(items)
        group_id = _target_group_id(document, items)
        missing_field_ids = _missing_field_ids(recovered)
        for field_id, value, snippet in self._candidate_recoveries(document, snippets, windows):
            if field_id not in missing_field_ids:
                continue
            recovered.append(_recovered_item(field_id, value, snippet, group_id, document))
            missing_field_ids.remove(field_id)
        return recovered

    def _candidate_recoveries(
        self,
        document: TrackDocument,
        snippets: tuple[str, ...],
        windows: tuple[str, ...] = (),
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
            if _snippet_mentions_target_variant(document, snippet):
                candidates.extend(_phasing_recoveries(document, snippet))
        for window in windows:
            if _snippet_mentions_target_variant(document, window):
                candidates.extend(_phasing_recoveries(document, window))
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
        "C.in_trans_confirmation",
        "C.maternal_genotype",
        "C.paternal_genotype",
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
    if "autosomal dominant" in normalized:
        return "AD"
    if "x-linked" in normalized or "x linked" in normalized:
        return "XL"
    return ""


def _variant_type_value(document: TrackDocument, normalized: str) -> str:
    target = document.extraction_target
    variant = target.primary_variant if target else ""
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


_MATERNAL_GT_RE = re.compile(
    r"maternal allele.{0,160}|母源[^。]{0,80}|母亲[^。]{0,40}(?:携带|未检测|缺失|del)",
    re.IGNORECASE,
)
_PATERNAL_GT_RE = re.compile(
    r"paternal allele.{0,160}|父源[^。]{0,80}|父亲[^。]{0,40}(?:携带|未检测|缺失|del)",
    re.IGNORECASE,
)
_VARIANT_WINDOW_RADIUS = 400


def _phasing_recoveries(document: TrackDocument, snippet: str) -> tuple[tuple[str, str, str], ...]:
    """Recover PM3-ready in-trans / parental genotype facts from a target-scoped span."""
    recovered: list[tuple[str, str, str]] = []
    in_trans_quote = _in_trans_quote(document, snippet)
    if in_trans_quote:
        recovered.append(("C.in_trans_confirmation", "in_trans", in_trans_quote))
    maternal = _MATERNAL_GT_RE.search(snippet)
    if maternal:
        recovered.append(("C.maternal_genotype", _compact(maternal.group(0)), _excerpt(snippet, maternal)))
    paternal = _PATERNAL_GT_RE.search(snippet)
    if paternal:
        recovered.append(("C.paternal_genotype", _compact(paternal.group(0)), _excerpt(snippet, paternal)))
    return tuple(recovered)


def _in_trans_quote(document: TrackDocument, snippet: str) -> str:
    in_trans = re.search(r"in[\s-]+trans", snippet, re.IGNORECASE)
    if in_trans:
        return _excerpt(snippet, in_trans)
    compound = re.search(r"compound heterozyg|复合杂合", snippet, re.IGNORECASE)
    if compound is None:
        return ""
    local = _excerpt(snippet, compound, radius=200)
    if _snippet_mentions_target_variant(document, local):
        return local
    if _MATERNAL_GT_RE.search(snippet) and _PATERNAL_GT_RE.search(snippet):
        return _excerpt(snippet, compound)
    return ""


def _target_variant_windows(document: TrackDocument) -> tuple[str, ...]:
    """Take local windows around the target coding/protein HGVS so phasing facts can be recovered."""
    target = document.extraction_target
    if target is None:
        return ()
    text = document.formatted_text or ""
    needles = [value for value in (target.variant_hgvs_c, target.variant_hgvs_p) if value]
    windows: list[str] = []
    for needle in needles:
        for variant in dict.fromkeys((needle, needle.replace(">", "&gt;"))):
            start = 0
            while True:
                index = text.find(variant, start)
                if index < 0:
                    break
                lo = max(0, index - _VARIANT_WINDOW_RADIUS)
                hi = min(len(text), index + len(variant) + _VARIANT_WINDOW_RADIUS)
                windows.append(text[lo:hi])
                start = index + len(variant)
    return tuple(dict.fromkeys(windows))


def _snippet_mentions_target_variant(document: TrackDocument, snippet: str) -> bool:
    target = document.extraction_target
    if target is None:
        return False
    normalized = _normalize(snippet).replace("&gt;", ">")
    compact_snippet = normalized.replace(" ", "")
    for needle in (target.variant_hgvs_c, target.variant_hgvs_p):
        if not needle:
            continue
        compact = _normalize(needle).replace("&gt;", ">").replace(" ", "")
        if compact and compact in compact_snippet:
            return True
    return False


def _excerpt(text: str, match: re.Match[str], radius: int = 160) -> str:
    lo = max(0, match.start() - radius)
    hi = min(len(text), match.end() + radius)
    return text[lo:hi].strip()


def _compact(value: str) -> str:
    return " ".join(value.split())


def _target_group_id(document: TrackDocument, items: list[EvidenceItem]) -> str:
    for item in items:
        if item.group_id:
            return item.group_id
    target = document.extraction_target
    if target is None:
        return make_group_id("", "")
    return make_group_id(target.gene_symbol, target.primary_variant)


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
        assigned_acmg_codes=[],
        assigned_clingen_modules=[],
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
        target_variant=target.primary_variant if target else "",
    )


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
