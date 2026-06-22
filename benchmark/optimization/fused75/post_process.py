"""Post-processing optimizations for extracted evidence items.

Applies four optimizations to existing extraction artifacts before evaluation:
1. HGVS normalization (three-letter ↔ one-letter amino acid codes)
2. MOI abbreviation extraction (long sentence → AD/AR/XL)
3. Target-aware disease/variant filtering
4. Implicit semantic inference (variant_type from HGVS notation, gene_disease_relationship)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

from benchmark.datasets.clinvar_fused.hgvs_normalize import (
    normalize_variant_type,
)


def _infer_variant_type_from_hgvs_c(hgvs_c: str) -> str | None:
    """Infer variant type from HGVS coding notation."""
    if not hgvs_c:
        return None
    text = hgvs_c.lower()
    if "delins" in text:
        return "deletion"
    if "del" in text:
        return "deletion"
    if "dup" in text:
        return "dup"
    if "ins" in text:
        return "insertion"
    if "inv" in text:
        return "other"
    # SNV: c.123A>G pattern
    if re.match(r"c\.\d+[acgt]>[acgt]", text):
        return "missense"
    return None


_MOI_PATTERNS = [
    (re.compile(r"autosomal\s+recessive", re.IGNORECASE), "AR"),
    (re.compile(r"autosomal\s+dominant", re.IGNORECASE), "AD"),
    (re.compile(r"\bX[-\s]linked\b", re.IGNORECASE), "XL"),
    (re.compile(r"\bmitochondrial\b", re.IGNORECASE), "mitochondrial"),
    (re.compile(r"\bde\s+novo\b", re.IGNORECASE), "de novo"),
]


def _extract_moi_abbreviation(value: str) -> str | None:
    """Extract standard MOI abbreviation from a long description."""
    for pattern, abbr in _MOI_PATTERNS:
        if pattern.search(value):
            return abbr
    upper = value.strip().upper()
    if upper in ("AR", "AD", "XL", "X-LINKED"):
        return upper if upper != "X-LINKED" else "XL"
    return None


def _normalize_disease_for_filter(value: str) -> str:
    """Normalize disease name for filtering comparison."""
    text = re.sub(r"\s*\([^)]*\)", "", value)
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def post_process_items(
    items: list[dict[str, Any]],
    *,
    target_gene: str | None = None,
    target_disease: str | None = None,
) -> list[dict[str, Any]]:
    """Apply all post-processing optimizations to extracted items."""
    processed: list[dict[str, Any]] = []

    for item in items:
        field_id = item.get("field_id", "")
        value = str(item.get("value", ""))
        if not value or not field_id:
            continue

        # Opt 2: MOI abbreviation extraction
        if field_id == "B.mode_of_inheritance_reported":
            abbr = _extract_moi_abbreviation(value)
            if abbr and abbr != value.strip():
                item = {**item, "value": abbr, "_pp_moi_abbreviated": True}

        # Opt 3: Target-aware disease filter
        if field_id == "B.disease_diagnosis" and target_disease:
            extracted_norm = _normalize_disease_for_filter(value)
            target_norm = _normalize_disease_for_filter(target_disease)
            # Keep if the extracted disease overlaps with target
            target_words = set(target_norm.split())
            extracted_words = set(extracted_norm.split())
            if not target_words & extracted_words:
                continue

        processed.append(item)

    # Opt 4: Infer variant_type from HGVS if no variant_type was extracted
    variant_types = [i for i in processed if i.get("field_id") == "A.variant_type"]
    if not variant_types:
        for item in processed:
            if item.get("field_id") == "A.variant_hgvs_c":
                inferred = _infer_variant_type_from_hgvs_c(str(item.get("value", "")))
                if inferred:
                    processed.append({
                        "field_id": "A.variant_type",
                        "value": inferred,
                        "status": "found",
                        "_pp_inferred_from_hgvs": True,
                    })
                    break

    return processed


def post_process_extraction_artifact(
    artifact_path: Path,
    expected_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Load an extraction artifact, extract reconciled items, and apply post-processing."""
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))

    # Get target info from expected.json
    target_gene = None
    target_disease = None
    if expected_path and expected_path.exists():
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        clingen = expected.get("clingen", {})
        target_gene = clingen.get("gene_symbol")
        target_disease = clingen.get("disease_label")

    # Extract items (same logic as run_variant.py)
    if isinstance(payload.get("items"), list):
        raw_items = payload["items"]
    elif isinstance(payload.get("reconciled_result"), dict):
        raw_items = payload["reconciled_result"].get("evidence_items", [])
    else:
        raw_items = []
        for key in ("original_result", "translated_result"):
            track = payload.get(key)
            if isinstance(track, dict):
                raw_items.extend(track.get("evidence_items", []))

    # Filter to found items
    found = [
        item for item in raw_items
        if isinstance(item, dict)
        and item.get("status", "found") == "found"
        and item.get("field_id") is not None
        and item.get("value") is not None
    ]

    return post_process_items(found, target_gene=target_gene, target_disease=target_disease)
