"""Server-side variant aggregation for the evidence database.

This module is a faithful Python port of
``frontend/src/features/evidence-db/utils/variantAggregation.ts``. The
variant index displays *variant-centric* rows, but the persistence layer
stores *evidence-group-centric* rows (one row per ``group_id``). Aggregation
groups evidence rows by a ``gene:variant[:disease]`` slug, computes per-variant
metrics, then filters/sorts/paginates.

Keeping this logic on the server means the browser only receives the current
page of variants instead of the full evidence-group corpus. The semantics here
MUST match the TypeScript implementation - the same input produces the same
variant rows, ordering, and stats. Tests in
``backend/tests/core/visualize_evidence_with_expert_in_loop/test_variant_aggregation.py``
mirror the TypeScript cases to guard against drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import cmp_to_key
from typing import Any, Iterable
from uuid import UUID

from .contracts import EvidenceSearchResult

UNKNOWN_SLUG_VALUE = "unknown"

SEVERITY_ORDER: tuple[str, ...] = (
    "pathogenic",
    "likely_pathogenic",
    "uncertain",
    "likely_benign",
    "benign",
)

_LANGUAGE_ALIASES: dict[str, str] = {
    "chinese": "zh",
    "deu": "de",
    "eng": "en",
    "english": "en",
    "fra": "fr",
    "fre": "fr",
    "french": "fr",
    "german": "de",
    "japanese": "ja",
    "jpn": "ja",
    "rus": "ru",
    "russian": "ru",
    "zho": "zh",
    "zh-cn": "zh",
    "zh-tw": "zh",
}

_CATEGORY_KEYS: tuple[str, ...] = ("A", "B", "D", "E", "J", "C", "F", "G", "H", "I")


# ── Pure helpers (mirror pathogenicity.ts / fieldModel.ts) ────────────────


def classify_level(classification: str | None) -> str:
    """Map a free-form classification string to a severity level.

    Mirrors ``classifyLevel`` in ``pathogenicity.ts``. Operator precedence in
    the TypeScript original means ``&&`` binds tighter than ``||``; the boolean
    expressions below preserve that.
    """
    lower = (classification or "").lower().strip()
    if not lower or lower in ("not specified", "unknown"):
        return "uncertain"
    if lower == "pathogenic" or (
        "pathogenic" in lower and "likely" not in lower and "benign" not in lower
    ):
        return "pathogenic"
    if "likely pathogenic" in lower or lower == "lp":
        return "likely_pathogenic"
    if lower == "benign" or (
        "benign" in lower and "likely" not in lower and "pathogenic" not in lower
    ):
        return "benign"
    if "likely benign" in lower or lower == "lb":
        return "likely_benign"
    if "uncertain" in lower or "vus" in lower or "conflicting" in lower:
        return "uncertain"
    return "uncertain"


def severity_rank(level: str) -> int:
    return SEVERITY_ORDER.index(level)


def normalize_source_language(value: str | None) -> str | None:
    normalized = (value or "").strip().lower().replace("_", "-")
    if not normalized:
        return None
    return _LANGUAGE_ALIASES.get(normalized, normalized)


def make_variant_slug(gene: str, variant: str, disease: str) -> str:
    parts = [gene or UNKNOWN_SLUG_VALUE, variant or UNKNOWN_SLUG_VALUE]
    if disease:
        parts.append(disease)
    return ":".join(parts)


def compute_review_status(statuses: Iterable[str]) -> str:
    status_list = list(statuses)
    if "rejected" in status_list:
        return "rejected"
    if "corrected" in status_list:
        return "corrected"
    if "approved" in status_list:
        return "approved"
    return "provisional"


def compute_review_progress(items: list[dict[str, Any]]) -> dict[str, Any]:
    progress = {
        "total": len(items),
        "reviewed": 0,
        "approved": 0,
        "corrected": 0,
        "rejected": 0,
        "provisional": 0,
        "reviewedPercent": 0.0,
    }
    for item in items:
        status = item.get("review_status")
        if status == "approved":
            progress["approved"] += 1
        elif status == "corrected":
            progress["corrected"] += 1
        elif status == "rejected":
            progress["rejected"] += 1
        else:
            progress["provisional"] += 1
    progress["reviewed"] = (
        progress["approved"] + progress["corrected"] + progress["rejected"]
    )
    progress["reviewedPercent"] = (
        progress["reviewed"] / progress["total"] if progress["total"] > 0 else 0.0
    )
    return progress


def expand_variant_sites(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand a result whose ``variant`` lists multiple ';' separated sites.

    Each expanded copy keeps the same group_id / source_document_id so L2
    detail navigation still resolves the underlying evidence group. Mirrors
    ``expandVariantSites`` in ``variantAggregation.ts``.
    """
    raw = result.get("variant") or ""
    if ";" not in raw:
        return [result]
    sites = [v.strip() for v in raw.split(";") if v.strip()]
    if len(sites) <= 1:
        return [result]
    return [{**result, "variant": site} for site in sites]


