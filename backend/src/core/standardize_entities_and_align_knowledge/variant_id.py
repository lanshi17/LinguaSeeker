"""Deterministic internal variant identifiers for unmatched variants."""
from __future__ import annotations

import hashlib

from src.core.standardize_entities_and_align_knowledge.normalizers import (
    normalize_gene_symbol,
    normalize_variant_text,
)

_PREFIX = "internal:variant:"


def make_internal_variant_id(normalized_hgvs: str, gene_symbol: str) -> str:
    """Return a stable internal id for a variant with no ClinVar match.

    The id is a deterministic sha256 digest of the normalized gene symbol and
    HGVS text, so repeated mentions of the same unmatched variant collapse onto
    one ``normalized_entities`` row. An empty gene symbol is represented as a
    sentinel ``_`` so the digest still distinguishes gene-less variants from
    gene-bearing ones.

    Args:
        normalized_hgvs: The variant's raw HGVS text (e.g. ``c.4748T>G``).
        gene_symbol: The candidate gene symbol, or an empty string when absent.

    Returns:
        A ``internal:variant:<sha8>`` identifier, never ``None``.
    """
    gene = normalize_gene_symbol(gene_symbol) if gene_symbol else "_"
    hgvs = normalize_variant_text(normalized_hgvs)
    digest = hashlib.sha256(f"{gene}|{hgvs}".encode("utf-8")).hexdigest()[:8]
    return f"{_PREFIX}{digest}"
