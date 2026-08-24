"""Deterministic recovery of high-signal fields from already selected target spans."""

from __future__ import annotations

import re

from src.core.standardize_entities_and_align_knowledge.hgvs_normalizer import (
    canonical_protein_hgvs,
    expand_hgvs_aliases,
)

from ..domain.catalog import get_field_spec
from ..domain.normalization import AcmgEvidenceValueNormalizer
from ..contracts import EvidenceItem, EvidenceStatus, ExtractionTarget, SourceLocation, TrackDocument
from ..core.grouping import make_group_id


class TargetSpanFieldRecovery:
    """Recover high-value fields from source snippets already selected by extraction."""

    def recover(self, document: TrackDocument, items: list[EvidenceItem]) -> list[EvidenceItem]:
        target = document.extraction_target
        if target is None:
            return items
        snippets = tuple(_selected_target_snippets(items))
        windows = _target_variant_windows(document)
        recovered = _rewrite_paper_nonsense_on_coding_indel(document, list(items))
        group_id = _target_group_id(document, recovered)
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
            candidates.extend(_family_recoveries(document, snippet))
            if _snippet_mentions_target_variant(document, snippet):
                candidates.extend(_phasing_recoveries(document, snippet))
        for window in windows:
            if _snippet_mentions_target_variant(document, window):
                candidates.extend(_family_recoveries(document, window))
                candidates.extend(_phasing_recoveries(document, window))
        for family_text in _document_level_joint_parental_texts(document):
            candidates.extend(_family_recoveries(document, family_text))
        candidates.extend(_document_identity_recoveries(document))
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
        "A.variant_hgvs_c",
        "A.variant_hgvs_p",
        "A.functional_domain_or_hotspot",
        "B.disease_diagnosis",
        "B.mode_of_inheritance_reported",
        "C.in_trans_confirmation",
        "C.maternal_genotype",
        "C.paternal_genotype",
        "C.de_novo_status",
        "C.parentage_confirmed",
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
    variant = " ".join(
        value
        for value in (
            target.primary_variant if target else "",
            target.variant_hgvs_c if target else "",
            target.variant_hgvs_p if target else "",
        )
        if value
    )
    compact = _normalize(variant).replace("&gt;", ">").replace(" ", "")
    if _coding_indel_token(compact) or _coding_indel_token(normalized.replace(" ", "")):
        if "移码" in normalized or "frameshift" in normalized or "提前终止" in normalized or "缺失" in normalized:
            return "frameshift"
        if re.search(r"c\.\d+(?:_\d+)?(?:del|ins)", compact + normalized.replace(" ", "")):
            return "frameshift"
        return "deletion"
    if "missense" in normalized or "错义" in normalized:
        return "missense"
    if "nonsense" in normalized or "无义" in normalized:
        return "nonsense"
    if "frameshift" in normalized or "移码" in normalized:
        return "frameshift"
    if "deletion" in normalized or " del" in normalized or "del" in compact:
        return "deletion"
    if "duplication" in normalized or " dup" in normalized or "dup" in compact:
        return "duplication"
    return ""


def _coding_indel_token(compact: str) -> bool:
    return AcmgEvidenceValueNormalizer.has_coding_indel(compact)


def _document_has_coding_indel(document: TrackDocument, items: list[EvidenceItem]) -> bool:
    target = document.extraction_target
    blobs = [
        target.variant_hgvs_c if target else "",
        target.primary_variant if target else "",
    ]
    for item in items:
        if item.field_id == "A.variant_hgvs_c" and item.status == EvidenceStatus.FOUND:
            blobs.append(str(item.value or ""))
        blobs.append(item.target_variant)
    return any(AcmgEvidenceValueNormalizer.has_coding_indel(blob) for blob in blobs)


