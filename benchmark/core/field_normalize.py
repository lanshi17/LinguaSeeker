"""Field-specific normalization for benchmark evidence matching.

Bridges the granularity gap between ground-truth values and LLM-extracted
values for fields where simple text comparison fails:

- **HGVS variants** (``A.variant_hgvs_c``, ``A.variant_hgvs_p``):
  three-letter vs one-letter amino acid codes, transcript prefix removal,
  stop codon normalization. Delegates to
  :mod:`benchmark.datasets.clinvar_fused.hgvs_normalize`.

- **Mode of inheritance** (``B.mode_of_inheritance_reported``,
  ``K.mode_of_inheritance``): maps ClinGen abbreviations (AD, AR, XL, …)
  and free-text descriptions ("autosomal dominant with reduced penetrance")
  to a canonical MOI code.

- **Variant type** (``A.variant_type``): maps ClinVar Type values and
  literature descriptions to the pipeline's enum values.

- **Gene-disease relationship** (``A.gene_disease_relationship``): maps
  free-text relationship statements to the ClinGen enum
  (causative / uncertain / disputed / refuted).
"""
from __future__ import annotations

import re

from benchmark.datasets.clinvar_fused.hgvs_normalize import (
    normalize_hgvs_for_matching,
    normalize_variant_type,
)

__all__ = [
    "normalize_field_for_matching",
    "normalize_gene_disease_relationship",
    "normalize_hpo_terms",
    "normalize_moi",
    "normalize_variant_type",
]

# ── MOI normalization ─────────────────────────────────────────────────

# ClinGen canonical MOI codes (GDV-12 Table 1).
_CANONICAL_MOI = frozenset({
    "AD", "AR", "SD", "XL", "Mitochondrial", "Somatic Mosaicism",
    "Undetermined",
})

# Order matters: longer/more-specific patterns first so that
# "X-linked dominant" is checked before the bare "X-linked".
_MOI_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AD", re.compile(r"autosomal\s*dominant", re.IGNORECASE)),
    ("AR", re.compile(r"autosomal\s*recessive", re.IGNORECASE)),
    ("XL", re.compile(r"x[\s\-]*linked", re.IGNORECASE)),
    ("SD", re.compile(r"semi[\s\-]*dominant", re.IGNORECASE)),
    ("Mitochondrial", re.compile(r"mitochondrial|maternal\s+inheritance", re.IGNORECASE)),
    ("Somatic Mosaicism", re.compile(r"somatic\s+mosaic|mosaicism", re.IGNORECASE)),
    ("Undetermined", re.compile(r"undetermined|unknown\s+inheritance", re.IGNORECASE)),
]

# Abbreviation aliases → canonical code.
_MOI_ABBR: dict[str, str] = {
    "ad": "AD",
    "ar": "AR",
    "sd": "SD",
    "xl": "XL",
    "xld": "XL",
    "xlr": "XL",
    "x-linked": "XL",
    "mitochondrial": "Mitochondrial",
    "somatic": "Somatic Mosaicism",
    "undetermined": "Undetermined",
}


def normalize_moi(value: str) -> str:
    """Normalize a mode-of-inheritance value to a canonical ClinGen code.

    Handles:
    - Exact ClinGen codes: "AD" → "AD"
    - Full descriptions: "autosomal dominant with reduced penetrance" → "AD"
    - Bilingual: "X连锁显性遗传" → "XL"
    - Compound: "X-linked dominant; de novo" → "XL"

    Returns ``""`` for empty input. Returns the original upper-cased
    value if no pattern matches (preserving extensibility).
    """
    if not value or not value.strip():
        return ""
    text = value.strip()

    # Already a canonical code
    if text in _CANONICAL_MOI:
        return text

    # Try abbreviation lookup (case-insensitive)
    upper = text.upper()
    if upper in _MOI_ABBR:
        return _MOI_ABBR[upper]
    lower = text.lower()
    if lower in _MOI_ABBR:
        return _MOI_ABBR[lower]

    # Pattern matching for free-text descriptions
    for canonical, pattern in _MOI_PATTERNS:
        if pattern.search(text):
            return canonical

    # Chinese MOI terms
    _zh_patterns: list[tuple[str, str]] = [
        ("AD", "常染色体显性"),
        ("AR", "常染色体隐性"),
        ("XL", "X连锁|x连锁"),
    ]
    for canonical, zh_pat in _zh_patterns:
        if re.search(zh_pat, text, re.IGNORECASE):
            return canonical

    # Unknown — return upper-cased original so downstream can still compare
    return upper


# ── Gene-disease relationship normalization ───────────────────────────

# ClinGen enum values (from _map_classification_to_relationship)
_GDR_CANONICAL = frozenset({"causative", "uncertain", "disputed", "refuted", "unknown"})

