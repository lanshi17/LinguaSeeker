"""End-to-end tests for three-channel document classification and extraction.

Tests the full chain from fixture document → relevance scan → channel classification
→ field eligibility → extraction status semantics for case_report, functional_study,
and cohort_study channels.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import (
    EVIDENCE_FIELD_SPECS,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.channel_contracts import (
    DocumentEvidenceChannel,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    RelevanceScanOutput,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import (
    CatalogExtractionStage,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map import (
    RelevanceScanStage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load a fixture markdown file."""
    path = _FIXTURES_DIR / name
    return path.read_text(encoding="utf-8")


def _doc_from_fixture(name: str) -> TrackDocument:
    """Create a TrackDocument from a fixture file."""
    text = _load_fixture(name)
    return TrackDocument(
        document_id=f"fixture-{name.replace('.md', '')}",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[ContentBlock(type="text", page_idx=0, text=text)],
    )


def _scan_output(
    channels: list[str],
    confidence: float = 0.85,
    rationale: str = "test classification",
) -> RelevanceScanOutput:
    """Create a RelevanceScanOutput with specified channels."""
    return RelevanceScanOutput(
        relevant=True,
        disease_terms=["ABCA3 deficiency"],
        gene_terms=["ABCA3"],
        variant_terms=["c.1882G>A"],
        selected_channels=channels,
        confidence=confidence,
        rationale=rationale,
        supporting_block_ids=["block_0"],
    )


def _get_status_by_field(items: list[EvidenceItem], field_id: str) -> EvidenceStatus:
    """Get the status of a specific field from a list of evidence items."""
    for item in items:
        if item.field_id == field_id:
            return item.status
    raise ValueError(f"Field {field_id} not found in items")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture,expected_channel,expected_categories,excluded_categories",
    [
        (
            "case_report.md",
            DocumentEvidenceChannel.CASE_REPORT,
            {"A", "B", "C", "H", "J"},  # Variant, Case, Segregation, Contradiction, Authority
            {"F", "I"},  # Functional, Gene Function
        ),
        (
            "functional_study.md",
            DocumentEvidenceChannel.FUNCTIONAL_STUDY,
            {
                "A",
                "E",
                "F",
                "I",
                "H",
                "J",
            },  # Variant, Computational, Functional, Gene Function, Contradiction, Authority
            {"B", "C"},  # Case, Segregation
        ),
        (
            "cohort_study.md",
            DocumentEvidenceChannel.COHORT_STUDY,
            {"A", "D", "G", "H", "J"},  # Variant, Population, Case-Control, Contradiction, Authority
            {"F", "I"},  # Functional, Gene Function
        ),
    ],
)
def test_channel_classification_and_eligibility(
    fixture: str,
    expected_channel: DocumentEvidenceChannel,
    expected_categories: set[str],
    excluded_categories: set[str],
) -> None:
    """Test full chain: fixture → relevance scan → classification → eligibility."""
    # Load fixture
    document = _doc_from_fixture(fixture)

    # Mock provider to return expected channel classification
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output(
        channels=[expected_channel.value],
        confidence=0.85,
        rationale=f"Document classified as {expected_channel.value}",
    )

    # Run relevance scan
    scan_stage = RelevanceScanStage(provider)
    scan_result = scan_stage.run(document)

    # Assert channel classification
    assert scan_result.channel_classification is not None
    assert expected_channel in scan_result.channel_classification.selected_channels
    assert scan_result.channel_classification.confidence == 0.85

    # Assert evidence map
    assert scan_result.evidence_map.relevant is True

    # Run catalog extraction with channel classification
    catalog_provider = MagicMock()
    catalog_provider.invoke_structured.return_value = []
    catalog_stage = CatalogExtractionStage(catalog_provider)

    # Get eligible catalog groups
    chunks = [MagicMock(index=1, total=1, text=document.formatted_text[:500])]
    groups = catalog_stage._eligible_catalog_groups(
        document,
        scan_result.evidence_map,
        chunks,
        channel_classification=scan_result.channel_classification,
    )

    # Collect all eligible field IDs
    eligible_field_ids: set[str] = set()
    for specs in groups.values():
        eligible_field_ids |= {spec.field_id for spec in specs}

    # Assert expected categories are eligible
    for cat in expected_categories:
        cat_fields = {spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id == cat}
        assert cat_fields.issubset(eligible_field_ids), f"Category {cat} should be eligible"

    # Assert excluded categories are not eligible
    for cat in excluded_categories:
        cat_fields = {spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id == cat}
        assert cat_fields.isdisjoint(eligible_field_ids), f"Category {cat} should be excluded"


