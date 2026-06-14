"""Tests for target-safe context pack contracts."""
from __future__ import annotations

import dataclasses

from src.core.standardize_entities_and_align_knowledge.context_pack.contracts import (
    DiseaseContext,
    GeneContext,
    TargetContextPack,
)


def test_target_context_pack_exposes_only_safe_target_fields() -> None:
    pack = TargetContextPack(
        entry_id="clingen_000",
        gene=GeneContext(symbol="AARS1", hgnc_id="HGNC:20", aliases=("AARS1",)),
        disease=DiseaseContext(
            label="Charcot-Marie-Tooth disease axonal type 2N",
            mondo_id="MONDO:0013212",
            aliases=("Charcot-Marie-Tooth disease axonal type 2N",),
            ancestor_labels=(),
        ),
        moi="AD",
        source_pmid="41743127",
        source_pmc="PMC12929025",
    )

    payload = dataclasses.asdict(pack)

    assert payload == {
        "entry_id": "clingen_000",
        "gene": {
            "symbol": "AARS1",
            "hgnc_id": "HGNC:20",
            "aliases": ("AARS1",),
        },
        "disease": {
            "label": "Charcot-Marie-Tooth disease axonal type 2N",
            "mondo_id": "MONDO:0013212",
            "aliases": ("Charcot-Marie-Tooth disease axonal type 2N",),
            "ancestor_labels": (),
        },
        "moi": "AD",
        "source_pmid": "41743127",
        "source_pmc": "PMC12929025",
    }
    assert "classification" not in payload
    assert "expected_evidence" not in payload


def test_context_contracts_are_immutable() -> None:
    pack = TargetContextPack(
        entry_id="clingen_000",
        gene=GeneContext(symbol="AARS1", hgnc_id=None, aliases=()),
        disease=DiseaseContext(label="CMT2N", mondo_id=None, aliases=(), ancestor_labels=()),
        moi="AD",
        source_pmid=None,
        source_pmc=None,
    )

    assert dataclasses.is_dataclass(pack)
    assert pack.__dataclass_params__.frozen is True