def _rewrite_paper_nonsense_on_coding_indel(
    document: TrackDocument,
    items: list[EvidenceItem],
) -> list[EvidenceItem]:
    """Overwrite LLM nonsense when the target (or sibling HGVS) is a coding del/ins."""
    if not _document_has_coding_indel(document, items):
        return items
    rewritten: list[EvidenceItem] = []
    for item in items:
        value = str(item.value).strip().lower() if item.value is not None else ""
        if (
            item.field_id == "A.variant_type"
            and item.status == EvidenceStatus.FOUND
            and value in AcmgEvidenceValueNormalizer._NONSENSE_TYPE_VALUES
        ):
            note = "target_span_recovery:coding_indel_not_nonsense"
            notes = f"{item.notes}; {note}" if item.notes else note
            rewritten.append(item.model_copy(update={"value": "frameshift", "notes": notes}))
            continue
        rewritten.append(item)
    return rewritten


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


_JOINT_PARENTAL_NEGATIVE_RE = re.compile(
    r"(?:患儿)?父母.{0,12}(?:均)?(?:未检测(?:到(?:突变)?)?|未携带|该位点均?无(?:异常|变异)?|无异常|无变异)|"
    r"both parents.{0,80}(?:not (?:found|detected|carrying)|negative|wild[- ]type)|"
    r"not found in (?:his|her|the) parents|"
    r"no mutations were detected in (?:their|the) parents|"
    r"observed only in the patient|"
    r"只在患儿(?:中)?发现|仅在患儿(?:中)?发现|"
    r"환자\s*부모.{0,40}정상",
    re.IGNORECASE,
)
_DE_NOVO_PHRASE_RE = re.compile(
    r"\bde[\s-]*novo\b|denovo|新发突变|新生变异",
    re.IGNORECASE,
)


def _family_recoveries(document: TrackDocument, snippet: str) -> tuple[tuple[str, str, str], ...]:
    """Recover assumed-de-novo / parental-genotype facts from a joint negative quote."""
    inherited = AcmgEvidenceValueNormalizer._INHERITED_VARIANT_RE.search(snippet)
    joint = _JOINT_PARENTAL_NEGATIVE_RE.search(snippet)
    if inherited is not None and joint is None:
        return ()
    recovered: list[tuple[str, str, str]] = []
    if joint:
        quote = _excerpt(snippet, joint)
        recovered.append(("C.maternal_genotype", "target_absent", quote))
        recovered.append(("C.paternal_genotype", "target_absent", quote))
        recovered.append(("C.de_novo_status", "de_novo", quote))
    elif _DE_NOVO_PHRASE_RE.search(snippet) and (
        _snippet_mentions_target_variant(document, snippet) or _mentions_both_parents_tested(snippet)
    ):
        de_novo = _DE_NOVO_PHRASE_RE.search(snippet)
        if de_novo:
            recovered.append(("C.de_novo_status", "de_novo", _excerpt(snippet, de_novo)))
    if recovered and not _document_has_parentage_confirmation(document):
        recovered.append(("C.parentage_confirmed", "not_confirmed", recovered[0][2]))
    return tuple(recovered)


def _mentions_both_parents_tested(snippet: str) -> bool:
    folded = snippet.casefold()
    return "父母" in snippet or "both parents" in folded or "his parents" in folded or "her parents" in folded


def _document_has_parentage_confirmation(document: TrackDocument) -> bool:
    text = document.formatted_text or ""
    return AcmgEvidenceValueNormalizer._PARENTAGE_CONFIRMED_RE.search(text) is not None


def _document_level_joint_parental_texts(document: TrackDocument) -> tuple[str, ...]:
    """Use a paper-level joint parental sentence when the target is present and nothing is inherited."""
    text = document.formatted_text or ""
    if not text or not _snippet_mentions_target_variant(document, text):
        return ()
    if AcmgEvidenceValueNormalizer._INHERITED_VARIANT_RE.search(text):
        return ()
    match = _JOINT_PARENTAL_NEGATIVE_RE.search(text)
    if match is None:
        return ()
    return (_excerpt(text, match, radius=80),)


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