@pytest.mark.parametrize(
    "fixture,expected_channel,channel_appropriate_field,channel_excluded_field",
    [
        (
            "case_report.md",
            DocumentEvidenceChannel.CASE_REPORT,
            "B.disease_diagnosis",  # Case-appropriate
            "F.assay_type",  # Functional-only
        ),
        (
            "functional_study.md",
            DocumentEvidenceChannel.FUNCTIONAL_STUDY,
            "F.assay_type",  # Functional-appropriate
            "G.odds_ratio",  # Cohort-only
        ),
        (
            "cohort_study.md",
            DocumentEvidenceChannel.COHORT_STUDY,
            "D.allele_frequency",  # Cohort-appropriate
            "F.assay_type",  # Functional-only
        ),
    ],
)
def test_channel_specific_filtering(
    fixture: str,
    expected_channel: DocumentEvidenceChannel,
    channel_appropriate_field: str,
    channel_excluded_field: str,
) -> None:
    """Test that channel-specific fields are included/excluded correctly."""
    document = _doc_from_fixture(fixture)

    # Mock provider for relevance scan
    scan_provider = MagicMock()
    scan_provider.invoke_structured.return_value = _scan_output(channels=[expected_channel.value])

    # Run relevance scan
    scan_stage = RelevanceScanStage(scan_provider)
    scan_result = scan_stage.run(document)

    # Mock provider for catalog extraction (return empty list)
    catalog_provider = MagicMock()
    catalog_provider.invoke_structured.return_value = []
    catalog_stage = CatalogExtractionStage(catalog_provider)

    # Run catalog extraction
    catalog_stage.run(
        document,
        scan_result.evidence_map,
        channel_classification=scan_result.channel_classification,
    )

    # Get the eligibility decision
    decision = catalog_stage.last_eligibility_decision
    assert decision is not None

    # Assert channel-appropriate field is eligible
    assert channel_appropriate_field in decision.allowed_field_ids, (
        f"{channel_appropriate_field} should be eligible for {expected_channel.value}"
    )

    # Assert channel-excluded field is not eligible
    assert channel_excluded_field not in decision.allowed_field_ids, (
        f"{channel_excluded_field} should be excluded for {expected_channel.value}"
    )

    # Assert channel-excluded field is in channel_rejected_field_ids
    assert channel_excluded_field in decision.channel_rejected_field_ids, (
        f"{channel_excluded_field} should be in channel_rejected_field_ids"
    )


