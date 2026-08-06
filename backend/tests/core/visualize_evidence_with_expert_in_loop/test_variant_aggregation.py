"""Tests for the server-side variant aggregation port.

These cases mirror ``frontend/tests/evidence-db/variantAggregation.test.tsx``
to guard against behavioural drift between the Python port and the original
TypeScript implementation.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid5

import pytest

from src.core.visualize_evidence_with_expert_in_loop.contracts import EvidenceSearchResult
from src.core.visualize_evidence_with_expert_in_loop.variant_aggregation import (
    VariantIndexFilters,
    aggregate_variants,
    build_variant_group_document_pairs,
    filter_and_paginate_variants,
)

JOINED_VARIANT = "c.316C>T; c.502C>T; c.808C>T; c.913insT; c.1126C>T"
JOINED_GROUP_ID = f"gene=MECP2|variant={JOINED_VARIANT}"
NAMESPACE = UUID("00000000-0000-0000-0000-000000000000")


def doc_id(name: str) -> UUID:
    return uuid5(NAMESPACE, name)


def make_result(**overrides: object) -> EvidenceSearchResult:
    defaults: dict[str, object] = {
        "group_id": "gene=MECP2|variant=c.316C>T",
        "source_document_id": doc_id("doc-1"),
        "gene": "MECP2",
        "variant": "c.316C>T",
        "disease": "Rett syndrome",
        "classification": "Pathogenic",
        "field_count": 10,
        "avg_confidence": 0.9,
        "review_status": "provisional",
        "canonical_evidence_id": doc_id("ev-1"),
    }
    defaults.update(overrides)
    return EvidenceSearchResult(**defaults)  # type: ignore[arg-type]


def test_single_variant_keeps_one_row() -> None:
    entries = aggregate_variants([make_result()])
    assert len(entries) == 1
    assert entries[0].variant == "c.316C>T"
    assert entries[0].gene == "MECP2"


def test_splits_multi_variant_into_five_rows() -> None:
    entries = aggregate_variants(
        [make_result(variant=JOINED_VARIANT, group_id=JOINED_GROUP_ID)]
    )
    assert len(entries) == 5
    assert sorted(e.variant for e in entries) == [
        "c.1126C>T",
        "c.316C>T",
        "c.502C>T",
        "c.808C>T",
        "c.913insT",
    ]
    for entry in entries:
        assert entry.gene == "MECP2"
        assert entry.classification_level == "pathogenic"
        # All split rows share the original group_id so L2 detail resolves.
        assert entry.group_ids == [JOINED_GROUP_ID]


def test_does_not_split_without_semicolon() -> None:
    entries = aggregate_variants([make_result(variant="c.316C>T")])
    assert len(entries) == 1


def test_aggregates_shared_split_variant_from_different_groups() -> None:
    entries = aggregate_variants(
        [
            make_result(
                variant="c.316C>T; c.502C>T",
                group_id="gene=MECP2|variant=c.316C>T; c.502C>T",
                source_document_id=doc_id("doc-a"),
            ),
            make_result(
                variant="c.316C>T; c.808C>T",
                group_id="gene=MECP2|variant=c.316C>T; c.808C>T",
                source_document_id=doc_id("doc-b"),
            ),
        ]
    )
    c316 = next(e for e in entries if e.variant == "c.316C>T")
    assert c316.evidence_group_count == 2
    assert len(c316.group_ids) == 2
    assert len(c316.source_document_ids) == 2
    assert c316.group_document_pairs == [
        {
            "groupId": "gene=MECP2|variant=c.316C>T; c.502C>T",
            "sourceDocumentId": str(doc_id("doc-a")),
        },
        {
            "groupId": "gene=MECP2|variant=c.316C>T; c.808C>T",
            "sourceDocumentId": str(doc_id("doc-b")),
        },
    ]


def test_computes_review_progress_from_grouped_rows() -> None:
    entries = aggregate_variants(
        [
            make_result(
                group_id="group-a",
                source_document_id=doc_id("doc-a"),
                review_status="approved",
            ),
            make_result(
                group_id="group-b",
                source_document_id=doc_id("doc-b"),
                review_status="corrected",
            ),
            make_result(
                group_id="group-c",
                source_document_id=doc_id("doc-c"),
                review_status="rejected",
            ),
            make_result(
                group_id="group-d",
                source_document_id=doc_id("doc-d"),
                review_status="provisional",
            ),
        ]
    )

    assert len(entries) == 1
    progress = entries[0].review_progress
    assert progress["reviewed"] == 3
    assert progress["reviewedPercent"] == pytest.approx(0.75)
    assert progress["rejected"] == 1


def test_preserves_availability_fields_on_representative() -> None:
    entries = aggregate_variants(
        [make_result(has_full_text=True, has_translation=True)]
    )
    assert entries[0].representative["has_full_text"] is True
    assert entries[0].representative["has_translation"] is True


def test_aggregates_source_languages_sorted() -> None:
    entries = aggregate_variants(
        [
            make_result(source_document_id=doc_id("doc-a"), source_language="zh"),
            make_result(source_document_id=doc_id("doc-b"), source_language="en"),
        ]
    )
    assert entries[0].source_languages == ["en", "zh"]


def test_default_sort_multi_literature_then_newest() -> None:
    entries = aggregate_variants(
        [
            make_result(
                group_id="group-old-single",
                source_document_id=doc_id("doc-old-single"),
                variant="c.100A>G",
                created_at=datetime(2026, 1, 1),
            ),
            make_result(
                group_id="group-new-single",
                source_document_id=doc_id("doc-new-single"),
                variant="c.200A>G",
                created_at=datetime(2026, 2, 1),
            ),
            make_result(
                group_id="group-multi-a",
                source_document_id=doc_id("doc-multi-a"),
                variant="c.300A>G",
                created_at=datetime(2026, 1, 15),
            ),
            make_result(
                group_id="group-multi-b",
                source_document_id=doc_id("doc-multi-b"),
                variant="c.300A>G",
                created_at=datetime(2026, 1, 16),
            ),
        ]
    )

    assert [e.variant for e in entries] == ["c.300A>G", "c.200A>G", "c.100A>G"]


def test_gene_only_evidence_becomes_unknown_variant_row() -> None:
    entries = aggregate_variants(
        [
            make_result(
                group_id="gene=MECP2|variant=__missing__",
                gene="MECP2",
                variant=None,
                disease="Rett syndrome",
            )
        ]
    )

    assert len(entries) == 1
    assert entries[0].variant_slug == "MECP2:unknown:Rett syndrome"
    assert entries[0].gene == "MECP2"
    assert entries[0].variant == ""
    assert entries[0].group_document_pairs == [
        {
            "groupId": "gene=MECP2|variant=__missing__",
            "sourceDocumentId": str(doc_id("doc-1")),
        }
    ]


def test_stats_not_inflated_by_split_rows() -> None:
    entries = aggregate_variants(
        [make_result(variant=JOINED_VARIANT, group_id=JOINED_GROUP_ID)]
    )
    data = filter_and_paginate_variants(entries, VariantIndexFilters(page=1, page_size=50))
    # Five variant rows, but only one underlying evidence group and document.
    assert data.stats.total_variants == 5
    assert data.stats.total_evidence_groups == 1
    assert data.stats.total_literature == 1


def test_filter_by_individual_split_variant() -> None:
    entries = aggregate_variants(
        [make_result(variant=JOINED_VARIANT, group_id=JOINED_GROUP_ID)]
    )
    data = filter_and_paginate_variants(
        entries, VariantIndexFilters(page=1, page_size=50, variant="c.502C>T")
    )
    assert len(data.items) == 1
    assert data.items[0].variant == "c.502C>T"
    assert data.total == 1


def test_filter_by_source_language() -> None:
    entries = aggregate_variants(
        [
            make_result(
                group_id="group-zh",
                source_document_id=doc_id("doc-zh"),
                source_language="zh",
                variant="c.316C>T",
            ),
            make_result(
                group_id="group-en",
                source_document_id=doc_id("doc-en"),
                source_language="en",
                variant="c.502C>T",
            ),
        ]
    )

    data = filter_and_paginate_variants(
        entries, VariantIndexFilters(page=1, page_size=50, source_language="zh")
    )

    assert len(data.items) == 1
    assert data.items[0].source_languages == ["zh"]


def test_build_pairs_without_cartesian_product() -> None:
    rows = [
        {
            "group_id": "group-a",
            "source_document_id": str(doc_id("doc-1")),
            "gene": "FLCN",
            "variant": "c.1177-5_-3delCTC",
            "disease": "Birt-Hogg-Dube syndrome",
        },
        {
            "group_id": "group-b",
            "source_document_id": str(doc_id("doc-2")),
            "gene": "FLCN",
            "variant": "c.1177-5_-3delCTC",
            "disease": "Birt-Hogg-Dube syndrome",
        },
    ]

    assert build_variant_group_document_pairs(
        rows, "FLCN:c.1177-5_-3delCTC:Birt-Hogg-Dube syndrome"
    ) == [
        {"groupId": "group-a", "sourceDocumentId": str(doc_id("doc-1"))},
        {"groupId": "group-b", "sourceDocumentId": str(doc_id("doc-2"))},
    ]


def test_pagination_returns_only_current_page() -> None:
    entries = aggregate_variants(
        [make_result(variant=f"c.{n}A>G", group_id=f"g-{n}") for n in range(10)]
    )
    data = filter_and_paginate_variants(
        entries, VariantIndexFilters(page=2, page_size=3)
    )
    assert len(data.items) == 3
    assert data.total == 10
    assert data.page == 2


def test_candidates_collect_distinct_sorted_values() -> None:
    entries = aggregate_variants(
        [
            make_result(gene="BRCA2", variant="c.2A>G", disease="Cancer"),
            make_result(gene="BRCA1", variant="c.1A>G", disease="Cancer"),
        ]
    )
    data = filter_and_paginate_variants(entries, VariantIndexFilters(page=1, page_size=50))
    assert data.candidates.genes == ["BRCA1", "BRCA2"]
    assert data.candidates.variants == ["c.1A>G", "c.2A>G"]
    assert data.candidates.diseases == ["Cancer"]
