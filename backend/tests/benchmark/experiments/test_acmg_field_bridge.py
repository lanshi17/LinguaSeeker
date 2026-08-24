"""Tests for the Stage-0 catalog-field bridge and MECP2 allele registry."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from benchmark.experiments.acmg_multilingual.canonical_alleles import (
    EventAlleleBinding,
    assert_event_bindings,
    assert_hard_non_identities,
    load_canonical_allele_registry,
)
from benchmark.experiments.acmg_multilingual.cli import _parse_args
from benchmark.experiments.acmg_multilingual.direct_inference import load_direct_inference_table
from benchmark.experiments.acmg_multilingual.field_bridge import (
    GATE_FIELD_IDS,
    FieldFact,
    load_and_verify_field_bridge,
    required_field_ids,
)


def _repository_root() -> Path:
    """Return the monorepo root that contains benchmark/ and backend/."""
    return Path(__file__).resolve().parents[4]


def test_gate_field_ids_exist_in_product_catalog() -> None:
    """Bridge field_ids must remain a subset of the live extraction catalog."""
    from src.core.evidence_extraction.domain.catalog import EVIDENCE_FIELD_SPECS

    catalog_ids = {spec.field_id for spec in EVIDENCE_FIELD_SPECS}
    assert GATE_FIELD_IDS <= catalog_ids


def test_frozen_field_bridge_matches_on_disk_sources() -> None:
    """On-disk catalog quotes, parentage absence, and allele bindings stay aligned."""
    repository_root = _repository_root()
    _table, inference, _registry, report = load_and_verify_field_bridge(
        reviewed_root=repository_root / "benchmark/experiments/acmg_multilingual/reviewed",
    )
    assert report.allele_mismatches == 0
    assert report.verified_on_disk_events == report.on_disk_events == 31
    assert len(inference.events) == 32


def test_r168x_aliases_share_one_registry_allele() -> None:
    """c.502C>T and c.538C>T must resolve to the same ClinVar allele."""
    table = load_direct_inference_table()
    registry = load_canonical_allele_registry()
    by_id = {event.event_id: event for event in table.events}
    assert by_id["rett_006_F_R168X"].canonical_allele_id == "VCV000011828"
    assert by_id["rett_007_case2_R180X"].canonical_allele_id == "VCV000011828"
    assert by_id["rett_004_R168X"].canonical_allele_id == "VCV000011828"
    allele = next(item for item in registry.alleles if item.allele_id == "VCV000011828")
    writings = {(alias.hgvs_c, alias.hgvs_p) for alias in allele.aliases}
    assert ("c.502C>T", "p.Arg168Ter") in writings
    assert ("c.538C>T", "p.Arg180Ter") in writings


def test_c844del_is_not_c844c_to_t() -> None:
    """Frameshift c.844del and nonsense c.844C>T stay split."""
    registry = load_canonical_allele_registry()
    assert_hard_non_identities(registry)
    table = load_direct_inference_table()
    frameshift = next(event for event in table.events if event.event_id == "rett_007_case4_R282fs")
    nonsense = next(event for event in table.events if event.event_id == "rett_006_D_R270X")
    assert frameshift.canonical_allele_id == "VCV000143702"
    assert nonsense.canonical_allele_id == "VCV000011815"
    assert frameshift.canonical_allele_id != nonsense.canonical_allele_id


def test_c194delc_is_adjacent_not_identical() -> None:
    """Paper c.194delC is not ClinVar c.195del and not LOVD c.194C>G."""
    table = load_direct_inference_table()
    event = next(item for item in table.events if item.event_id == "rett_084_194delC")
    assert event.canonical_allele_id == "unmatched_c.194delC"
    assert event.clinvar_vcv == "VCV001076185"
    assert event.clinvar_match == "coordinate_near"
    registry = load_canonical_allele_registry()
    assert_event_bindings(
        registry,
        (
            EventAlleleBinding(
                event_id=event.event_id,
                canonical_allele_id=event.canonical_allele_id,
                clinvar_vcv=event.clinvar_vcv,
                clinvar_match=event.clinvar_match,
            ),
        ),
    )


def test_coordinate_near_cannot_reuse_vcv_as_allele_id() -> None:
    """A near ClinVar record must not be treated as the paper allele."""
    registry = load_canonical_allele_registry()
    with pytest.raises(ValueError, match="coordinate_near"):
        assert_event_bindings(
            registry,
            (
                EventAlleleBinding(
                    event_id="bad_near",
                    canonical_allele_id="VCV001076185",
                    clinvar_vcv="VCV001076185",
                    clinvar_match="coordinate_near",
                ),
            ),
        )


def test_pm6_requires_parentage_absence_field() -> None:
    """Granting PM6 always requires the parentage-confirmed absence check."""
    table = load_direct_inference_table()
    event = next(item for item in table.events if item.event_id == "rett_011_P237R")
    assert "C.parentage_confirmed" in required_field_ids(event)
    assert "C.maternal_genotype" in required_field_ids(event)


def test_absent_field_rejects_spans() -> None:
    """Absence facts cannot hide a quote that the source does not support."""
    with pytest.raises(ValidationError, match="absent"):
        FieldFact.model_validate(
            {
                "field_id": "C.parentage_confirmed",
                "presence": "absent",
                "spans": [{"line": 1, "quote": "亲子鉴定", "language": "zh"}],
            }
        )


def test_span_recovery_covers_on_disk_pm6_field_bridge_gates() -> None:
    """Deterministic recovery should populate the PM6 catalog gates on reviewed sources."""
    from src.core.evidence_extraction.contracts import (
        EvidenceItem,
        EvidenceStatus,
        ExtractionTarget,
        SourceLocation,
        Track,
        TrackDocument,
    )
    from src.core.evidence_extraction.domain.normalization import AcmgEvidenceValueNormalizer
    from src.core.evidence_extraction.postprocess.target_span_recovery import TargetSpanFieldRecovery

    repository_root = _repository_root()
    table = load_direct_inference_table()
    reviewed_root = repository_root / "benchmark/experiments/acmg_multilingual/reviewed"
    missing: list[str] = []
    for event in table.events:
        if event.materialization_status != "on_disk" or "PM6" not in event.expected_codes:
            continue
        text = (reviewed_root / event.source_relative_path).read_text(encoding="utf-8")
        document = TrackDocument(
            document_id=event.event_id,
            track=Track.ORIGINAL,
            formatted_text=text,
            page_spans=[],
            extraction_target=ExtractionTarget(
                gene_symbol=event.gene,
                disease_name="Rett syndrome",
                variant_hgvs_c=event.paper_hgvs_c,
                variant_hgvs_p=event.paper_hgvs_p,
            ),
        )
        seed = EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene symbol",
            status=EvidenceStatus.FOUND,
            value="MECP2",
            confidence=0.9,
            group_id=f"gene=MECP2|variant={event.paper_hgvs_c}",
            source=SourceLocation(
                context_type="text",
                context_ref="seed",
                text_snippet=event.paper_hgvs_c,
            ),
            target_variant=event.paper_hgvs_c,
        )
        recovered = TargetSpanFieldRecovery().recover(document, [seed])
        normalized, _issues = AcmgEvidenceValueNormalizer().normalize(recovered)
        values = {
            item.field_id: item.value
            for item in normalized
            if item.status == EvidenceStatus.FOUND
        }
        for field_id in (
            "C.de_novo_status",
            "C.maternal_genotype",
            "C.paternal_genotype",
            "C.parentage_confirmed",
        ):
            if field_id == "C.de_novo_status" and values.get(field_id) != "de_novo":
                missing.append(f"{event.event_id}:{field_id}={values.get(field_id)}")
            elif field_id == "C.parentage_confirmed" and values.get(field_id) != "not_confirmed":
                missing.append(f"{event.event_id}:{field_id}={values.get(field_id)}")
            elif field_id.endswith("_genotype") and not values.get(field_id):
                missing.append(f"{event.event_id}:{field_id}=missing")
    assert missing == []


def test_cli_check_field_bridge_parses_roots() -> None:
    """The field-bridge CLI keeps cases, alleles, facts, and sources separate."""
    args = _parse_args(
        (
            "check-field-bridge",
            "--cases",
            "cases.json",
            "--alleles",
            "alleles.json",
            "--facts",
            "facts.json",
            "--reviewed-root",
            "reviewed",
            "--report",
            "report.json",
        )
    )
    assert args.cases == Path("cases.json")
    assert args.alleles == Path("alleles.json")
    assert args.facts == Path("facts.json")
    assert args.reviewed_root == Path("reviewed")
    assert args.report == Path("report.json")