@pytest.mark.parametrize(
    "fixture,expected_channel",
    [
        ("case_report.md", DocumentEvidenceChannel.CASE_REPORT),
        ("functional_study.md", DocumentEvidenceChannel.FUNCTIONAL_STUDY),
        ("cohort_study.md", DocumentEvidenceChannel.COHORT_STUDY),
    ],
)
def test_status_semantics(
    fixture: str,
    expected_channel: DocumentEvidenceChannel,
) -> None:
    """Test that eligible absent fields are NOT_FOUND, channel-excluded are NOT_APPLICABLE."""
    document = _doc_from_fixture(fixture)

    # Mock provider for relevance scan
    scan_provider = MagicMock()
    scan_provider.invoke_structured.return_value = _scan_output(channels=[expected_channel.value])

    # Run relevance scan
    scan_stage = RelevanceScanStage(scan_provider)
    scan_result = scan_stage.run(document)

    # Mock provider for catalog extraction (return one found item)
    catalog_provider = MagicMock()
    # Return a single found item for A.gene_symbol
    spec = next(s for s in EVIDENCE_FIELD_SPECS if s.field_id == "A.gene_symbol")
    catalog_provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="A.gene_symbol",
            category=spec.category_id,
            field_name=spec.field_name,
            status=EvidenceStatus.FOUND,
            value="ABCA3",
            confidence=0.9,
        )
    ]
    catalog_stage = CatalogExtractionStage(catalog_provider)

    # Run catalog extraction
    items = catalog_stage.run(
        document,
        scan_result.evidence_map,
        channel_classification=scan_result.channel_classification,
    )

    # Get eligibility decision
    decision = catalog_stage.last_eligibility_decision
    assert decision is not None

    # Simulate backfill with eligibility info
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import (
        EvidenceItemNormalizer,
    )

    normalizer = EvidenceItemNormalizer()
    normalized = normalizer.normalize_grouped(
        items,
        channel_excluded_field_ids=decision.channel_rejected_field_ids,
    )

    # Assert A.gene_symbol is FOUND (was extracted)
    assert _get_status_by_field(normalized, "A.gene_symbol") == EvidenceStatus.FOUND

    # Assert a channel-excluded field is NOT_APPLICABLE
    # Pick a field from an excluded category
    if expected_channel == DocumentEvidenceChannel.CASE_REPORT:
        excluded_field = "F.assay_type"  # Category F not in case_report
    elif expected_channel == DocumentEvidenceChannel.FUNCTIONAL_STUDY:
        excluded_field = "G.odds_ratio"  # Category G not in functional_study
    else:
        excluded_field = "F.assay_type"  # Category F not in cohort_study

    assert _get_status_by_field(normalized, excluded_field) == EvidenceStatus.NOT_APPLICABLE

    # Assert an eligible but absent field is NOT_FOUND
    if expected_channel == DocumentEvidenceChannel.CASE_REPORT:
        eligible_absent = "B.clinical_phenotypes"  # Category B is eligible for case_report
    elif expected_channel == DocumentEvidenceChannel.FUNCTIONAL_STUDY:
        eligible_absent = "F.functional_result"  # Category F is eligible for functional_study
    else:
        eligible_absent = "D.allele_frequency"  # Category D is eligible for cohort_study

    assert _get_status_by_field(normalized, eligible_absent) == EvidenceStatus.NOT_FOUND


@pytest.mark.parametrize(
    "fixture,expected_channel",
    [
        ("case_report.md", DocumentEvidenceChannel.CASE_REPORT),
        ("functional_study.md", DocumentEvidenceChannel.FUNCTIONAL_STUDY),
        ("cohort_study.md", DocumentEvidenceChannel.COHORT_STUDY),
    ],
)
def test_json_round_trip(
    fixture: str,
    expected_channel: DocumentEvidenceChannel,
) -> None:
    """Test that result model can be serialized and reloaded with all metadata."""
    document = _doc_from_fixture(fixture)

    # Mock provider for relevance scan
    scan_provider = MagicMock()
    scan_provider.invoke_structured.return_value = _scan_output(channels=[expected_channel.value])

    # Run relevance scan
    scan_stage = RelevanceScanStage(scan_provider)
    scan_result = scan_stage.run(document)

    # Create a result with channel metadata
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        FieldEligibilitySummary,
    )

    summary = FieldEligibilitySummary(
        eligible_field_count=73,
        channel_excluded_field_count=70,
        target_excluded_field_count=0,
        not_applicable_count=70,
        not_attempted_count=0,
    )

    result = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id=document.document_id,
        track=document.track,
        evidence_map=scan_result.evidence_map,
        channel_classification=scan_result.channel_classification,
        field_eligibility_summary=summary,
    )

    # Serialize to JSON
    json_str = result.model_dump_json()

    # Deserialize
    restored = EvidenceExtractionResult.model_validate_json(json_str)

    # Verify channel classification
    assert restored.channel_classification is not None
    assert expected_channel in restored.channel_classification.selected_channels
    assert restored.channel_classification.confidence == 0.85

    # Verify field eligibility summary
    assert restored.field_eligibility_summary is not None
    assert restored.field_eligibility_summary.eligible_field_count == 73
    assert restored.field_eligibility_summary.channel_excluded_field_count == 70

    # Verify evidence map
    assert restored.evidence_map is not None
    assert restored.evidence_map.relevant is True

    # Verify output schema unchanged
    assert isinstance(restored, EvidenceExtractionResult)
    assert restored.status == EvidenceExtractionStatus.COMPLETED