def _created_at_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _source_document_id_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    text = str(value).strip()
    return text or None


def _result_to_dict(result: EvidenceSearchResult) -> dict[str, Any]:
    """Convert an EvidenceSearchResult model to the dict shape the aggregation
    functions consume. Datetimes become ISO strings so lexicographic sort
    matches the TypeScript behaviour (which sorts ISO strings)."""
    return {
        "group_id": result.group_id,
        "source_document_id": _source_document_id_str(result.source_document_id),
        "title": result.title,
        "pmid": result.pmid,
        "doi": result.doi,
        "source_language": result.source_language,
        "gene": result.gene,
        "variant": result.variant,
        "disease": result.disease,
        "classification": result.classification,
        "field_count": result.field_count,
        "avg_confidence": result.avg_confidence,
        "review_status": result.review_status,
        "canonical_evidence_id": _source_document_id_str(result.canonical_evidence_id),
        "created_at": _created_at_iso(result.created_at),
        "has_full_text": result.has_full_text,
        "has_translation": result.has_translation,
    }


def build_variant_group_document_pairs(
    items: list[dict[str, Any]],
    variant_slug: str,
) -> list[dict[str, str]]:
    seen: set[str] = set()
    pairs: list[dict[str, str]] = []
    for result in items:
        for row in expand_variant_sites(result):
            slug = make_variant_slug(
                row.get("gene") or "",
                row.get("variant") or "",
                row.get("disease") or "",
            )
            if slug != variant_slug:
                continue
            key = f'{row.get("group_id")}\0{row.get("source_document_id")}'
            if key in seen:
                continue
            seen.add(key)
            pairs.append(
                {
                    "groupId": row.get("group_id"),
                    "sourceDocumentId": row.get("source_document_id"),
                }
            )
    return pairs


# ── Aggregation ───────────────────────────────────────────────────────────


@dataclass
class VariantIndexEntry:
    """Aggregated variant row (internal contract). Mirrors the TypeScript
    ``VariantIndexEntry`` interface."""

    variant_slug: str
    gene: str
    variant: str
    disease: str
    classification: str
    classification_level: str
    evidence_group_count: int
    literature_count: int
    avg_confidence: float
    field_count: int
    category_distribution: dict[str, int]
    review_status: str
    review_progress: dict[str, Any]
    created_at: str | None
    group_ids: list[str]
    source_document_ids: list[str]
    source_languages: list[str]
    group_document_pairs: list[dict[str, str]]
    representative: dict[str, Any]