_MECP2_MBD = (90, 162)
_MECP2_TRD = (302, 306)
_CODING_COORDS_RE = re.compile(r"(?:c\.)?(\d+)([ACGT])>([ACGT])$", re.IGNORECASE)
_TABLE_CODING_RE = re.compile(
    r"(?:c\.)?\s*(\d+)\s*([ACGT])\s*(?:→|->|>|＞|&gt;)\s*([ACGT])",
    re.IGNORECASE,
)
_OCR_CODING_RE = re.compile(r"c[.\uFF0E]\s*(\d+)\s*([ACGT])\s+([ACGT])", re.IGNORECASE)
_PROTEIN_POS_RE = re.compile(r"(?:p\.)?\s*(?:[A-Z][a-z]{2}|[A-Z])\s*(\d+)")
_STOP_PROTEIN_RE = re.compile(r"(?:Ter|X|\*)$")
_TRUNCATED_PROTEIN_RE = re.compile(r"^p\.[A-Z][a-z]{2}\d+$")
_XQ28_REGION_RE = re.compile(r"Xq28.{0,60}(?:重复|duplication|dup)", re.IGNORECASE)
_XQ28_SIZE_RE = re.compile(r"(\d+\.\d+)\s*(?:Mb|MB)")
_MDS_RE = re.compile(r"MECP2\s*重复综合征|MECP2 duplication syndrome", re.IGNORECASE)
_RETT_RE = re.compile(
    r"Rett\s*综合征|Rett syndrome|syndrome de Rett|синдром\s*Ретта|"
    r"S[ií]ndrome de Rett",
    re.IGNORECASE,
)


def _document_identity_recoveries(document: TrackDocument) -> tuple[tuple[str, str, str], ...]:
    """Fill identity fields from the full document when the paper used a non-HGVS spelling."""
    text = document.formatted_text or ""
    if not text:
        return ()
    recovered: list[tuple[str, str, str]] = []
    coding = _recover_coding_hgvs(document, text)
    if coding is not None:
        recovered.append(("A.variant_hgvs_c", coding[0], coding[1]))
    protein = _recover_protein_hgvs(document, text)
    if protein is not None:
        recovered.append(("A.variant_hgvs_p", protein[0], protein[1]))
    variant_type = _recover_variant_type(document, text)
    if variant_type is not None:
        recovered.append(("A.variant_type", variant_type[0], variant_type[1]))
    domain = _recover_mecp2_domain(document, text)
    if domain is not None:
        recovered.append(("A.functional_domain_or_hotspot", domain[0], domain[1]))
    diagnosis = _recover_diagnosis(document, text)
    if diagnosis is not None:
        recovered.append(("B.disease_diagnosis", diagnosis[0], diagnosis[1]))
    return tuple(recovered)


def _parse_coding_coords(value: str) -> tuple[str, str, str] | None:
    compact = re.sub(r"\s+", "", value or "")
    compact = compact.replace("→", ">").replace("->", ">").replace("＞", ">")
    match = _CODING_COORDS_RE.fullmatch(compact)
    if match is None:
        return None
    return match.group(1), match.group(2).upper(), match.group(3).upper()


def _recover_coding_hgvs(document: TrackDocument, text: str) -> tuple[str, str] | None:
    target = document.extraction_target
    if target is None:
        return None
    xq28 = _recover_xq28_dup(target, text)
    if xq28 is not None:
        return xq28
    wanted = _parse_coding_coords(target.variant_hgvs_c)
    if wanted is not None:
        pos, ref, alt = wanted
        for match in (*_TABLE_CODING_RE.finditer(text), *_OCR_CODING_RE.finditer(text)):
            if match.group(1) == pos and match.group(2).upper() == ref and match.group(3).upper() == alt:
                return f"c.{pos}{ref}>{alt}", match.group(0)
        exact = _find_token(text, (f"c.{pos}{ref}>{alt}", f"c.{pos}{ref}&gt;{alt}"))
        if exact is not None:
            return f"c.{pos}{ref}>{alt}", exact
        return None
    raw = target.variant_hgvs_c or ""
    # rett_078 stores the paper's protein string in the coding slot.
    if raw.startswith("p."):
        hit = _find_token(text, _protein_tokens(raw))
        if hit is not None:
            return raw, hit
    if re.search(r"(?:del|ins|dup)", raw, re.IGNORECASE) and "xq28" not in raw.casefold():
        hit = _find_token(text, (raw, raw.replace(">", "&gt;")))
        if hit is not None:
            return raw, hit
    return None


