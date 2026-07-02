"""Build a Rett/MECP2 variant-centered annotation candidate manifest.

The manifest uses this package's reviewed ``ground_truth/`` dataset as the
primary source. It joins each ``rett_xxx`` annotation entry back to the unified
benchmark via ``unified/*/expected.json::original_entry_id`` when available.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from .manifest import load_manifest

RETT_ANNOTATION_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_ROOT = RETT_ANNOTATION_ROOT.parent.parent
DATA_ROOT = BENCHMARK_ROOT / "data"
ANNOTATION_ROOT = RETT_ANNOTATION_ROOT / "ground_truth"
UNIFIED_ROOT = DATA_ROOT / "ground_truth" / "unified"
DEFAULT_OUTPUT = DATA_ROOT / "manifests" / "rett_multilingual_variant_annotation_candidates.json"

IDENTITY_FIELDS = {
    "A.gene_symbol",
    "A.variant_hgvs_c",
    "A.variant_hgvs_p",
    "A.variant_type",
}
CORE_CLINICAL_FIELDS = {
    "B.sex",
    "B.age_of_onset",
    "B.hpo_terms",
    "B.clinical_phenotypes",
    "C.de_novo_status",
}
TABLE_KEYWORDS_RE = re.compile(
    r"\b(Table|Patient|Age|Onset|Mutation|Genotype|Phenotype)\b|表|표|患者|환자|变异|突变|돌연변이",
    re.IGNORECASE,
)
RETT_RE = re.compile(
    r"Rett|RTT|Rett综合征|雷特综合征|レット|レツト|레트|Ретт|síndrome\s+de\s+Rett|sindrome\s+de\s+Rett",
    re.IGNORECASE,
)
MECP2_RE = re.compile(r"\bMECP2\b|MeCP2|Mecp2", re.IGNORECASE)
HGVS_C_RE = re.compile(r"c\.\s*\d+(?:[+_\-\d]*)?\s*[ACGT]?\s*>\s*[ACGT]?|c\.\s*\d+[A-Za-z]*", re.IGNORECASE)
HGVS_P_RE = re.compile(
    r"p\.\s*(?:[A-Z][a-z]{2}\d+(?:[A-Z][a-z]{2}|Ter|\*)|[A-Z]\d+(?:[A-Z]|X|\*))",
    re.IGNORECASE,
)
BARE_PROTEIN_RE = re.compile(r"\b[A-Z]\d{2,4}(?:X|Ter|\*|[A-Z])\b")

AA3_TO_1 = {
    "Ala": "A",
    "Arg": "R",
    "Asn": "N",
    "Asp": "D",
    "Cys": "C",
    "Gln": "Q",
    "Glu": "E",
    "Gly": "G",
    "His": "H",
    "Ile": "I",
    "Leu": "L",
    "Lys": "K",
    "Met": "M",
    "Phe": "F",
    "Pro": "P",
    "Ser": "S",
    "Thr": "T",
    "Trp": "W",
    "Tyr": "Y",
    "Val": "V",
    "Ter": "X",
}


class ExistingGoldPayload(TypedDict):
    """Unified benchmark gold fields already attached to a Rett entry."""

    unified_entry_id: str
    existing_gold_count: int
    existing_clinical_gold_count: int
    existing_core_clinical_gold_count: int
    existing_gold_field_ids: list[str]
    existing_core_clinical_field_ids: list[str]


class ParserCheckPayload(TypedDict):
    """Lightweight source.md feature check."""

    source_md_chars: int
    has_mecp2: bool
    has_rett: bool
    has_variant_pattern: bool
    table_likely: bool
    source_type_hint: Literal["text", "table_likely", "scanned_or_empty"]


class QualityGatePayload(TypedDict):
    """Candidate-level quality gates for manual annotation triage."""

    is_native_non_en: bool
    has_mecp2_rett: bool
    has_variant_mention: bool
    markdown_available: bool
    source_pdf_available: bool
    provenance_locatable: bool


class ManifestEntryPayload(TypedDict, total=False):
    """One Rett annotation candidate entry."""

    annotation_entry_id: str
    original_entry_id: str
    unified_entry_id: str | None
    in_unified_benchmark: bool
    source_md_path: str
    source_pdf_path: str | None
    source_image_dir: str | None
    language: str
    title: str
    tier_assignment: Literal["Tier 1", "Tier 2", "Tier 3"]
    candidate_role: str
    parser_check: ParserCheckPayload
    quality_gates: QualityGatePayload
    hit_surface_loci: list[str]
    hit_biological_variant_units: list[str]
    matched_aliases_by_unit: dict[str, list[str]]
    variant_mentions: list[str]
    existing_gold_count: int
    existing_clinical_gold_count: int
    existing_core_clinical_gold_count: int
    existing_gold_field_ids: list[str]
    existing_core_clinical_field_ids: list[str]
    priority: Literal["CRITICAL_MANUAL", "HIGH", "MEDIUM", "LOW"]
    annotation_status: Literal["pending", "skipped"]


class VariantAliasUnitPayload(TypedDict):
    """Serialized biological variant unit and its surface aliases."""

    unit_id: str
    canonical_hgvs_c: str
    canonical_hgvs_p: str
    aliases: list[str]
    source_entry_ids: list[str]


class ManifestSummaryPayload(TypedDict):
    """Manifest-level summary counts."""

    total_entries: int
    in_unified_benchmark: int
    annotation_only_entries: int
    with_variant_hits: int
    critical_manual: int
    by_language: dict[str, int]
    by_tier: dict[str, int]
    by_priority: dict[str, int]


class ManifestPayload(TypedDict):
    """Top-level manifest file."""

    manifest_id: str
    created_at: str
    annotation_root: str
    unified_root: str
    rett_ground_truth_root: str
    summary: ManifestSummaryPayload
    variant_alias_units: list[VariantAliasUnitPayload]
    entries: list[ManifestEntryPayload]


@dataclass
class UnifiedGoldIndex:
    """Join helper from Rett original entry ids to unified benchmark ids."""

    unified_id_by_original: dict[str, str] = field(default_factory=dict)
    gold_by_original: dict[str, ExistingGoldPayload] = field(default_factory=dict)


@dataclass
class RettExpectedIndex:
    """Loaded Rett expected.json records keyed by original Rett id."""

    # Raw expected.json records are schema-variable source data, not a stable
    # cross-module return contract.
    expected_by_entry_id: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class VariantAliasUnit:
    """In-memory biological variant unit."""

    unit_id: str
    canonical_hgvs_c: str = ""
    canonical_hgvs_p: str = ""
    aliases: set[str] = field(default_factory=set)
    source_entry_ids: set[str] = field(default_factory=set)

    def to_payload(self) -> VariantAliasUnitPayload:
        """Serialize the alias unit."""

        return {
            "unit_id": self.unit_id,
            "canonical_hgvs_c": self.canonical_hgvs_c,
            "canonical_hgvs_p": self.canonical_hgvs_p,
            "aliases": sorted(self.aliases),
            "source_entry_ids": sorted(self.source_entry_ids),
        }


@dataclass
class VariantAliasIndex:
    """Alias index used for warm-start matching against source.md."""

    units: dict[str, VariantAliasUnit] = field(default_factory=dict)


def _read_json(path: Path) -> Any:
    """Read JSON from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_hgvs_c(value: str) -> str:
    """Normalize a nucleotide HGVS surface form for matching."""

    value = value.strip()
    value = re.sub(r"^[A-Z]{2}_\d+(?:\.\d+)?:", "", value)
    value = re.sub(r"^NM_\d+(?:\.\d+)?:", "", value)
    value = re.sub(r"\s+", "", value)
    return value