def aggregate_variants(results: list[EvidenceSearchResult]) -> list[VariantIndexEntry]:
    """Aggregate flat evidence search results into variant-centric entries.

    Groups by the ``gene:variant[:disease]`` composite slug. Mirrors
    ``aggregateVariants`` in ``variantAggregation.ts``.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}

    for result in results:
        row_source = _result_to_dict(result)
        for row in expand_variant_sites(row_source):
            gene = row.get("gene") or ""
            variant = row.get("variant") or ""
            disease = row.get("disease") or ""
            slug = make_variant_slug(gene, variant, disease)
            grouped.setdefault(slug, []).append(row)

    entries: list[VariantIndexEntry] = []

    for slug, items in grouped.items():
        first = items[0]
        gene = first.get("gene") or ""
        variant = first.get("variant") or ""
        disease = first.get("disease") or ""
        classification = first.get("classification") or ""

        group_ids = list({r.get("group_id") for r in items if r.get("group_id")})
        source_document_ids = list(
            {r.get("source_document_id") for r in items if r.get("source_document_id")}
        )
        source_languages = sorted(
            {
                normalized
                for r in items
                if (normalized := normalize_source_language(r.get("source_language")))
            }
        )
        group_document_pairs = build_variant_group_document_pairs(items, slug)

        total_fields = sum(r.get("field_count") or 0 for r in items)
        weighted_confidence = sum(
            (r.get("avg_confidence") or 0) * (r.get("field_count") or 0) for r in items
        )
        avg_confidence = weighted_confidence / total_fields if total_fields > 0 else 0

        # Category distribution - approximate from field_count, matching the
        # TypeScript heuristic (distribute across A/B/E).
        category_distribution: dict[str, int] = {key: 0 for key in _CATEGORY_KEYS}
        for item in items:
            field_count = item.get("field_count") or 0
            per_cat = field_count // 3
            remainder = field_count % 3
            category_distribution["A"] += per_cat + (1 if remainder > 0 else 0)
            category_distribution["B"] += per_cat + (1 if remainder > 1 else 0)
            category_distribution["E"] += per_cat

        review_statuses = [r.get("review_status") for r in items]
        classification_level = classify_level(classification)

        created_values = [
            _created_at_iso(r.get("created_at")) for r in items if r.get("created_at")
        ]
        created_at = sorted(created_values)[-1] if created_values else None

        entries.append(
            VariantIndexEntry(
                variant_slug=slug,
                gene=gene,
                variant=variant,
                disease=disease,
                classification=classification,
                classification_level=classification_level,
                evidence_group_count=len(items),
                literature_count=len(source_document_ids),
                avg_confidence=avg_confidence,
                field_count=total_fields,
                category_distribution=category_distribution,
                review_status=compute_review_status(review_statuses),
                review_progress=compute_review_progress(items),
                created_at=created_at,
                group_ids=group_ids,
                source_document_ids=source_document_ids,
                source_languages=source_languages,
                group_document_pairs=group_document_pairs,
                representative=first,
            )
        )

    # Default sort: multi-literature support first, then most recent evidence.
    entries.sort(
        key=lambda e: (
            e.literature_count,
            e.created_at or "",
        ),
        reverse=True,
    )
    return entries


# ── Filter / sort / paginate / stats ──────────────────────────────────────


@dataclass
class VariantIndexFilters:
    gene: str | None = None
    variant: str | None = None
    disease: str | None = None
    classification: str | None = None
    review_status: str | None = None
    source_language: str | None = None
    sort_by: str | None = None
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 24


@dataclass
class VariantIndexStats:
    total_variants: int = 0
    total_evidence_groups: int = 0
    total_literature: int = 0
    avg_confidence: float = 0.0
    classification_distribution: dict[str, int] = field(
        default_factory=lambda: {
            "pathogenic": 0,
            "likely_pathogenic": 0,
            "uncertain": 0,
            "likely_benign": 0,
            "benign": 0,
        }
    )


@dataclass
class VariantIndexCandidates:
    genes: list[str] = field(default_factory=list)
    variants: list[str] = field(default_factory=list)
    diseases: list[str] = field(default_factory=list)


@dataclass
class VariantIndexData:
    items: list[VariantIndexEntry]
    total: int
    page: int
    page_size: int
    stats: VariantIndexStats
    candidates: VariantIndexCandidates


def _cmp_str(a: str, b: str) -> int:
    """Case-insensitive, base-sensitivity comparison mirroring
    ``a.localeCompare(b, undefined, { sensitivity: 'base' })``."""
    return (a.lower() > b.lower()) - (a.lower() < b.lower())


def _sort_entries(
    entries: list[VariantIndexEntry],
    sort_by: str | None,
    sort_order: str,
) -> list[VariantIndexEntry]:
    """Apply user-controlled sort. Mirrors the switch in
    ``filterAndPaginateVariants``. When no ``sort_by`` is set the entries keep
    the default aggregation order (literature count desc, then created_at desc).
    """
    if not sort_by:
        return entries
    mul = 1 if sort_order == "asc" else -1

    def comparator(a: VariantIndexEntry, b: VariantIndexEntry) -> int:
        if sort_by == "gene":
            return mul * _cmp_str(a.gene or "", b.gene or "")
        if sort_by == "variant":
            return mul * _cmp_str(a.variant or "", b.variant or "")
        if sort_by == "disease":
            return mul * _cmp_str(a.disease or "", b.disease or "")
        if sort_by == "classification":
            return mul * (
                severity_rank(a.classification_level)
                - severity_rank(b.classification_level)
            )
        if sort_by == "evidence":
            return mul * (a.evidence_group_count - b.evidence_group_count)
        if sort_by == "refs":
            return mul * (a.literature_count - b.literature_count)
        if sort_by == "confidence":
            return mul * (a.avg_confidence - b.avg_confidence)
        if sort_by == "updated":
            return mul * _cmp_str(a.created_at or "", b.created_at or "")
        return 0

    return sorted(entries, key=cmp_to_key(comparator))


def filter_and_paginate_variants(
    entries: list[VariantIndexEntry],
    filters: VariantIndexFilters,
) -> VariantIndexData:
    """Apply filters, sort, and pagination to aggregated variant entries.

    Mirrors ``filterAndPaginateVariants`` in ``variantAggregation.ts``. Stats
    and candidates are computed over the *full* entry set (pre-filter), matching
    the TypeScript behaviour.
    """
    filtered = entries

    if filters.gene:
        q = filters.gene.lower()
        filtered = [e for e in filtered if filters_gene_match(e, q)]
    if filters.variant:
        q = filters.variant.lower()
        filtered = [e for e in filtered if filters_variant_match(e, q)]
    if filters.disease:
        q = filters.disease.lower()
        filtered = [e for e in filtered if filters_disease_match(e, q)]
    if filters.classification:
        filtered = [e for e in filtered if e.classification_level == filters.classification]
    if filters.review_status:
        filtered = [e for e in filtered if e.review_status == filters.review_status]
    if filters.source_language:
        language = filters.source_language
        filtered = [e for e in filtered if language in e.source_languages]

    filtered = _sort_entries(list(filtered), filters.sort_by, filters.sort_order)

    total = len(filtered)
    start = (filters.page - 1) * filters.page_size
    page_items = filtered[start : start + filters.page_size]

    stats = _compute_stats(entries)
    candidates = _compute_candidates(entries)

    return VariantIndexData(
        items=page_items,
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        stats=stats,
        candidates=candidates,
    )


def filters_gene_match(entry: VariantIndexEntry, q: str) -> bool:
    return q in entry.gene.lower()


def filters_variant_match(entry: VariantIndexEntry, q: str) -> bool:
    return q in entry.variant.lower()


def filters_disease_match(entry: VariantIndexEntry, q: str) -> bool:
    return q in entry.disease.lower()


def _compute_stats(entries: list[VariantIndexEntry]) -> VariantIndexStats:
    group_doc_pairs: set[str] = set()
    distinct_docs: set[str] = set()
    group_confidences: dict[str, float] = {}

    for entry in entries:
        for gid in entry.group_ids:
            if gid not in group_confidences:
                group_confidences[gid] = entry.avg_confidence
            for doc_id in entry.source_document_ids:
                group_doc_pairs.add(f"{gid}\0{doc_id}")
        for doc_id in entry.source_document_ids:
            distinct_docs.add(doc_id)

    distribution = {
        "pathogenic": 0,
        "likely_pathogenic": 0,
        "uncertain": 0,
        "likely_benign": 0,
        "benign": 0,
    }
    for entry in entries:
        distribution[entry.classification_level] = distribution.get(
            entry.classification_level, 0
        ) + 1

    avg_confidence = (
        sum(group_confidences.values()) / len(group_confidences)
        if group_confidences
        else 0.0
    )

    return VariantIndexStats(
        total_variants=len(entries),
        total_evidence_groups=len(group_doc_pairs),
        total_literature=len(distinct_docs),
        avg_confidence=avg_confidence,
        classification_distribution=distribution,
    )


def _compute_candidates(entries: list[VariantIndexEntry]) -> VariantIndexCandidates:
    genes: set[str] = set()
    variants: set[str] = set()
    diseases: set[str] = set()
    for entry in entries:
        if entry.gene:
            genes.add(entry.gene)
        if entry.variant:
            variants.add(entry.variant)
        if entry.disease:
            diseases.add(entry.disease)
    return VariantIndexCandidates(
        genes=sorted(genes),
        variants=sorted(variants),
        diseases=sorted(diseases),
    )