def _recover_xq28_dup(target: ExtractionTarget, text: str) -> tuple[str, str] | None:
    blob = f"{target.variant_hgvs_c} {target.primary_variant}"
    if not re.search(r"xq28|_dup|\bdup\b", blob, re.IGNORECASE):
        return None
    for match in _XQ28_REGION_RE.finditer(text):
        tail = text[match.start() : match.end() + 80]
        size = _XQ28_SIZE_RE.search(tail)
        if size is None:
            continue
        return f"Xq28 {size.group(1)} Mb dup", tail[: size.end()]
    return None


def _recover_protein_hgvs(document: TrackDocument, text: str) -> tuple[str, str] | None:
    target = document.extraction_target
    if target is None or not target.variant_hgvs_p:
        return None
    wanted = canonical_protein_hgvs(target.variant_hgvs_p) or target.variant_hgvs_p
    hit = _find_token(text, _protein_tokens(target.variant_hgvs_p))
    if hit is None:
        return None
    return wanted, hit


def _protein_position_from_text(*values: str) -> int | None:
    for value in values:
        match = _PROTEIN_POS_RE.search(value or "")
        if match is not None:
            return int(match.group(1))
    return None


def _recover_mecp2_domain(document: TrackDocument, text: str) -> tuple[str, str] | None:
    target = document.extraction_target
    if target is None or (target.gene_symbol or "").casefold() != "mecp2":
        return None
    position = _protein_position_from_text(target.variant_hgvs_p, target.variant_hgvs_c)
    if position is None:
        return None
    if _MECP2_MBD[0] <= position <= _MECP2_MBD[1]:
        label = "MBD (VCEP 90-162)"
    elif _MECP2_TRD[0] <= position <= _MECP2_TRD[1]:
        label = "TRD (VCEP 302-306)"
    else:
        return None
    hit = _find_token(
        text,
        [*_protein_tokens(target.variant_hgvs_p), *_protein_tokens(target.variant_hgvs_c)],
    )
    if hit is None:
        return None
    return label, hit


def _recover_diagnosis(document: TrackDocument, text: str) -> tuple[str, str] | None:
    target = document.extraction_target
    if target is None:
        return None
    target_is_mds = bool(
        re.search(r"xq28|_dup|\bdup\b", f"{target.variant_hgvs_c} {target.primary_variant}", re.I)
    )
    if target_is_mds:
        mds = _MDS_RE.search(text)
        if mds is None:
            return None
        return "MECP2 duplication syndrome", mds.group(0)
    rett = _RETT_RE.search(text)
    if rett is None:
        return None
    return "Rett syndrome", rett.group(0)


def _recover_variant_type(document: TrackDocument, text: str) -> tuple[str, str] | None:
    target = document.extraction_target
    if target is None:
        return None
    coding = target.variant_hgvs_c or ""
    protein = target.variant_hgvs_p or ""
    if AcmgEvidenceValueNormalizer.has_coding_indel(coding):
        hit = _find_token(text, (coding, coding.replace(">", "&gt;"), *_protein_tokens(protein)))
        if hit is None:
            return None
        return "frameshift", hit
    compact_protein = re.sub(r"\s+", "", protein)
    is_stop = bool(_STOP_PROTEIN_RE.search(compact_protein))
    is_truncated = bool(_TRUNCATED_PROTEIN_RE.fullmatch(compact_protein))
    if not (is_stop or is_truncated):
        return None
    hit = _find_token(text, (*_protein_tokens(protein), coding))
    if hit is None:
        return None
    return "nonsense", hit


