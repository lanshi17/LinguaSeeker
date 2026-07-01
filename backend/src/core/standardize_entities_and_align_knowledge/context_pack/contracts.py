"""Typed contracts for target-safe context packs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeneContext:
    """Safe target gene context available before evidence extraction."""

    symbol: str
    hgnc_id: str | None
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class DiseaseContext:
    """Safe target disease context available before evidence extraction."""

    label: str
    mondo_id: str | None
    aliases: tuple[str, ...]
    ancestor_labels: tuple[str, ...]


@dataclass(frozen=True)
class TargetContextPack:
    """No-leakage context pack for benchmark and runtime verification."""

    entry_id: str
    gene: GeneContext
    disease: DiseaseContext
    moi: str
    source_pmid: str | None
    source_pmc: str | None