# Keyword → canonical relationship.  Leading ``\b`` anchors to word start;
# trailing ``\b`` is omitted on stem-prefixes (e.g. ``refut``) so they also
# match inflected forms (``refuted``, ``disputed``, ``causative`` …).
_GDR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("refuted", re.compile(
        r"\b(?:refut\w*|no\s+evidence|not\s+associated|no\s+relationship|excluded)\b",
        re.IGNORECASE,
    )),
    ("disputed", re.compile(
        r"\b(?:disput\w*|controvers\w*|contradict\w*|conflict\w*)\b",
        re.IGNORECASE,
    )),
    ("uncertain", re.compile(
        r"\b(?:uncertain|limited|possible|preliminary|suggest\w*|may\s+(?:be|cause)|potential)\b",
        re.IGNORECASE,
    )),
    ("causative", re.compile(
        r"\b(?:causat\w*|responsible\s+for|due\s+(?:\w+\s+)?to|cause[sd]?|result\w*\s+from|driven\s+by|attribut\w*)\b",
        re.IGNORECASE,
    )),
]


# Broad relationship terms that map to the most common ClinGen enum.
# Used when ground truth uses a generic term like "associated" instead of
# the more specific ClinGen value (causative/susceptibility/uncertain/etc.).
_GDR_BROAD_TERMS: dict[str, str] = {
    "associated": "causative",
    "related": "causative",
    "linked": "causative",
    "implicated": "causative",
    "susceptibility": "causative",
    "risk factor": "causative",
    "predisposition": "causative",
}


def normalize_gene_disease_relationship(value: str) -> str:
    """Normalize a gene-disease relationship description to canonical enum.

    Maps both enum values and free-text statements:
    - "causative" → "causative"
    - "associated" → "causative" (broad term synonym)
    - "susceptibility" → "causative" (broad term synonym)
    - "MECP2 mutations cause Rett syndrome" → "causative"
    - "The relationship is uncertain" → "uncertain"
    - "Evidence is limited" → "uncertain"
    - "The association is disputed" → "disputed"
    - "No evidence of association" → "refuted"

    Returns ``""`` for empty input. Returns the lower-cased original
    if it's already canonical or no pattern matches.
    """
    if not value or not value.strip():
        return ""
    text = value.strip()
    lower = text.lower()

    # Already canonical
    if lower in _GDR_CANONICAL:
        return lower

    # Broad relationship terms → canonical
    if lower in _GDR_BROAD_TERMS:
        return _GDR_BROAD_TERMS[lower]

    # Pattern matching for free-text
    for canonical, pattern in _GDR_PATTERNS:
        if pattern.search(text):
            return canonical

    return lower


# ── HPO phenotype normalization ───────────────────────────────────────

_HPO_ID_RE = re.compile(r"HP:\d{7}", re.IGNORECASE)

# Conservative benchmark-side phrase map.  Phase 3 still owns full terminology
# matching; this fallback only bridges common raw article phrases in value-F1.
_HPO_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("HP:0001250", re.compile(r"\b(?:seizure|seizures|epileptic|epileptiform)\b", re.IGNORECASE)),
    ("HP:0001252", re.compile(r"\b(?:hypotonia|low\s+muscular\s+tension|abnormal\s+muscular\s+tension)\b", re.IGNORECASE)),
    ("HP:0001263", re.compile(r"\b(?:developmental\s+(?:delay|backwardness|regression)|global\s+developmental\s+delay)\b", re.IGNORECASE)),
    ("HP:0001631", re.compile(r"\batrial\s+septal\s+defect\b", re.IGNORECASE)),
    ("HP:0012759", re.compile(r"\b(?:severe\s+)?neonatal\s+encephalopathy\b", re.IGNORECASE)),
    ("HP:0002353", re.compile(r"\b(?:abnormal\s+EEG|spike\s+slow\s+waves?|slow\s+waves?)\b", re.IGNORECASE)),
]


def normalize_hpo_terms(value: str) -> str:
    """Normalize HPO IDs and selected raw phenotype phrases for matching."""
    if not value or not value.strip():
        return ""
    text = value.strip()
    ids = {match.upper() for match in _HPO_ID_RE.findall(text)}
    for hpo_id, pattern in _HPO_PATTERNS:
        if pattern.search(text):
            ids.add(hpo_id)
    if not ids:
        return text
    return ";".join(sorted(ids))


# ── Dispatch ──────────────────────────────────────────────────────────

# Fields that benefit from specialized normalization.
_HGVS_FIELDS = {"A.variant_hgvs_c", "A.variant_hgvs_p"}
_MOI_FIELDS = {"B.mode_of_inheritance_reported", "K.mode_of_inheritance"}
_VARIANT_TYPE_FIELDS = {"A.variant_type"}
_GDR_FIELDS = {"A.gene_disease_relationship"}
_HPO_FIELDS = {"B.hpo_terms", "B.clinical_phenotypes"}


def normalize_field_for_matching(field_id: str, value: str) -> str:
    """Dispatch to the correct field-specific normalizer.

    For fields without a specialized normalizer, returns the value
    unchanged (the caller's generic normalization still applies).
    """
    if not value:
        return ""
    if field_id in _HGVS_FIELDS:
        return normalize_hgvs_for_matching(value, field_id)
    if field_id in _MOI_FIELDS:
        return normalize_moi(value)
    if field_id in _VARIANT_TYPE_FIELDS:
        return normalize_variant_type(value)
    if field_id in _GDR_FIELDS:
        return normalize_gene_disease_relationship(value)
    if field_id in _HPO_FIELDS:
        return normalize_hpo_terms(value)
    return value
