"""Gold-standard literature filter for the unified benchmark dataset.

Scans every entry across the four source datasets (``clingen``,
``clinvar_fused``, ``rett``, ``parkinson``) and applies five quality gates to
decide which literature is genuinely suitable to act as a gold-standard
document together with its annotated ``expected.json``. Entries that pass every
gate become the curated ``gold_standard_selection.json`` -- the input for the
subsequent merge into one standard dataset.

Gates (an entry must pass all five):

1. ``source_integrity``     -- ``source.md`` is a real, single, parseable
   article (not an erratum/correction, not a multi-article concatenation, and
   above a minimal stripped-text length).
2. ``standardization_ids``  -- ``expected_standardization`` carries a valid
   ``HGNC:`` gene id and ``MONDO:`` disease id. Parkinson entries store the
   bare gene symbol; these are back-filled from the project HGNC terminology
   file and pass when a stable id resolves.
3. ``article_alignment``     -- the source article actually mentions the
   expected gene (approved symbol or any HGNC alias / previous symbol) so the
   linked literature is topically relevant.
4. ``verifiable_source``     -- the literature is locatable: a PMID, DOI, a
   reachable ``source_pdf_url``, or a local ``source_pdf_path`` that exists.
5. ``cross_dataset_dedup``   -- no duplicate literature across datasets
   (matched on normalized DOI, PMID, or title). When a clash occurs the entry
   with the richest evidence wins and the rest are excluded.

The filter never mutates the original ground-truth data; it only writes a
report and a curated selection index.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from loguru import logger

from benchmark.core.paths import (
    BENCHMARK_ROOT,
    DATA_ROOT,
    GROUND_TRUTH_ROOT,
    RAW_PDF_ROOT,
)

__all__ = [
    "DATASET_DIRS",
    "GoldStandardFilterReportPayload",
    "GoldStandardSelectionEntry",
    "build_gold_standard_selection",
    "format_summary",
    "main",
]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Source datasets scanned by the filter, in canonical order. ``merged_73`` is
# an incomplete earlier merge shim (only a ``selection.json``, empty entry
# dirs) and is deliberately excluded.
DATASET_DIRS: tuple[str, ...] = ("clingen", "clinvar_fused", "rett", "parkinson")

# Per-dataset gold-source provenance recorded on every selection entry.
DATASET_PROVENANCE: dict[str, dict[str, str]] = {
    "clingen": {
        "gold_source": "database",
        "annotation_provenance": "clingen_gene_validity_csv",
    },
    "clinvar_fused": {
        "gold_source": "database",
        "annotation_provenance": "clingen_clinvar_join",
    },
    "rett": {
        "gold_source": "article",
        "annotation_provenance": "ai_auto_review",
    },
    "parkinson": {
        "gold_source": "article",
        "annotation_provenance": "xlsx_auto_convert",
    },
}

HGNC_TERMINOLOGY_FILE = BENCHMARK_ROOT.parent / "database" / "terminology_database" / "hgnc" / "hgnc_complete_set.txt"

# Gate thresholds, calibrated against the scanned corpus.
MIN_STRIPPED_TEXT_CHARS = 1500
MULTI_ARTICLE_MIN_DISTINCT_TITLES = 4
TITLE_LIKE_MIN_LEN = 25
ERRATUM_RE = re.compile(
    r"^\s*#*\s*(errata|erratum|correction|corrigendum|retraction|author correction)\b",
    re.IGNORECASE,
)
HGNC_RE = re.compile(r"^HGNC:\d+$")
MONDO_RE = re.compile(r"^MONDO:\d+$")

REPORTS_DIR = DATA_ROOT / "reports" / "curation"
SELECTION_PATH = DATA_ROOT / "ground_truth" / "gold_standard_selection.json"


# ---------------------------------------------------------------------------
# Contracts (rule 22: no bare dict return types)
# ---------------------------------------------------------------------------


class GateDetail(TypedDict, total=False):
    """Diagnostic detail emitted by a single gate."""

    source_md_bytes: int
    stripped_text_chars: int
    distinct_title_like_h1: int
    detected_kind: str  # single_article | multi_article_corpus | erratum | fragment
    gene_id: str
    disease_id: str
    backfilled_hgnc_id: str
    gene_present: bool
    local_pdf_exists: bool
    resolved_pdf_path: str
    gene_matched_via: str
    has_pmid: bool
    has_doi: bool
    has_pdf_url: bool
    local_pdf_exists: bool
    dedup_key: str
    dedup_winner: str
    dedup_group: list[str]


class GateResultPayload(TypedDict):
    gate: str
    passed: bool
    reason: str
    detail: GateDetail


class GoldStandardSelectionEntry(TypedDict, total=False):
    """One curated entry in the gold-standard selection index."""

    unified_id: str
    original_entry_id: str
    source_dataset: str
    gold_source: str
    annotation_provenance: str
    gene_symbol: str
    hgnc_id: str
    disease_label: str
    mondo_id: str
    moi: str
    source_pmid: str | None
    source_doi: str | None
    source_title: str
    source_year: str
    source_language: str
    source_pdf_path: str | None
    evidence_field_ids: list[str]
    evidence_count: int
    evaluation_layers: list[str]
    multilingual_sources: list[str]
    expected_json_path: str
    source_md_path: str
    backfilled: dict[str, str]
    gate_notes: str


class EntryReportPayload(TypedDict):
    entry_id: str
    source_dataset: str
    gold_source: str
    annotation_provenance: str
    gene_symbol: str
    disease_label: str
    overall_passed: bool
    fail_reasons: list[str]
    gates: list[GateResultPayload]
    selection: GoldStandardSelectionEntry | None


class DedupGroupPayload(TypedDict):
    key: str
    key_type: str
    members: list[str]
    winner: str
    excluded: list[str]


class GoldStandardFilterReportPayload(TypedDict):
    schema_version: str
    generated_at: str
    summary: dict[str, int]
    per_dataset: dict[str, dict[str, int]]
    dedup_groups: list[DedupGroupPayload]
    entries: list[EntryReportPayload]


@dataclass(frozen=True)
class GateResult:
    """Result of one gate for one entry."""

    gate: str
    passed: bool
    reason: str
    detail: GateDetail = field(default_factory=dict)


@dataclass(frozen=True)
class EntryRecord:
    """Normalized view of one ground-truth entry loaded from disk."""

    entry_id: str
    source_dataset: str
    entry_dir: Path
    expected: dict[str, object]
    meta: dict[str, object]
    source_md: str
    source_md_path: Path


# ---------------------------------------------------------------------------
# HGNC gene alias lookup
# ---------------------------------------------------------------------------


def load_gene_alias_map(genes: set[str]) -> dict[str, dict[str, object]]:
    """Resolve ``gene_symbol -> {approved, hgnc_id, aliases, previous}`` from
    the project HGNC terminology file.

    Matches on approved symbol, alias symbols, and previous symbols so that
    renamed genes (e.g. ``GBA`` -> approved ``GBA1``) still resolve.
    """
    aliases: dict[str, dict[str, object]] = {}
    if not HGNC_TERMINOLOGY_FILE.exists():
        logger.warning("HGNC terminology file not found: {}", HGNC_TERMINOLOGY_FILE)
        return aliases
    with HGNC_TERMINOLOGY_FILE.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            approved = (row.get("Approved symbol") or "").strip()
            if not approved:
                continue
            alias_symbols = [s.strip() for s in (row.get("Alias symbols") or "").split(",") if s.strip()]
            previous_symbols = [s.strip() for s in (row.get("Previous symbols") or "").split(",") if s.strip()]
            known = {approved, *alias_symbols, *previous_symbols}
            for gene in genes:
                if gene in known:
                    aliases[gene] = {
                        "approved": approved,
                        "hgnc_id": f"HGNC:{(row.get('HGNC ID') or '').strip()}",
                        "aliases": alias_symbols,
                        "previous": previous_symbols,
                    }
    unresolved = genes - set(aliases)
    if unresolved:
        logger.warning("HGNC unresolved for {} genes: {}", len(unresolved), sorted(unresolved))
    return aliases


# ---------------------------------------------------------------------------
# Entry loading
# ---------------------------------------------------------------------------


def _dataset_root(dataset: str) -> Path:
    if dataset == "clingen":
        return GROUND_TRUTH_ROOT
    return DATA_ROOT / "ground_truth" / dataset


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_markdown(md: str) -> str:
    """Return ``md`` with markup/boilerplate removed for length heuristics."""
    lines = []
    for line in md.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("|") or stripped.startswith("```"):
            continue
        # Drop leading markdown emphasis/heading markers.
        cleaned = re.sub(r"^[#>\-\*\+\s]+", "", stripped)
        if cleaned:
            lines.append(cleaned)
    return " ".join(lines)


def _title_like_h1_lines(md: str) -> list[str]:
    """Distinct H1 lines that look like paper titles (long, sentence-like)."""
    titles: list[str] = []
    for line in md.splitlines():
        if not (line.startswith("# ") and not line.startswith("## ")):
            continue
        text = line[2:].strip()
        if len(text) < TITLE_LIKE_MIN_LEN or text.endswith(":"):
            continue
        titles.append(text)
    # Deduplicate exact repeats (e.g. repeated all-caps section headers).
    seen: set[str] = set()
    distinct: list[str] = []
    for title in titles:
        key = title.lower()
        if key not in seen:
            seen.add(key)
            distinct.append(title)
    return distinct


def load_entries() -> tuple[list[EntryRecord], dict[str, dict[str, object]]]:
    """Load every entry across the four datasets and the gene alias map."""
    records: list[EntryRecord] = []
    genes: set[str] = set()
    for dataset in DATASET_DIRS:
        root = _dataset_root(dataset)
        if not root.exists():
            logger.warning("dataset root missing: {}", root)
            continue
        for entry_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            expected_path = entry_dir / "expected.json"
            source_path = entry_dir / "source.md"
            if not expected_path.exists() or not source_path.exists():
                logger.debug("skipping incomplete entry: {}", entry_dir.name)
                continue
            try:
                expected = _load_json(expected_path)
            except json.JSONDecodeError as exc:
                logger.warning("invalid expected.json in {}: {}", entry_dir.name, exc)
                continue
            meta: dict[str, object] = {}
            meta_path = entry_dir / "meta.json"
            if meta_path.exists():
                try:
                    meta = _load_json(meta_path)
                except json.JSONDecodeError:
                    meta = {}
            source_md = source_path.read_text(encoding="utf-8", errors="replace")
            records.append(
                EntryRecord(
                    entry_id=str(expected.get("entry_id") or entry_dir.name),
                    source_dataset=dataset,
                    entry_dir=entry_dir,
                    expected=expected,
                    meta=meta,
                    source_md=source_md,
                    source_md_path=source_path,
                )
            )
            gene = expected.get("gene_symbol")
            if isinstance(gene, str):
                genes.add(gene)
            clingen = expected.get("clingen")
            if isinstance(clingen, dict):
                nested_gene = clingen.get("gene_symbol")
                if isinstance(nested_gene, str):
                    genes.add(nested_gene)
    alias_map = load_gene_alias_map(genes)
    logger.info(
        "loaded {} entries across {} datasets ({} unique genes)",
        len(records),
        len(DATASET_DIRS),
        len(genes),
    )
    return records, alias_map


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


def _gene_symbol(record: EntryRecord) -> str:
    gene = record.expected.get("gene_symbol")
    if isinstance(gene, str) and gene:
        return gene
    clingen = record.expected.get("clingen")
    if isinstance(clingen, dict):
        nested = clingen.get("gene_symbol")
        if isinstance(nested, str) and nested:
            return nested
    return ""


def _gene_hgnc_id(record: EntryRecord) -> str:
    """Return the gene HGNC id declared in ``expected_standardization.gene``."""
    std = record.expected.get("expected_standardization")
    if isinstance(std, dict):
        gene = std.get("gene")
        if isinstance(gene, str) and HGNC_RE.match(gene):
            return gene
    top = record.expected.get("hgnc_id")
    if isinstance(top, str) and HGNC_RE.match(top):
        return top
    return ""


def _disease_mondo_id(record: EntryRecord) -> str:
    std = record.expected.get("expected_standardization")
    if isinstance(std, dict):
        disease = std.get("disease")
        if isinstance(disease, str) and MONDO_RE.match(disease):
            return disease
    top = record.expected.get("mondo_id")
    if isinstance(top, str) and MONDO_RE.match(top):
        return top
    return ""


def _disease_label(record: EntryRecord) -> str:
    """Disease label, falling back to the nested ``clingen`` block (clinvar_fused)."""
    label = record.expected.get("disease_label")
    if isinstance(label, str) and label.strip():
        return label
    clingen = record.expected.get("clingen")
    if isinstance(clingen, dict):
        nested = clingen.get("disease_label")
        if isinstance(nested, str) and nested.strip():
            return nested
    return ""


def _moi(record: EntryRecord) -> str:
    """Mode of inheritance, falling back to the nested ``clingen`` block."""
    moi = record.expected.get("moi")
    if isinstance(moi, str) and moi.strip():
        return moi
    clingen = record.expected.get("clingen")
    if isinstance(clingen, dict):
        nested = clingen.get("moi")
        if isinstance(nested, str) and nested.strip():
            return nested
    return ""


def _source_language(record: EntryRecord) -> str:
    """Source article language, with meta.json fallback and an English default
    for the ClinGen / ClinVar-fused datasets (English PMC full text)."""
    lang = record.expected.get("source_language")
    if isinstance(lang, str) and lang.strip():
        return lang.strip()
    meta_lang = record.meta.get("language")
    if isinstance(meta_lang, str) and meta_lang.strip():
        return meta_lang.strip()
    if record.source_dataset in {"clingen", "clinvar_fused"}:
        return "en"
    return ""


def gate_source_integrity(record: EntryRecord) -> GateResult:
    """Gate 1: source.md is a real, single, parseable article."""
    detail: GateDetail = {}
    raw_bytes = len(record.source_md.encode("utf-8"))
    stripped = _strip_markdown(record.source_md)
    stripped_chars = len(stripped)
    distinct_titles = _title_like_h1_lines(record.source_md)
    detail["source_md_bytes"] = raw_bytes
    detail["stripped_text_chars"] = stripped_chars
    detail["distinct_title_like_h1"] = len(distinct_titles)

    if ERRATUM_RE.match(record.source_md.lstrip()[:80]):
        detail["detected_kind"] = "erratum"
        return GateResult(
            "source_integrity",
            False,
            "source.md is an erratum/correction notice, not a research article",
            detail,
        )
    if stripped_chars < MIN_STRIPPED_TEXT_CHARS:
        detail["detected_kind"] = "fragment"
        return GateResult(
            "source_integrity",
            False,
            f"source.md has only {stripped_chars} stripped chars "
            f"(< {MIN_STRIPPED_TEXT_CHARS}); likely a parse fragment",
            detail,
        )
    if len(distinct_titles) >= MULTI_ARTICLE_MIN_DISTINCT_TITLES:
        detail["detected_kind"] = "multi_article_corpus"
        return GateResult(
            "source_integrity",
            False,
            f"source.md concatenates {len(distinct_titles)} distinct article "
            "titles; not a single gold-standard document",
            detail,
        )
    detail["detected_kind"] = "single_article"
    return GateResult("source_integrity", True, "single parseable article", detail)


def gate_standardization_ids(
    record: EntryRecord,
    alias_map: dict[str, dict[str, object]],
) -> GateResult:
    """Gate 2: valid HGNC gene id + MONDO disease id (with parkinson back-fill)."""
    detail: GateDetail = {}
    gene_id = _gene_hgnc_id(record)
    disease_id = _disease_mondo_id(record)
    backfilled_hgnc = ""
    if not gene_id:
        # Parkinson stores the bare symbol in expected_standardization.gene.
        gene = _gene_symbol(record)
        entry = alias_map.get(gene)
        if entry and HGNC_RE.match(str(entry["hgnc_id"])):
            gene_id = str(entry["hgnc_id"])
            backfilled_hgnc = gene_id
    detail["gene_id"] = gene_id
    detail["disease_id"] = disease_id
    if backfilled_hgnc:
        detail["backfilled_hgnc_id"] = backfilled_hgnc

    if not gene_id:
        return GateResult(
            "standardization_ids",
            False,
            "missing valid HGNC gene id and gene symbol did not resolve",
            detail,
        )
    if not disease_id:
        return GateResult(
            "standardization_ids",
            False,
            "missing valid MONDO disease id",
            detail,
        )
    reason = "valid HGNC + MONDO ids"
    if backfilled_hgnc:
        reason += f" (HGNC back-filled from gene symbol -> {backfilled_hgnc})"
    return GateResult("standardization_ids", True, reason, detail)


def gate_article_alignment(
    record: EntryRecord,
    alias_map: dict[str, dict[str, object]],
) -> GateResult:
    """Gate 3: the source article mentions the expected gene (symbol/alias)."""
    detail: GateDetail = {}
    gene = _gene_symbol(record)
    haystack = record.source_md.lower()
    names = [gene]
    entry = alias_map.get(gene)
    if entry:
        names.extend(str(a) for a in entry.get("aliases", []))
        names.extend(str(a) for a in entry.get("previous", []))
    matched_via = ""
    gene_present = False
    for name in names:
        if name and re.search(r"\b" + re.escape(name.lower()) + r"\b", haystack):
            gene_present = True
            matched_via = name
            break
    detail["gene_present"] = gene_present
    detail["gene_matched_via"] = matched_via

    disease = _disease_label(record)
    disease_tokens = [
        t for t in re.findall(r"[A-Za-z]{4,}", disease) if t.lower() not in {"syndrome", "disease", "type", "with"}
    ]
    disease_present = bool(disease) and disease.lower() in haystack
    if not disease_present and disease_tokens:
        disease_present = any(tok.lower() in haystack for tok in disease_tokens[:6])
    detail["disease_present"] = disease_present

    if not gene_present:
        return GateResult(
            "article_alignment",
            False,
            f"expected gene '{gene}' not mentioned in source article",
            detail,
        )
    reason = f"gene '{matched_via}' present in article"
    if not disease_present:
        reason += "; disease label not found (warning only)"
    return GateResult("article_alignment", True, reason, detail)


def _resolve_pdf_path(record: EntryRecord) -> Path | None:
    """Return an existing local PDF for the entry, tolerating relocated paths.

    Rett entries record ``source_pdf_path`` under the legacy
    ``benchmark/literature_acquisition/downloads/`` prefix; after the framework
    refactor the PDFs moved to ``benchmark/data/inputs/literature_acquisition/
    downloads/`` (``RAW_PDF_ROOT``). Annotation copies also live at
    ``benchmark/annotation/ground_truth/<entry_id>/source.pdf``. Any of these
    counts as a verifiable local copy.
    """
    recorded = record.expected.get("source_pdf_path")
    candidates: list[Path] = []
    if isinstance(recorded, str) and recorded:
        path = Path(recorded)
        candidates.append(path)
        # Relocated RAW_PDF_ROOT: preserve the subpath after "downloads/".
        marker = "/downloads/"
        if marker in recorded:
            sub = recorded.split(marker, 1)[1]
            candidates.append(RAW_PDF_ROOT / sub)
    # Annotation ground_truth copy (rett / parkinson review artifacts).
    candidates.append(BENCHMARK_ROOT / "annotation" / "ground_truth" / record.entry_id / "source.pdf")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def gate_verifiable_source(record: EntryRecord) -> GateResult:
    """Gate 4: literature is locatable (PMID / DOI / PDF URL / existing local PDF)."""
    detail: GateDetail = {}
    pmid = record.expected.get("source_pmid")
    doi = record.expected.get("source_doi")
    pdf_url = record.expected.get("source_pdf_url")
    has_pmid = isinstance(pmid, str) and pmid.strip() and pmid.strip() != "0"
    has_doi = isinstance(doi, str) and doi.strip()
    has_pdf_url = isinstance(pdf_url, str) and pdf_url.strip()
    resolved_pdf = _resolve_pdf_path(record)
    detail["has_pmid"] = has_pmid
    detail["has_doi"] = has_doi
    detail["has_pdf_url"] = has_pdf_url
    detail["local_pdf_exists"] = resolved_pdf is not None
    detail["resolved_pdf_path"] = str(resolved_pdf) if resolved_pdf else ""
    if has_pmid or has_doi or has_pdf_url or resolved_pdf is not None:
        return GateResult("verifiable_source", True, "locatable via PMID/DOI/PDF", detail)
    return GateResult(
        "verifiable_source",
        False,
        "no PMID, DOI, PDF URL, or existing local PDF path",
        detail,
    )


# ---------------------------------------------------------------------------
# Cross-dataset dedup
# ---------------------------------------------------------------------------


def _normalize_doi(doi: object) -> str:
    if not isinstance(doi, str) or not doi.strip():
        return ""
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip().lower())


def _normalize_title(title: object) -> str:
    if not isinstance(title, str) or not title.strip():
        return ""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _dedup_keys(record: EntryRecord) -> list[tuple[str, str]]:
    """Return ``(key_type, key)`` pairs usable for cross-dataset dedup."""
    keys: list[tuple[str, str]] = []
    doi = _normalize_doi(record.expected.get("source_doi"))
    if doi:
        keys.append(("doi", doi))
    pmid = record.expected.get("source_pmid")
    if isinstance(pmid, str) and pmid.strip() and pmid.strip() != "0":
        keys.append(("pmid", pmid.strip()))
    title = _normalize_title(record.expected.get("source_title"))
    if title and len(title) >= 20:
        keys.append(("title", title))
    return keys


def _evidence_count(record: EntryRecord) -> int:
    evidence = record.expected.get("expected_evidence")
    if isinstance(evidence, list):
        return len(evidence)
    return 0


def _dedup_rank(record: EntryRecord) -> tuple[object, ...]:
    """Sort key: richer evidence first, then DB-grounded over article-grounded."""
    provenance = DATASET_PROVENANCE[record.source_dataset]
    return (
        _evidence_count(record),
        0 if provenance["gold_source"] == "database" else 1,
        record.entry_id,
    )


def compute_dedup(records: list[EntryRecord]) -> dict[str, GateResult]:
    """Gate 5: mark entries whose literature duplicates a better entry."""
    by_key: dict[tuple[str, str], list[EntryRecord]] = {}
    for record in records:
        for key_type, key in _dedup_keys(record):
            by_key.setdefault((key_type, key), []).append(record)

    results: dict[str, GateResult] = {}
    for (key_type, key), group in by_key.items():
        datasets = {r.source_dataset for r in group}
        if len(group) < 2 or len(datasets) < 2:
            continue  # only dedup across datasets
        winner = max(group, key=_dedup_rank)
        for record in group:
            if record.entry_id == winner.entry_id:
                continue
            existing = results.get(record.entry_id)
            detail: GateDetail = {
                "dedup_key": key,
                "dedup_winner": winner.entry_id,
                "dedup_group": [r.entry_id for r in group],
            }
            reason = f"duplicate literature ({key_type}={key}) kept by {winner.entry_id}"
            if existing is None:
                results[record.entry_id] = GateResult("cross_dataset_dedup", False, reason, detail)
            # If already flagged, keep the first reason; dedup is binary.
    # Every record not flagged passes.
    for record in records:
        results.setdefault(
            record.entry_id,
            GateResult("cross_dataset_dedup", True, "no cross-dataset duplicate", {}),
        )
    return results


# ---------------------------------------------------------------------------
# Selection assembly
# ---------------------------------------------------------------------------


def _evaluation_layers(record: EntryRecord) -> list[str]:
    config = record.expected.get("evaluation_config")
    layers: list[str] = []
    if isinstance(config, dict):
        for key, value in config.items():
            if isinstance(value, list) and value:
                layers.append(key)
    return layers


def _multilingual_sources(record: EntryRecord) -> list[str]:
    langs: list[str] = []
    for child in record.entry_dir.iterdir():
        name = child.name
        if name.startswith("source_") and name.endswith(".md") and name != "source.md":
            langs.append(name[len("source_") : -len(".md")])
    return sorted(langs)


def _relative(path: Path) -> str:
    """Return ``path`` relative to the repository root for portable output."""
    try:
        return str(path.relative_to(BENCHMARK_ROOT.parents[0]))
    except ValueError:
        return str(path)


def _build_selection_entry(
    record: EntryRecord,
    gate_results: dict[str, GateResult],
    unified_id: str,
) -> GoldStandardSelectionEntry:
    provenance = DATASET_PROVENANCE[record.source_dataset]
    evidence = record.expected.get("expected_evidence")
    field_ids = [
        str(item.get("field_id"))
        for item in (evidence if isinstance(evidence, list) else [])
        if isinstance(item, dict) and item.get("field_id")
    ]
    backfilled: dict[str, str] = {}
    std_detail = gate_results["standardization_ids"].detail
    if std_detail.get("backfilled_hgnc_id"):
        backfilled["hgnc_id"] = str(std_detail["backfilled_hgnc_id"])
    verifiable_detail = gate_results["verifiable_source"].detail
    resolved_pdf_abs = str(verifiable_detail.get("resolved_pdf_path") or "")
    resolved_pdf = _relative(Path(resolved_pdf_abs)) if resolved_pdf_abs else ""
    if resolved_pdf and resolved_pdf != _opt_str(record.expected.get("source_pdf_path")):
        backfilled["source_pdf_path"] = resolved_pdf
    notes: list[str] = []
    if not gate_results["article_alignment"].detail.get("disease_present", True):
        notes.append("disease label not found in article (gene present)")
    return GoldStandardSelectionEntry(
        unified_id=unified_id,
        original_entry_id=record.entry_id,
        source_dataset=record.source_dataset,
        gold_source=provenance["gold_source"],
        annotation_provenance=provenance["annotation_provenance"],
        gene_symbol=_gene_symbol(record),
        hgnc_id=std_detail.get("gene_id", _gene_hgnc_id(record)),
        disease_label=_disease_label(record),
        mondo_id=_disease_mondo_id(record),
        moi=_moi(record),
        source_pmid=_opt_str(record.expected.get("source_pmid")),
        source_doi=_opt_str(record.expected.get("source_doi")),
        source_title=str(record.expected.get("source_title") or ""),
        source_year=str(record.expected.get("source_year") or ""),
        source_language=_source_language(record),
        source_pdf_path=resolved_pdf if resolved_pdf else _opt_str(record.expected.get("source_pdf_path")),
        evidence_field_ids=field_ids,
        evidence_count=len(field_ids),
        evaluation_layers=_evaluation_layers(record),
        multilingual_sources=_multilingual_sources(record),
        expected_json_path=_relative(record.entry_dir / "expected.json"),
        source_md_path=_relative(record.source_md_path),
        backfilled=backfilled,
        gate_notes="; ".join(notes),
    )


def _opt_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


GATE_ORDER = (
    "source_integrity",
    "standardization_ids",
    "article_alignment",
    "verifiable_source",
    "cross_dataset_dedup",
)


def build_gold_standard_selection(
    records: list[EntryRecord],
    alias_map: dict[str, dict[str, object]],
) -> tuple[list[EntryReportPayload], list[GoldStandardSelectionEntry], list[DedupGroupPayload]]:
    """Run all gates and assemble the report + curated selection."""
    dedup_results = compute_dedup(records)
    reports: list[EntryReportPayload] = []
    passing: list[tuple[EntryRecord, dict[str, GateResult]]] = []

    for record in records:
        gate_results = {
            "source_integrity": gate_source_integrity(record),
            "standardization_ids": gate_standardization_ids(record, alias_map),
            "article_alignment": gate_article_alignment(record, alias_map),
            "verifiable_source": gate_verifiable_source(record),
            "cross_dataset_dedup": dedup_results[record.entry_id],
        }
        fail_reasons = [g.reason for g in (gate_results[k] for k in GATE_ORDER) if not g.passed]
        overall = not fail_reasons
        provenance = DATASET_PROVENANCE[record.source_dataset]
        reports.append(
            EntryReportPayload(
                entry_id=record.entry_id,
                source_dataset=record.source_dataset,
                gold_source=provenance["gold_source"],
                annotation_provenance=provenance["annotation_provenance"],
                gene_symbol=_gene_symbol(record),
                disease_label=str(record.expected.get("disease_label") or ""),
                overall_passed=overall,
                fail_reasons=fail_reasons,
                gates=[
                    GateResultPayload(
                        gate=g.gate,
                        passed=g.passed,
                        reason=g.reason,
                        detail=g.detail,
                    )
                    for g in (gate_results[k] for k in GATE_ORDER)
                ],
                selection=None,
            )
        )
        if overall:
            passing.append((record, gate_results))

    # Assign unified ids in stable order: dataset, then entry_id.
    passing.sort(key=lambda item: (item[0].source_dataset, item[0].entry_id))
    selection: list[GoldStandardSelectionEntry] = []
    for idx, (record, gate_results) in enumerate(passing):
        unified_id = f"gs_{idx:03d}"
        entry = _build_selection_entry(record, gate_results, unified_id)
        selection.append(entry)
        # Back-fill the selection onto the matching report for convenience.
        for report in reports:
            if report["entry_id"] == record.entry_id:
                report["selection"] = entry
                break

    dedup_groups = _dedup_groups(records)
    return reports, selection, dedup_groups


def _dedup_groups(records: list[EntryRecord]) -> list[DedupGroupPayload]:
    by_key: dict[tuple[str, str], list[EntryRecord]] = {}
    for record in records:
        for key_type, key in _dedup_keys(record):
            by_key.setdefault((key_type, key), []).append(record)
    groups: list[DedupGroupPayload] = []
    for (key_type, key), group in by_key.items():
        if len(group) < 2 or len({r.source_dataset for r in group}) < 2:
            continue
        winner = max(group, key=_dedup_rank)
        groups.append(
            DedupGroupPayload(
                key=key,
                key_type=key_type,
                members=[r.entry_id for r in group],
                winner=winner.entry_id,
                excluded=[r.entry_id for r in group if r.entry_id != winner.entry_id],
            )
        )
    groups.sort(key=lambda g: (g["key_type"], g["key"]))
    return groups


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _summary(
    reports: list[EntryReportPayload],
    selection: list[GoldStandardSelectionEntry],
    dedup_groups: list[DedupGroupPayload],
) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    total = len(reports)
    passed = sum(1 for r in reports if r["overall_passed"])
    per_dataset: dict[str, dict[str, int]] = {}
    for dataset in DATASET_DIRS:
        ds_reports = [r for r in reports if r["source_dataset"] == dataset]
        ds_passed = sum(1 for r in ds_reports if r["overall_passed"])
        per_dataset[dataset] = {
            "total": len(ds_reports),
            "passed": ds_passed,
            "failed": len(ds_reports) - ds_passed,
        }
    fail_by_gate: dict[str, int] = {}
    for report in reports:
        if report["overall_passed"]:
            continue
        for gate in report["gates"]:
            if not gate["passed"]:
                fail_by_gate[gate["gate"]] = fail_by_gate.get(gate["gate"], 0) + 1
    summary: dict[str, int] = {
        "total_entries": total,
        "total_passed": passed,
        "total_failed": total - passed,
        "dedup_groups": len(dedup_groups),
        "dedup_excluded": sum(len(g["excluded"]) for g in dedup_groups),
    }
    summary.update(fail_by_gate)
    return summary, per_dataset


def write_report(
    reports: list[EntryReportPayload],
    selection: list[GoldStandardSelectionEntry],
    dedup_groups: list[DedupGroupPayload],
) -> tuple[Path, Path, Path]:
    """Persist the filter report (JSON + Markdown) and curated selection."""
    import datetime as _dt

    timestamp = _dt.datetime.now(_dt.UTC).strftime("%Y%m%d_%H%M%S")
    summary, per_dataset = _summary(reports, selection, dedup_groups)
    payload = GoldStandardFilterReportPayload(
        schema_version="1.0.0",
        generated_at=timestamp,
        summary=summary,
        per_dataset=per_dataset,
        dedup_groups=dedup_groups,
        entries=reports,
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_json = REPORTS_DIR / f"gold_standard_filter_{timestamp}.json"
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md = REPORTS_DIR / f"gold_standard_filter_{timestamp}.md"
    report_md.write_text(format_summary(payload, selection), encoding="utf-8")
    # Stable-name selection index for the merge step.
    SELECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    selection_payload = {
        "schema_version": "1.0.0",
        "generated_at": timestamp,
        "source_datasets": list(DATASET_DIRS),
        "summary": {
            "total_passed": summary["total_passed"],
            "by_gold_source": {
                "database": sum(1 for e in selection if e["gold_source"] == "database"),
                "article": sum(1 for e in selection if e["gold_source"] == "article"),
            },
            "by_dataset": per_dataset,
        },
        "entries": selection,
    }
    SELECTION_PATH.write_text(json.dumps(selection_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_json, report_md, SELECTION_PATH


def format_summary(
    report: GoldStandardFilterReportPayload,
    selection: list[GoldStandardSelectionEntry],
) -> str:
    """Render a human-readable Markdown summary of the filter run."""
    summary = report["summary"]
    lines: list[str] = [
        "# Gold-Standard Literature Filter Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Schema: `{report['schema_version']}`",
        "",
        "## Summary",
        "",
        f"- Total entries scanned: **{summary['total_entries']}**",
        f"- Passed all gates: **{summary['total_passed']}**",
        f"- Failed: **{summary['total_failed']}**",
        f"- Cross-dataset dedup groups: **{summary['dedup_groups']}** ({summary['dedup_excluded']} entries excluded)",
        "",
        "## Per-dataset outcome",
        "",
        "| Dataset | Total | Passed | Failed |",
        "|---------|-------|--------|--------|",
    ]
    for dataset in DATASET_DIRS:
        stats = report["per_dataset"].get(dataset, {"total": 0, "passed": 0, "failed": 0})
        lines.append(f"| {dataset} | {stats['total']} | {stats['passed']} | {stats['failed']} |")
    lines.extend(["", "## Failure counts by gate", ""])
    gate_labels = {
        "source_integrity": "Source integrity",
        "standardization_ids": "Standardization IDs",
        "article_alignment": "Article-evidence alignment",
        "verifiable_source": "Verifiable source",
        "cross_dataset_dedup": "Cross-dataset dedup",
    }
    for gate, label in gate_labels.items():
        count = summary.get(gate, 0)
        lines.append(f"- {label}: **{count}**")
    if report["dedup_groups"]:
        lines.extend(["", "## Cross-dataset duplicates", ""])
        lines.append("| Key type | Key | Winner | Excluded |")
        lines.append("|----------|-----|--------|----------|")
        for group in report["dedup_groups"]:
            lines.append(
                f"| {group['key_type']} | `{group['key'][:60]}` | {group['winner']} | {', '.join(group['excluded'])} |"
            )
    lines.extend(["", "## Curated selection composition", ""])
    by_source: dict[str, int] = {}
    by_dataset: dict[str, int] = {}
    for entry in selection:
        by_source[entry["gold_source"]] = by_source.get(entry["gold_source"], 0) + 1
        by_dataset[entry["source_dataset"]] = by_dataset.get(entry["source_dataset"], 0) + 1
    lines.append(f"- gold_source=database: **{by_source.get('database', 0)}**")
    lines.append(f"- gold_source=article: **{by_source.get('article', 0)}**")
    lines.append("- by dataset: " + ", ".join(f"{k}={v}" for k, v in sorted(by_dataset.items())))
    lines.extend(
        [
            "",
            "Selection index written to `benchmark/data/ground_truth/gold_standard_selection.json`.",
        ]
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Filter gold-standard literature across all benchmark datasets.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress per-entry logging",
    )
    args = parser.parse_args(argv)

    records, alias_map = load_entries()
    if not records:
        logger.error("no entries loaded; aborting")
        return 1
    reports, selection, dedup_groups = build_gold_standard_selection(records, alias_map)
    report_json, report_md, selection_path = write_report(reports, selection, dedup_groups)

    summary, per_dataset = _summary(reports, selection, dedup_groups)
    print(f"\n=== Gold-standard filter: {summary['total_passed']}/{summary['total_entries']} entries passed ===")
    for dataset in DATASET_DIRS:
        stats = per_dataset[dataset]
        print(f"  {dataset:14s}: {stats['passed']}/{stats['total']} passed ({stats['failed']} failed)")
    print(f"\nReport JSON : {report_json}")
    print(f"Report MD   : {report_md}")
    print(f"Selection   : {selection_path}")

    if not args.quiet:
        for report in reports:
            if not report["overall_passed"]:
                reasons = "; ".join(report["fail_reasons"])
                logger.info("FAIL {} ({}): {}", report["entry_id"], report["source_dataset"], reasons)
    return 0


if __name__ == "__main__":
    sys.exit(main())