def _normalize_hgvs_p_key(value: str) -> str:
    """Return a one-letter protein key such as R168X."""

    value = value.strip()
    value = re.sub(r"^[A-Z]{2}_\d+(?:\.\d+)?:", "", value)
    value = re.sub(r"^NP_\d+(?:\.\d+)?:", "", value)
    value = re.sub(r"^p\.", "", value)
    value = re.sub(r"\s+", "", value)
    value = value.replace("Ter", "X").replace("*", "X")
    match = re.fullmatch(r"([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|X)", value)
    if match:
        ref, pos, alt = match.groups()
        return f"{AA3_TO_1.get(ref, ref[0])}{pos}{AA3_TO_1.get(alt, alt[0])}"
    match = re.fullmatch(r"([A-Z])(\d+)([A-Z]|X)", value)
    if match:
        return "".join(match.groups())
    return value


def _protein_aliases(value: str) -> set[str]:
    """Generate common protein aliases from one p. surface form."""

    key = _normalize_hgvs_p_key(value)
    aliases = {value.strip(), value.strip().removeprefix("p."), f"p.{key}", key}
    if key.endswith("X"):
        aliases.add(key[:-1] + "*")
        aliases.add(f"p.{key[:-1]}*")
    return {alias for alias in aliases if alias}