def _protein_tokens(value: str) -> tuple[str, ...]:
    raw = (value or "").strip()
    if not raw:
        return ()
    candidates = [raw, re.sub(r"\s+", "", raw), re.sub(r"\s+", " ", raw)]
    if raw.startswith("p."):
        remainder = raw[2:].strip()
        candidates.append(remainder)
        candidates.append(f"p. {remainder}")
    for alias in expand_hgvs_aliases(raw):
        candidates.append(alias)
        if alias.startswith("p."):
            candidates.append(alias[2:])
    canon = canonical_protein_hgvs(raw)
    if canon:
        candidates.append(canon)
        candidates.append(canon[2:])
        for alias in expand_hgvs_aliases(canon):
            one = re.fullmatch(r"p\.([A-Z])(\d+)([A-Z*])", alias)
            if one is None:
                continue
            alt = "X" if one.group(3) == "*" else one.group(3)
            candidates.append(alias)
            candidates.append(alias[2:])
            candidates.append(f"{one.group(1)} {one.group(2)} {alt}")
    starred: list[str] = []
    for token in candidates:
        if "Ter" in token:
            starred.append(token.replace("Ter", "*"))
            starred.append(token.replace("Ter", r"\*"))
        if "*" in token:
            starred.append(token.replace("*", "Ter"))
            starred.append(token.replace("*", r"\*"))
    candidates.extend(starred)
    tokens: list[str] = []
    for token in candidates:
        token = token.strip()
        if len(token) >= 4 and token not in tokens:
            tokens.append(token)
    return tuple(tokens)


def _find_token(text: str, tokens: tuple[str, ...] | list[str]) -> str | None:
    folded = text.casefold()
    for token in sorted({item for item in tokens if item and len(item) >= 4}, key=len, reverse=True):
        index = text.find(token)
        if index < 0:
            index = folded.find(token.casefold())
        if index >= 0:
            return text[index : index + len(token)]
    return None


def _target_variant_windows(document: TrackDocument) -> tuple[str, ...]:
    """Take local windows around the target coding/protein HGVS so phasing facts can be recovered."""
    target = document.extraction_target
    if target is None:
        return ()
    text = document.formatted_text or ""
    windows: list[str] = []
    for needle in _variant_window_needles(target):
        start = 0
        while True:
            index = text.find(needle, start)
            if index < 0:
                index = text.casefold().find(needle.casefold(), start)
            if index < 0:
                break
            lo = max(0, index - _VARIANT_WINDOW_RADIUS)
            hi = min(len(text), index + len(needle) + _VARIANT_WINDOW_RADIUS)
            windows.append(text[lo:hi])
            start = index + len(needle)
    return tuple(dict.fromkeys(windows))


def _variant_window_needles(target: ExtractionTarget) -> tuple[str, ...]:
    needles: list[str] = []
    for raw in (target.variant_hgvs_c, target.variant_hgvs_p):
        if not raw:
            continue
        needles.append(raw)
        needles.append(raw.replace(">", "&gt;"))
        needles.extend(_protein_tokens(raw))
        coords = _parse_coding_coords(raw)
        if coords is not None:
            pos, ref, alt = coords
            needles.extend((f"{pos} {ref}→{alt}", f"{pos} {ref}>{alt}", f"c.{pos}{ref}>{alt}"))
    return tuple(dict.fromkeys(item for item in needles if item and len(item) >= 4))


def _snippet_mentions_target_variant(document: TrackDocument, snippet: str) -> bool:
    target = document.extraction_target
    if target is None:
        return False
    compact_snippet = _compact_variant_key(snippet)
    folded = snippet.casefold()
    for needle in (target.variant_hgvs_c, target.variant_hgvs_p):
        if not needle:
            continue
        compact = _compact_variant_key(needle)
        if compact and compact in compact_snippet:
            return True
        for token in _protein_tokens(needle):
            if token.casefold() in folded or _compact_variant_key(token) in compact_snippet:
                return True
        coords = _parse_coding_coords(needle)
        if coords is not None:
            pos, ref, alt = coords
            if f"{pos}{ref}>{alt}".casefold() in compact_snippet:
                return True
    return False


def _compact_variant_key(value: str) -> str:
    text = _normalize(value).replace("&gt;", ">").replace("→", ">").replace("->", ">")
    text = text.replace(" ", "")
    text = re.sub(r"^c\.", "", text)
    return re.sub(r"^p\.", "", text)


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
        target_variant=(target.variant_hgvs_c or target.primary_variant) if target else "",
    )


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
