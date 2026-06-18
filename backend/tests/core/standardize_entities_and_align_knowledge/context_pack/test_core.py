"""Tests for target-safe context pack loading."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from src.core.standardize_entities_and_align_knowledge.context_pack.core import (
    build_context_pack_from_expected_json,
    build_context_pack_from_runtime_target,
)


def test_build_context_pack_from_expected_json_uses_only_safe_fields(tmp_path: Path) -> None:
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps(
            {
                "entry_id": "clingen_000",
                "gene_symbol": "AARS1",
                "hgnc_id": "HGNC:20",
                "disease_label": "Charcot-Marie-Tooth disease axonal type 2N",
                "mondo_id": "MONDO:0013212",
                "moi": "AD",
                "classification": "Definitive",
                "expected_evidence": [
                    {"field_id": "A.gene_disease_relationship", "value": "causative"}
                ],
                "source_pmid": "41743127",
                "source_pmc": "PMC12929025",
            }
        ),
        encoding="utf-8",
    )

    pack = build_context_pack_from_expected_json(expected_path)
    payload_text = json.dumps(dataclasses.asdict(pack), ensure_ascii=False)

    assert pack.entry_id == "clingen_000"
    assert pack.gene.symbol == "AARS1"
    assert pack.gene.hgnc_id == "HGNC:20"
    assert pack.disease.label == "Charcot-Marie-Tooth disease axonal type 2N"
    assert pack.disease.mondo_id == "MONDO:0013212"
    assert pack.moi == "AD"
    assert pack.source_pmid == "41743127"
    assert pack.source_pmc == "PMC12929025"
    assert "classification" not in payload_text
    assert "Definitive" not in payload_text
    assert "expected_evidence" not in payload_text
    assert "causative" not in payload_text


def test_build_context_pack_from_runtime_target_uses_safe_target_metadata() -> None:
    pack = build_context_pack_from_runtime_target(
        entry_id="clingen_024",
        gene_symbol=" tlr5 ",
        disease_label="Systemic lupus erythematosus (susceptibility)",
        hgnc_id="HGNC:11851",
        mondo_id="MONDO:0007915",
        moi="AD",
        source_pmid="12345678",
        source_pmc="PMC123456",
    )

    assert pack.entry_id == "clingen_024"
    assert pack.gene.symbol == "TLR5"
    assert pack.gene.hgnc_id == "HGNC:11851"
    assert pack.gene.aliases == ("TLR5",)
    assert pack.disease.label == "Systemic lupus erythematosus (susceptibility)"
    assert pack.disease.mondo_id == "MONDO:0007915"
    assert pack.disease.aliases == (
        "Systemic lupus erythematosus (susceptibility)",
        "systemic lupus erythematosus (susceptibility)",
        "Systemic lupus erythematosus",
        "systemic lupus erythematosus",
    )
    assert pack.moi == "AD"
    assert pack.source_pmid == "12345678"
    assert pack.source_pmc == "PMC123456"


def test_build_context_pack_adds_deterministic_disease_aliases(tmp_path: Path) -> None:
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps(
            {
                "entry_id": "clingen_alias",
                "gene_symbol": "GENE1",
                "disease_label": "Example syndrome (type 1)",
                "moi": "AR",
            }
        ),
        encoding="utf-8",
    )

    pack = build_context_pack_from_expected_json(expected_path)

    assert pack.disease.aliases == (
        "Example syndrome (type 1)",
        "example syndrome (type 1)",
        "Example syndrome",
        "example syndrome",
    )


def test_build_context_pack_harvests_source_abbreviation_aliases(tmp_path: Path) -> None:
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps(
            {
                "entry_id": "clingen_020",
                "gene_symbol": "GJA1",
                "disease_label": "congenital heart disease",
                "moi": "UD",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "source.md").write_text(
        "Tetralogy of Fallot (TOF) is the most common cyanotic congenital heart disease with "
        "right ventricular outflow tract (RVOT) obstruction.",
        encoding="utf-8",
    )

    pack = build_context_pack_from_expected_json(expected_path)

    assert "TOF" in pack.disease.aliases
    assert "RVOT" not in pack.disease.aliases


def test_build_context_pack_harvests_safe_source_stem_aliases(tmp_path: Path) -> None:
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps(
            {
                "entry_id": "clingen_024",
                "gene_symbol": "TLR5",
                "disease_label": "systemic lupus erythematosus, susceptibility to, 1",
                "moi": "UD",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "source.md").write_text(
        "The review discusses systemic lupus erythematosus (SLE) and Toll-like receptor 7 (TLR7) signaling.",
        encoding="utf-8",
    )

    pack = build_context_pack_from_expected_json(expected_path)

    assert "systemic lupus erythematosus" in pack.disease.aliases
    assert "SLE" in pack.disease.aliases
    assert "TLR7" not in pack.disease.aliases


def test_build_context_pack_harvests_source_observed_mondo_disease_aliases(tmp_path: Path) -> None:
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps(
            {
                "entry_id": "clingen_010",
                "gene_symbol": "AP1G1",
                "disease_label": "complex neurodevelopmental disorder",
                "mondo_id": "MONDO:0100038",
                "moi": "AD",
                "classification": "Definitive",
                "expected_evidence": [
                    {"field_id": "A.gene_disease_relationship", "value": "causative"}
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "source.md").write_text(
        "Variants in the AP1G1 gene have recently been associated with "
        "Usmani-Riazuddin syndrome (USRISD), a very rare human genetic disorder. "
        "AP1G1 neurodevelopmental disorder can present with epilepsy and developmental delay.",
        encoding="utf-8",
    )

    pack = build_context_pack_from_expected_json(expected_path)
    aliases = {alias.casefold() for alias in pack.disease.aliases}

    assert "Usmani-Riazuddin syndrome" in pack.disease.aliases
    assert "USRISD" in pack.disease.aliases
    assert "epilepsy" not in aliases
    assert "developmental delay" not in aliases
    assert "Usmani-Riazuddin syndrome, autosomal dominant" not in pack.disease.aliases
    assert "Usmani-Riazuddin syndrome, autosomal recessive" not in pack.disease.aliases