def _safe_unit_part(value: str) -> str:
    """Create a stable, readable unit-id fragment."""

    return re.sub(r"[^A-Za-z0-9_.>*-]+", "", value)


def _load_unified_gold_index(unified_root: Path) -> UnifiedGoldIndex:
    """Load unified Rett mapping and existing gold field counts."""

    index = UnifiedGoldIndex()
    for expected_path in sorted(unified_root.glob("*/expected.json")):
        expected = cast(dict[str, Any], _read_json(expected_path))
        if expected.get("source_dataset") != "rett":
            continue
        original_entry_id = str(expected.get("original_entry_id") or "")
        if not original_entry_id:
            continue
        unified_entry_id = expected_path.parent.name
        evidence = cast(list[dict[str, Any]], expected.get("expected_evidence") or [])
        field_ids = [str(item.get("field_id") or "") for item in evidence]
        clinical_field_ids = [field_id for field_id in field_ids if field_id not in IDENTITY_FIELDS]
        core_clinical_field_ids = [field_id for field_id in clinical_field_ids if field_id in CORE_CLINICAL_FIELDS]
        index.unified_id_by_original[original_entry_id] = unified_entry_id
        index.gold_by_original[original_entry_id] = {
            "unified_entry_id": unified_entry_id,
            "existing_gold_count": len(field_ids),
            "existing_clinical_gold_count": len(clinical_field_ids),
            "existing_core_clinical_gold_count": len(core_clinical_field_ids),
            "existing_gold_field_ids": sorted(set(field_ids)),
            "existing_core_clinical_field_ids": sorted(set(core_clinical_field_ids)),
        }
    return index


def _load_rett_expected_index(rett_root: Path) -> RettExpectedIndex:
    """Load original Rett expected.json records."""

    index = RettExpectedIndex()
    for expected_path in sorted(rett_root.glob("*/expected.json")):
        expected = cast(dict[str, Any], _read_json(expected_path))
        entry_id = str(expected.get("entry_id") or expected_path.parent.name)
        index.expected_by_entry_id[entry_id] = expected
    return index


def _variant_values(expected: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract hgvs_c/hgvs_p pairs from one Rett expected record."""

    pairs: list[tuple[str, str]] = []
    for variant in cast(list[dict[str, Any]], expected.get("variants") or []):
        hgvs_c = _normalize_hgvs_c(str(variant.get("hgvs_c") or ""))
        hgvs_p = str(variant.get("hgvs_p") or "").strip()
        if hgvs_c or hgvs_p:
            pairs.append((hgvs_c, hgvs_p))
    return pairs


def _build_variant_alias_index(rett_index: RettExpectedIndex) -> VariantAliasIndex:
    """Build biological variant units from Rett expected variants."""

    alias_index = VariantAliasIndex()
    grouped_records: dict[str, list[tuple[str, str, str]]] = {}

    for entry_id, expected in rett_index.expected_by_entry_id.items():
        for hgvs_c, hgvs_p in _variant_values(expected):
            p_key = _normalize_hgvs_p_key(hgvs_p) if hgvs_p else ""
            if p_key:
                group_key = f"p:{p_key}"
            elif hgvs_c:
                group_key = f"c:{hgvs_c}"
            else:
                continue
            grouped_records.setdefault(group_key, []).append((entry_id, hgvs_c, hgvs_p))

    for group_key, records in grouped_records.items():
        canonical_c = next((hgvs_c for _, hgvs_c, _ in records if hgvs_c), "")
        canonical_p = next((hgvs_p for _, _, hgvs_p in records if hgvs_p), "")
        if canonical_c:
            p_part = _safe_unit_part(_normalize_hgvs_p_key(canonical_p)) if canonical_p else "p_unknown"
            unit_id = f"MECP2_{_safe_unit_part(canonical_c)}_{p_part}"
        else:
            unit_id = f"MECP2_p.{_safe_unit_part(_normalize_hgvs_p_key(canonical_p))}"
        unit = VariantAliasUnit(
            unit_id=unit_id,
            canonical_hgvs_c=canonical_c,
            canonical_hgvs_p=canonical_p,
        )
        for entry_id, hgvs_c, hgvs_p in records:
            unit.source_entry_ids.add(entry_id)
            if hgvs_c:
                unit.aliases.add(hgvs_c)
            if hgvs_p:
                unit.aliases.update(_protein_aliases(hgvs_p))
        alias_index.units[group_key] = unit

    return alias_index


def _compact_text(value: str) -> str:
    """Normalize text for high-recall alias scanning."""

    return re.sub(r"\s+", "", value).lower()


def _scan_variant_units(content: str, alias_index: VariantAliasIndex) -> tuple[list[str], list[str], dict[str, list[str]]]:
    """Scan source text for known biological variant aliases."""

    compact = _compact_text(content)
    hit_units: list[str] = []
    hit_surface_loci: set[str] = set()
    matched_aliases_by_unit: dict[str, list[str]] = {}

    for unit in alias_index.units.values():
        matched_aliases = []
        for alias in sorted(unit.aliases, key=len, reverse=True):
            if not alias:
                continue
            if _compact_text(alias) in compact:
                matched_aliases.append(alias)
        if matched_aliases:
            hit_units.append(unit.unit_id)
            hit_surface_loci.update(matched_aliases)
            matched_aliases_by_unit[unit.unit_id] = sorted(set(matched_aliases))

    return sorted(set(hit_units)), sorted(hit_surface_loci), matched_aliases_by_unit


def _extract_variant_mentions(content: str) -> list[str]:
    """Extract broad surface variant mentions from source text."""

    mentions = set()
    for regex in (HGVS_C_RE, HGVS_P_RE, BARE_PROTEIN_RE):
        for match in regex.findall(content):
            if isinstance(match, tuple):
                mentions.add("".join(match))
            else:
                mentions.add(str(match).strip())
    return sorted(mention for mention in mentions if mention)


def _table_likely(content: str) -> bool:
    """Lightweight table-likelihood heuristic for annotation triage."""

    table_keyword_hits = len(TABLE_KEYWORDS_RE.findall(content))
    markdown_table_lines = sum(1 for line in content.splitlines() if line.count("|") >= 2)
    repeated_spacing_hits = len(re.findall(r" {3,}", content))
    return table_keyword_hits >= 5 or markdown_table_lines >= 5 or repeated_spacing_hits >= 20


def _first_markdown_title(content: str) -> str:
    """Extract a provisional title from the first Markdown heading."""

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            if title:
                return title
    return ""


def _make_entry(
    annotation_dir: Path,
    unified_index: UnifiedGoldIndex,
    rett_index: RettExpectedIndex,
    alias_index: VariantAliasIndex,
) -> ManifestEntryPayload:
    """Build one manifest entry from an annotation directory."""

    annotation_entry_id = annotation_dir.name
    expected = rett_index.expected_by_entry_id.get(annotation_entry_id, {})
    source_md_path = annotation_dir / "source.md"
    source_pdf_path = annotation_dir / "source.pdf"
    source_image_dir = annotation_dir / "images"
    content = source_md_path.read_text(encoding="utf-8")

    unified_entry_id = unified_index.unified_id_by_original.get(annotation_entry_id)
    gold = unified_index.gold_by_original.get(annotation_entry_id)
    language = str(expected.get("source_language") or "")
    title = str(expected.get("source_title") or "") or _first_markdown_title(content)
    hit_units, hit_surface_loci, matched_aliases_by_unit = _scan_variant_units(content, alias_index)
    variant_mentions = _extract_variant_mentions(content)
    has_mecp2 = bool(MECP2_RE.search(content))
    has_rett = bool(RETT_RE.search(content))
    has_variant_pattern = bool(variant_mentions)
    table_likely = _table_likely(content)
    source_md_chars = len(content)
    source_type_hint: Literal["text", "table_likely", "scanned_or_empty"]
    if source_md_chars < 200:
        source_type_hint = "scanned_or_empty"
    elif table_likely:
        source_type_hint = "table_likely"
    else:
        source_type_hint = "text"

    is_native_non_en = language not in {"", "en", "default_en"}
    in_unified_benchmark = unified_entry_id is not None
    if hit_units and is_native_non_en:
        tier_assignment: Literal["Tier 1", "Tier 2", "Tier 3"] = "Tier 1"
        candidate_role = "non_english_variant_evidence_candidate"
    elif hit_units and language == "en":
        tier_assignment = "Tier 2"
        candidate_role = "english_baseline_comparator"
    else:
        tier_assignment = "Tier 3"
        candidate_role = "supplement_or_negative_filter_candidate"

    if annotation_entry_id == "rett_067" or (hit_units and language in {"zh", "ko", "ja"}):
        priority: Literal["CRITICAL_MANUAL", "HIGH", "MEDIUM", "LOW"] = "CRITICAL_MANUAL"
    elif hit_units:
        priority = "HIGH"
    elif has_mecp2 and has_rett:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    empty_gold: ExistingGoldPayload = {
        "unified_entry_id": unified_entry_id or "",
        "existing_gold_count": 0,
        "existing_clinical_gold_count": 0,
        "existing_core_clinical_gold_count": 0,
        "existing_gold_field_ids": [],
        "existing_core_clinical_field_ids": [],
    }
    gold_payload = gold or empty_gold

    return {
        "annotation_entry_id": annotation_entry_id,
        "original_entry_id": annotation_entry_id,
        "unified_entry_id": unified_entry_id,
        "in_unified_benchmark": in_unified_benchmark,
        "source_md_path": str(source_md_path),
        "source_pdf_path": str(source_pdf_path) if source_pdf_path.exists() else None,
        "source_image_dir": str(source_image_dir) if source_image_dir.exists() else None,
        "language": language,
        "title": title,
        "tier_assignment": tier_assignment,
        "candidate_role": candidate_role,
        "parser_check": {
            "source_md_chars": source_md_chars,
            "has_mecp2": has_mecp2,
            "has_rett": has_rett,
            "has_variant_pattern": has_variant_pattern,
            "table_likely": table_likely,
            "source_type_hint": source_type_hint,
        },
        "quality_gates": {
            "is_native_non_en": is_native_non_en,
            "has_mecp2_rett": has_mecp2 and has_rett,
            "has_variant_mention": bool(hit_units),
            "markdown_available": source_md_path.exists(),
            "source_pdf_available": source_pdf_path.exists(),
            "provenance_locatable": source_md_path.exists() and (source_pdf_path.exists() or source_image_dir.exists()),
        },
        "hit_surface_loci": hit_surface_loci,
        "hit_biological_variant_units": hit_units,
        "matched_aliases_by_unit": matched_aliases_by_unit,
        "variant_mentions": variant_mentions[:100],
        "existing_gold_count": gold_payload["existing_gold_count"],
        "existing_clinical_gold_count": gold_payload["existing_clinical_gold_count"],
        "existing_core_clinical_gold_count": gold_payload["existing_core_clinical_gold_count"],
        "existing_gold_field_ids": gold_payload["existing_gold_field_ids"],
        "existing_core_clinical_field_ids": gold_payload["existing_core_clinical_field_ids"],
        "priority": priority,
        "annotation_status": "pending" if hit_units else "skipped",
    }


def build_manifest(
    annotation_root: Path = ANNOTATION_ROOT,
    rett_root: Path = ANNOTATION_ROOT,
    unified_root: Path = UNIFIED_ROOT,
) -> ManifestPayload:
    """Build the Rett multilingual variant annotation manifest payload."""

    unified_index = _load_unified_gold_index(unified_root)
    rett_index = _load_rett_expected_index(rett_root)
    alias_index = _build_variant_alias_index(rett_index)
    source_manifest = load_manifest(annotation_root / "manifest.json")
    ground_truth_entry_ids = {
        entry.entry_id
        for entry in source_manifest.entries
        if entry.status == "ground_truth"
    }
    if not ground_truth_entry_ids:
        ground_truth_entry_ids = {
            annotation_dir.name
            for annotation_dir in annotation_root.glob("rett_*")
            if annotation_dir.is_dir()
        }
    entries = []
    for entry_id in sorted(ground_truth_entry_ids):
        annotation_dir = annotation_root / entry_id
        if annotation_dir.is_dir() and (annotation_dir / "source.md").exists():
            entries.append(_make_entry(annotation_dir, unified_index, rett_index, alias_index))
    by_language = Counter(entry["language"] for entry in entries)
    by_tier = Counter(entry["tier_assignment"] for entry in entries)
    by_priority = Counter(entry["priority"] for entry in entries)
    summary: ManifestSummaryPayload = {
        "total_entries": len(entries),
        "in_unified_benchmark": sum(1 for entry in entries if entry["in_unified_benchmark"]),
        "annotation_only_entries": sum(1 for entry in entries if not entry["in_unified_benchmark"]),
        "with_variant_hits": sum(1 for entry in entries if entry["hit_biological_variant_units"]),
        "critical_manual": sum(1 for entry in entries if entry["priority"] == "CRITICAL_MANUAL"),
        "by_language": dict(sorted(by_language.items())),
        "by_tier": dict(sorted(by_tier.items())),
        "by_priority": dict(sorted(by_priority.items())),
    }
    return {
        "manifest_id": "rett_multilingual_variant_annotation_candidates",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "annotation_root": str(annotation_root),
        "unified_root": str(unified_root),
        "rett_ground_truth_root": str(rett_root),
        "summary": summary,
        "variant_alias_units": [unit.to_payload() for unit in alias_index.units.values()],
        "entries": entries,
    }


def write_manifest(payload: ManifestPayload, output_path: Path) -> None:
    """Write manifest payload to disk."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotation-root", type=Path, default=ANNOTATION_ROOT)
    parser.add_argument("--rett-root", type=Path, default=ANNOTATION_ROOT)
    parser.add_argument("--unified-root", type=Path, default=UNIFIED_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = build_manifest(
        annotation_root=args.annotation_root,
        rett_root=args.rett_root,
        unified_root=args.unified_root,
    )
    write_manifest(payload, args.output)
    print(f"Wrote {len(payload['entries'])} Rett annotation candidates to {args.output}")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
