"""Materialize the unified gold-standard benchmark dataset.

Reads ``gold_standard_selection.json`` (the filter output) and writes a
self-contained, schema-unified dataset under
``benchmark/data/ground_truth/unified/gs_NNN/``. For every selected entry this
module:

1. **Lifts** the nested ``clingen{}`` block of clinvar_fused entries to
   top-level fields (gene_symbol, hgnc_id, disease_label, mondo_id, moi,
   classification, gcep, classification_date, clingen_report_url).
2. **Back-fills** missing standard identifiers and metadata from local
   authority files:
   - ``hgnc_id`` from the HGNC terminology file (parkinson bare symbols).
   - ``moi`` / ``classification`` / ``gcep`` / ``classification_date`` /
     ``clingen_report_url`` from the ClinGen Gene-Disease Summary CSV
     (parkinson genes; looked up by gene symbol, falling back to the HGNC
     approved symbol so renamed genes like GBA -> GBA1 still resolve).
   - ``source_language`` from ``meta.json`` (parkinson) or ``"en"`` default
     for the English-PMC clingen / clinvar_fused datasets.
   - ``source_pdf_path`` resolved to an existing local PDF (pipeline input for
     clingen/clinvar_fused, ``meta.json`` for parkinson, relocated
     ``RAW_PDF_ROOT`` for rett).
   - ``expected_entities`` derived from standardization + top-level fields
     when empty (rett).
   - ``evaluation_config`` generated from the actual ``expected_evidence``
     field ids via the evidence-field-catalog layer map (clingen/parkinson).
3. **Back-fills** ``source_doi`` / ``source_journal`` / ``source_year`` from
   EuropePMC by PMID (cached, concurrent, failure-tolerant).
4. **Unifies** ``variants[]`` across the rett ``variants[]`` and clinvar_fused
   ``clinvar_variants[]`` shapes, preserving every source field (fidelity) and
   tagging each item with its origin.
5. **Materializes** ``expected.json`` + ``source.md`` (+ any multilingual
   ``source_*.md``) per entry, plus a top-level ``manifest.json``.

Original ground-truth data is never modified.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

import httpx
from loguru import logger

from benchmark.analysis.dataset_curation.gold_standard_filter import DATASET_PROVENANCE
from benchmark.core.paths import BENCHMARK_ROOT, DATA_ROOT

__all__ = [
    "build_unified_dataset",
    "main",
]

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

UNIFIED_ROOT = DATA_ROOT / "ground_truth" / "unified"
SELECTION_PATH = DATA_ROOT / "ground_truth" / "gold_standard_selection.json"
HGNC_TERMINOLOGY_FILE = BENCHMARK_ROOT.parent / "database" / "terminology_database" / "hgnc" / "hgnc_complete_set.txt"
CLINGEN_CSV = (
    BENCHMARK_ROOT.parent / "database" / "terminology_database" / "clingen" / "Clingen-Gene-Disease-Summary.csv"
)
FIELD_CATALOG = BENCHMARK_ROOT.parent / "knowledges" / "evidence-field-catalog.json"
PMID_CACHE_PATH = DATA_ROOT / "ground_truth" / "unified_pmid_cache.json"

PIPELINE_PDF_ROOT = BENCHMARK_ROOT / "pipeline" / "input" / "ground_truth"

EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPEPMC_ALLOWED_HOST = "www.ebi.ac.uk"
PMID_CONCURRENCY = 5
PMID_TIMEOUT = 30.0

HGNC_RE = re.compile(r"^HGNC:\d+$")
MONDO_RE = re.compile(r"^MONDO:\d+$")

# Provenance label per dataset, recorded in the unified ``source`` field.
SOURCE_LABEL: dict[str, str] = {
    "clingen": "clingen_literature",
    "clinvar_fused": "clingen_clinvar_fused",
    "rett": "rett_literature",
    "parkinson": "parkinson_literature",
}

# Fields lifted from the clinvar_fused nested ``clingen{}`` block.
CLINGEN_LIFT_FIELDS = (
    "gene_symbol",
    "hgnc_id",
    "disease_label",
    "mondo_id",
    "moi",
    "classification",
    "gcep",
    "classification_date",
)

# Evidence fields that belong to the gene-disease evaluation layer (the rest of
# category A + J.clinvar_assertion are variant fields; B/C/D/E/F/G/H/I are
# clinical fields). Populated from the field catalog at load time.
GENE_DISEASE_FIELD_IDS = {
    "A.gene_symbol",
    "A.gene_aliases",
    "A.gene_disease_relationship",
    "B.disease_diagnosis",
    "B.mode_of_inheritance_reported",
}


# ---------------------------------------------------------------------------
# Contracts (rule 22: no bare dict return types)
# ---------------------------------------------------------------------------


class UnifiedVariant(TypedDict, total=False):
    """One unified variant item (fidelity-preserving across sources)."""

    source: str  # rett | clinvar
    hgvs_c: str
    hgvs_p: str
    hgvs_name: str
    variant_type: str
    clinical_significance: str
    exon: str
    domain: str
    variation_id: str
    rsid: str
    review_status: str
    review_stars: int
    phenotype_ids: str
    phenotype_list: str


class UnifiedEntity(TypedDict, total=False):
    text: str
    hgnc_id: str
    mondo_id: str
    variation_id: str
    rsid: str


class UnifiedExpected(TypedDict, total=False):
    """The canonical unified ``expected.json`` schema."""

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
    classification: str
    gcep: str
    classification_date: str
    clingen_report_url: str
    source: str
    source_pmid: str
    source_doi: str
    source_pmc: str
    source_pdf_url: str
    source_pdf_path: str
    source_title: str
    source_journal: str
    source_year: str
    source_language: str
    variants: list[UnifiedVariant]
    expected_evidence: list[dict[str, Any]]
    expected_entities: dict[str, Any]
    expected_standardization: dict[str, Any]
    evaluation_config: dict[str, list[str]]
    notes: str
    backfilled: dict[str, str]


class ManifestEntry(TypedDict):
    unified_id: str
    original_entry_id: str
    source_dataset: str
    gene_symbol: str
    hgnc_id: str
    disease_label: str
    mondo_id: str
    source_pmid: str
    source_doi: str
    source_pdf_path: str
    files: list[str]


class Manifest(TypedDict):
    schema_version: str
    generated_at: str
    entry_count: int
    by_dataset: dict[str, int]
    by_gold_source: dict[str, int]
    backfill_summary: dict[str, int]
    entries: list[ManifestEntry]


@dataclass
class BuildContext:
    """Shared lookup tables loaded once for the whole build."""

    hgnc_aliases: dict[str, dict[str, Any]] = field(default_factory=dict)
    clingen_records: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)
    field_layer: dict[str, str] = field(default_factory=dict)
    pmid_cache: dict[str, dict[str, str]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Authority file loading
# ---------------------------------------------------------------------------


def load_hgnc_aliases(genes: set[str]) -> dict[str, dict[str, Any]]:
    """Resolve gene_symbol -> {approved, hgnc_id, aliases, previous} from HGNC."""
    aliases: dict[str, dict[str, Any]] = {}
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
    return aliases


def load_clingen_records() -> dict[tuple[str, str], dict[str, str]]:
    """Parse the ClinGen Gene-Disease Summary CSV (header on row 5).

    Returns a ``(gene_symbol, mondo_id) -> record`` map. The CSV has 4 banner
    rows before the real header.
    """
    records: dict[tuple[str, str], dict[str, str]] = {}
    if not CLINGEN_CSV.exists():
        logger.warning("ClinGen CSV not found: {}", CLINGEN_CSV)
        return records
    fieldnames = ["GS", "HGNC", "DISEASE", "MONDO", "MOI", "SOP", "CLASS", "URL", "DATE", "GCEP"]
    with CLINGEN_CSV.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle, fieldnames=fieldnames)
        for index, row in enumerate(reader):
            if index < 5:  # skip banner + separator rows
                continue
            gene = (row["GS"] or "").strip()
            mondo = (row["MONDO"] or "").strip()
            if not gene or not mondo:
                continue
            records[(gene, mondo)] = {
                "gene_symbol": gene,
                "hgnc_id": (row["HGNC"] or "").strip(),
                "disease_label": (row["DISEASE"] or "").strip(),
                "mondo_id": mondo,
                "moi": (row["MOI"] or "").strip(),
                "classification": (row["CLASS"] or "").strip(),
                "gcep": (row["GCEP"] or "").strip(),
                "classification_date": (row["DATE"] or "").strip(),
                "clingen_report_url": (row["URL"] or "").strip(),
            }
    return records


def load_field_layer() -> dict[str, str]:
    """Map every catalog field_id to an evaluation layer."""
    layer: dict[str, str] = {}
    if not FIELD_CATALOG.exists():
        logger.warning("Field catalog not found: {}", FIELD_CATALOG)
        return layer
    catalog = json.loads(FIELD_CATALOG.read_text(encoding="utf-8"))
    for item in catalog.get("items", []):
        field_id = item.get("field_id")
        category = item.get("category_id")
        if not field_id:
            continue
        if field_id in GENE_DISEASE_FIELD_IDS:
            layer[field_id] = "gene_disease_fields"
        elif category == "A" or field_id == "J.clinvar_assertion":
            layer[field_id] = "variant_fields"
        elif category in {"B", "C", "D", "E", "F", "G", "H", "I"}:
            layer[field_id] = "clinical_fields"
        else:
            layer[field_id] = "other"
    return layer


def load_pmid_cache() -> dict[str, dict[str, str]]:
    if PMID_CACHE_PATH.exists():
        try:
            return json.loads(PMID_CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("pmid cache corrupt, starting fresh: {}", PMID_CACHE_PATH)
    return {}


# ---------------------------------------------------------------------------
# EuropePMC metadata back-fill
# ---------------------------------------------------------------------------


def _pmids_needing_lookup(entries: list[dict[str, Any]]) -> list[str]:
    """Collect PMIDs whose entry is missing doi, journal, or year."""
    pmids: set[str] = set()
    for entry in entries:
        pmid = entry.get("source_pmid")
        if not isinstance(pmid, str) or not pmid.strip() or pmid.strip() == "0":
            continue
        missing = not entry.get("source_doi") or not entry.get("source_journal") or not entry.get("source_year")
        if missing:
            pmids.add(pmid.strip())
    return sorted(pmids)


async def _fetch_pmid_metadata(
    client: httpx.AsyncClient, pmid: str, cache: dict[str, dict[str, str]]
) -> dict[str, str]:
    """Query EuropePMC by PMID for doi / journal / year, with cache."""
    if pmid in cache:
        return cache[pmid]
    params = {"query": f"EXT_ID:{pmid}", "format": "json", "pageSize": 1, "resultType": "core"}
    result: dict[str, str] = {}
    try:
        resp = await client.get(EUROPEPMC_SEARCH, params=params, timeout=PMID_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("resultList", {}).get("result", [])
        if results:
            row = results[0]
            doi = (row.get("doi") or "").strip()
            journal = ""
            journal_info = row.get("journalInfo") or {}
            if isinstance(journal_info, dict):
                journal_obj = journal_info.get("journal") or {}
                if isinstance(journal_obj, dict):
                    journal = (journal_obj.get("title") or "").strip()
            year = (row.get("pubYear") or "").strip()
            if not year and isinstance(journal_info, dict):
                year = str(journal_info.get("yearOfPublication") or "").strip()
            if doi:
                result["source_doi"] = doi
            if journal:
                result["source_journal"] = journal
            if year:
                result["source_year"] = year
    except (httpx.HTTPError, httpx.RequestError) as exc:
        logger.debug("europepmc lookup failed for PMID {}: {}", pmid, exc)
        result["__error__"] = str(exc)
    cache[pmid] = result
    return result


async def backfill_pmid_metadata(selection_entries: list[dict[str, Any]], cache: dict[str, dict[str, str]]) -> None:
    """Fetch missing doi/journal/year from EuropePMC for all eligible entries."""
    pmids = _pmids_needing_lookup(selection_entries)
    pmids = [p for p in pmids if p not in cache or "__error__" in cache[p]]
    if not pmids:
        logger.info("no PMIDs need EuropePMC lookup (all cached or complete)")
        return
    logger.info("fetching EuropePMC metadata for {} PMIDs", len(pmids))
    semaphore = asyncio.Semaphore(PMID_CONCURRENCY)

    async with httpx.AsyncClient(headers={"User-Agent": "lingua-seeker-benchmark/1.0"}) as client:

        async def _bounded(pmid: str) -> None:
            async with semaphore:
                await _fetch_pmid_metadata(client, pmid, cache)

        await asyncio.gather(*(_bounded(p) for p in pmids))
    PMID_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PMID_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Per-entry unification
# ---------------------------------------------------------------------------


def _gene_symbol_of(expected: dict[str, Any]) -> str:
    gene = expected.get("gene_symbol")
    if isinstance(gene, str) and gene.strip():
        return gene.strip()
    clingen = expected.get("clingen")
    if isinstance(clingen, dict):
        nested = clingen.get("gene_symbol")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return ""


def _resolve_pdf_path(entry: dict[str, Any], expected: dict[str, Any]) -> str:
    """Resolve an existing local PDF path for the unified entry."""
    # 1. parkinson: meta.json pdf_path (absolute, verified existing).
    # 2. clingen/clinvar_fused: pipeline input PDF (English primary).
    # 3. rett: already-resolved source_pdf_path from the selection index.
    dataset = entry["source_dataset"]
    original_id = entry["original_entry_id"]
    if dataset == "parkinson":
        meta_path = BENCHMARK_ROOT / "data" / "ground_truth" / "parkinson" / original_id / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            pdf = meta.get("pdf_path")
            if isinstance(pdf, str) and pdf and Path(pdf).exists():
                return _relative(Path(pdf))
    if dataset in {"clingen", "clinvar_fused"}:
        for lang in ("en", "zh", "ja", "ko", "de", "es", "fr"):
            candidate = PIPELINE_PDF_ROOT / lang / "case_report" / f"{original_id}.pdf"
            if candidate.exists():
                return _relative(candidate)
    recorded = entry.get("source_pdf_path")
    if isinstance(recorded, str) and recorded and (BENCHMARK_ROOT.parent / recorded).exists():
        return recorded
    return ""


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(BENCHMARK_ROOT.parents[0]))
    except ValueError:
        return str(path)


def _lookup_clingen(ctx: BuildContext, gene_symbol: str, mondo_id: str) -> dict[str, str] | None:
    """Look up a ClinGen record by (gene, mondo); fall back to HGNC approved symbol."""
    if not gene_symbol or not mondo_id:
        return None
    record = ctx.clingen_records.get((gene_symbol, mondo_id))
    if record:
        return record
    alias = ctx.hgnc_aliases.get(gene_symbol)
    if alias:
        approved = alias.get("approved")
        if isinstance(approved, str):
            record = ctx.clingen_records.get((approved, mondo_id))
            if record:
                return record
    return None


def _unify_variants(expected: dict[str, Any], dataset: str) -> list[UnifiedVariant]:
    """Merge rett ``variants[]`` / clinvar ``clinvar_variants[]`` into one list."""
    variants: list[UnifiedVariant] = []
    rett_variants = expected.get("variants")
    if isinstance(rett_variants, list):
        for item in rett_variants:
            if isinstance(item, dict):
                unified: UnifiedVariant = {"source": "rett"}
                for key in ("hgvs_c", "hgvs_p", "variant_type", "clinical_significance", "exon", "domain"):
                    value = item.get(key)
                    if isinstance(value, str) and value:
                        unified[key] = value
                variants.append(unified)
    clinvar_variants = expected.get("clinvar_variants")
    if isinstance(clinvar_variants, list):
        for item in clinvar_variants:
            if isinstance(item, dict):
                unified = {"source": "clinvar"}
                for key in (
                    "variation_id",
                    "hgvs_name",
                    "hgvs_c",
                    "hgvs_p",
                    "variant_type",
                    "clinical_significance",
                    "rsid",
                    "review_status",
                    "phenotype_ids",
                    "phenotype_list",
                ):
                    value = item.get(key)
                    if value in (None, ""):
                        continue
                    if key == "review_stars" or key == "variation_id":
                        unified[key] = str(value) if key == "variation_id" else value  # type: ignore[assignment]
                    else:
                        unified[key] = str(value) if not isinstance(value, str) else value
                if isinstance(item.get("review_stars"), int):
                    unified["review_stars"] = item["review_stars"]
                variants.append(unified)
    return variants


def _build_expected_entities(expected: dict[str, Any], unified: UnifiedExpected) -> dict[str, Any]:
    """Ensure expected_entities has gene + disease (+ variants) populated."""
    entities = dict(expected.get("expected_entities") or {})
    gene_entity = entities.get("gene")
    if not isinstance(gene_entity, dict) or not gene_entity:
        gene_entity = {"text": unified["gene_symbol"]}
        if unified.get("hgnc_id"):
            gene_entity["hgnc_id"] = unified["hgnc_id"]
        entities["gene"] = gene_entity
    else:
        if not gene_entity.get("hgnc_id") and unified.get("hgnc_id"):
            gene_entity["hgnc_id"] = unified["hgnc_id"]
        if not gene_entity.get("text"):
            gene_entity["text"] = unified["gene_symbol"]
    disease_entity = entities.get("disease")
    if not isinstance(disease_entity, dict) or not disease_entity:
        disease_entity = {"text": unified["disease_label"]}
        if unified.get("mondo_id"):
            disease_entity["mondo_id"] = unified["mondo_id"]
        entities["disease"] = disease_entity
    else:
        if not disease_entity.get("mondo_id") and unified.get("mondo_id"):
            disease_entity["mondo_id"] = unified["mondo_id"]
        if not disease_entity.get("text"):
            disease_entity["text"] = unified["disease_label"]
    # variant entities (clinvar carries variation_id / rsid).
    if "variants" not in entities and unified.get("variants"):
        var_entities: list[UnifiedEntity] = []
        for var in unified["variants"]:
            entity: UnifiedEntity = {"text": var.get("hgvs_c") or var.get("hgvs_p") or var.get("hgvs_name") or ""}
            if var.get("variation_id"):
                entity["variation_id"] = var["variation_id"]
            if var.get("rsid"):
                entity["rsid"] = var["rsid"]
            if entity["text"] or entity.get("variation_id"):
                var_entities.append(entity)
        if var_entities:
            entities["variants"] = var_entities
    return entities


def _build_evaluation_config(expected: dict[str, Any], ctx: BuildContext) -> dict[str, list[str]]:
    """Generate evaluation_config from the actual expected_evidence field ids."""
    evidence = expected.get("expected_evidence")
    if not isinstance(evidence, list):
        return {}
    layers: dict[str, list[str]] = {
        "gene_disease_fields": [],
        "variant_fields": [],
        "clinical_fields": [],
    }
    seen: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            continue
        field_id = item.get("field_id")
        if not isinstance(field_id, str) or field_id in seen:
            continue
        seen.add(field_id)
        layer = ctx.field_layer.get(field_id, "other")
        if layer in layers:
            layers[layer].append(field_id)
    config: dict[str, list[str]] = {k: v for k, v in layers.items() if v}
    config["standardization_fields"] = ["gene", "disease"]
    std = expected.get("expected_standardization")
    if isinstance(std, dict) and std.get("variant_candidates"):
        config["standardization_fields"].append("variant")
    return config


def _build_standardization(expected: dict[str, Any], unified: UnifiedExpected) -> dict[str, Any]:
    std = dict(expected.get("expected_standardization") or {})
    if not std.get("gene") or not HGNC_RE.match(str(std.get("gene"))):
        if unified.get("hgnc_id"):
            std["gene"] = unified["hgnc_id"]
    if not std.get("disease") or not MONDO_RE.match(str(std.get("disease"))):
        if unified.get("mondo_id"):
            std["disease"] = unified["mondo_id"]
    return std


def unify_entry(entry: dict[str, Any], expected: dict[str, Any], ctx: BuildContext) -> UnifiedExpected:
    """Build the unified expected.json for one selection entry."""
    dataset = entry["source_dataset"]
    provenance = DATASET_PROVENANCE[dataset]
    backfilled: dict[str, str] = {}
    notes_parts: list[str] = []

    # Start from the original expected (keeps expected_evidence, notes, etc.).
    unified: UnifiedExpected = {}
    unified["unified_id"] = entry["unified_id"]
    unified["original_entry_id"] = entry["original_entry_id"]
    unified["source_dataset"] = dataset
    unified["gold_source"] = provenance["gold_source"]
    unified["annotation_provenance"] = provenance["annotation_provenance"]
    unified["source"] = SOURCE_LABEL[dataset]

    # --- Lift clinvar_fused nested clingen{} block to top level. ---
    gene_symbol = _gene_symbol_of(expected)
    hgnc_id = ""
    disease_label = ""
    mondo_id = ""
    moi = ""
    classification = ""
    gcep = ""
    classification_date = ""
    clingen_report_url = ""
    if dataset == "clinvar_fused":
        clingen = expected.get("clingen") or {}
        gene_symbol = clingen.get("gene_symbol") or gene_symbol
        hgnc_id = clingen.get("hgnc_id") or ""
        disease_label = clingen.get("disease_label") or ""
        mondo_id = clingen.get("mondo_id") or ""
        moi = clingen.get("moi") or ""
        classification = clingen.get("classification") or ""
        gcep = clingen.get("gcep") or ""
        classification_date = clingen.get("classification_date") or ""
        report_url = clingen.get("report_url") or ""
        if isinstance(report_url, str) and report_url:
            clingen_report_url = report_url
            backfilled["clingen_report_url"] = "lifted_clingen_block"
        for fname in CLINGEN_LIFT_FIELDS:
            backfilled[fname] = "lifted_clingen_block"
    else:
        gene_symbol = expected.get("gene_symbol") or gene_symbol
        hgnc_id = expected.get("hgnc_id") or ""
        disease_label = expected.get("disease_label") or ""
        mondo_id = expected.get("mondo_id") or ""
        moi = expected.get("moi") or ""
        classification = expected.get("classification") or ""
        gcep = expected.get("gcep") or ""
        classification_date = expected.get("classification_date") or ""
        clingen_report_url = expected.get("clingen_report_url") or ""

    # --- hgnc_id back-fill from HGNC file (parkinson bare symbols). ---
    if not hgnc_id or not HGNC_RE.match(str(hgnc_id)):
        alias = ctx.hgnc_aliases.get(gene_symbol)
        if alias and HGNC_RE.match(str(alias.get("hgnc_id", ""))):
            hgnc_id = str(alias["hgnc_id"])
            backfilled["hgnc_id"] = "hgnc_file"

    # --- ClinGen CSV back-fill (parkinson) for moi/classification/etc. ---
    if (not moi or not classification) and mondo_id:
        record = _lookup_clingen(ctx, gene_symbol, mondo_id)
        if record:
            if not moi and record.get("moi"):
                moi = record["moi"]
                backfilled["moi"] = "clingen_csv"
            if not classification and record.get("classification"):
                classification = record["classification"]
                backfilled["classification"] = "clingen_csv"
            if not gcep and record.get("gcep"):
                gcep = record["gcep"]
                backfilled["gcep"] = "clingen_csv"
            if not classification_date and record.get("classification_date"):
                classification_date = record["classification_date"]
                backfilled["classification_date"] = "clingen_csv"
            if not clingen_report_url and record.get("clingen_report_url"):
                clingen_report_url = record["clingen_report_url"]
                backfilled["clingen_report_url"] = "clingen_csv"
        elif not moi:
            notes_parts.append(f"{gene_symbol}: no ClinGen record; moi unknown")

    # --- source_language back-fill. ---
    source_language = str(expected.get("source_language") or "").strip()
    if not source_language:
        meta_path = BENCHMARK_ROOT / "data" / "ground_truth" / dataset / entry["original_entry_id"] / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                lang = meta.get("language")
                if isinstance(lang, str) and lang.strip():
                    source_language = lang.strip()
                    backfilled["source_language"] = "meta_json"
            except json.JSONDecodeError:
                pass
        if not source_language and dataset in {"clingen", "clinvar_fused"}:
            source_language = "en"
            backfilled["source_language"] = "default_en"

    # --- source_pdf_path resolution. ---
    source_pdf_path = _resolve_pdf_path(entry, expected)
    if source_pdf_path and source_pdf_path != entry.get("source_pdf_path"):
        backfilled["source_pdf_path"] = "resolved_local"

    unified.update(
        gene_symbol=gene_symbol,
        hgnc_id=hgnc_id,
        disease_label=disease_label,
        mondo_id=mondo_id,
        moi=moi,
        classification=classification,
        gcep=gcep,
        classification_date=classification_date,
        clingen_report_url=clingen_report_url,
        source_pmid=str(expected.get("source_pmid") or entry.get("source_pmid") or "").strip() or "",
        source_doi=str(expected.get("source_doi") or "").strip(),
        source_pmc=str(expected.get("source_pmc") or "").strip(),
        source_pdf_url=str(expected.get("source_pdf_url") or "").strip(),
        source_pdf_path=source_pdf_path,
        source_title=str(expected.get("source_title") or entry.get("source_title") or "").strip(),
        source_journal=str(expected.get("source_journal") or "").strip(),
        source_year=str(expected.get("source_year") or "").strip(),
        source_language=source_language,
    )

    # --- EuropePMC back-fill (doi / journal / year) from cache. ---
    pmid = unified["source_pmid"]
    if pmid and pmid in ctx.pmid_cache:
        meta = ctx.pmid_cache[pmid]
        for key in ("source_doi", "source_journal", "source_year"):
            if not unified.get(key) and meta.get(key):
                unified[key] = meta[key]
                backfilled[key] = "europepmc_pmid"

    # --- variants, entities, standardization, evaluation_config. ---
    variants = _unify_variants(expected, dataset)
    unified["variants"] = variants
    unified["expected_evidence"] = list(expected.get("expected_evidence") or [])
    unified["expected_standardization"] = _build_standardization(expected, unified)
    unified["expected_entities"] = _build_expected_entities(expected, unified)
    if "evaluation_config" not in expected or not expected.get("evaluation_config"):
        unified["evaluation_config"] = _build_evaluation_config(expected, ctx)
        backfilled["evaluation_config"] = "derived_from_evidence"
    else:
        unified["evaluation_config"] = expected["evaluation_config"]
    if not expected.get("expected_entities"):
        backfilled["expected_entities"] = "derived_from_standardization"

    unified["notes"] = str(expected.get("notes") or "")
    if notes_parts:
        unified["notes"] = (unified["notes"] + " | " if unified["notes"] else "") + "; ".join(notes_parts)
    unified["backfilled"] = backfilled
    return unified


# ---------------------------------------------------------------------------
# Materialization
# ---------------------------------------------------------------------------


def _copy_source_files(entry: dict[str, Any], dest: Path) -> list[str]:
    """Copy source.md (+ multilingual source_*.md) into the unified entry dir."""
    src_md_rel = entry.get("source_md_path")
    files: list[str] = []
    if not src_md_rel:
        return files
    src_md = BENCHMARK_ROOT.parent / src_md_rel
    if src_md.exists():
        shutil.copy2(src_md, dest / "source.md")
        files.append("source.md")
    # Multilingual source_*.md live next to source.md in the original entry dir.
    src_dir = src_md.parent
    for sibling in src_dir.iterdir():
        name = sibling.name
        if name.startswith("source_") and name.endswith(".md") and name != "source.md":
            shutil.copy2(sibling, dest / name)
            files.append(name)
    return files


def _collect_pdf_sources(
    entry: dict[str, Any], expected: dict[str, Any], source_language: str
) -> list[tuple[str, Path]]:
    """Collect every available local PDF for the entry as ``(lang, path)``.

    For clingen / clinvar_fused the pipeline input holds one PDF per language
    under ``{lang}/case_report/{original_id}.pdf``. Parkinson has a single PDF
    recorded in ``meta.json``. Rett has a single resolved PDF (from the
    selection index). The single-file cases are tagged ``"_primary"`` so the
    caller copies them as ``source.pdf``.
    """
    dataset = entry["source_dataset"]
    original_id = entry["original_entry_id"]
    sources: list[tuple[str, Path]] = []
    if dataset in {"clingen", "clinvar_fused"}:
        for lang_dir in PIPELINE_PDF_ROOT.iterdir():
            if not lang_dir.is_dir():
                continue
            pdf = lang_dir / "case_report" / f"{original_id}.pdf"
            if pdf.exists():
                sources.append((lang_dir.name, pdf))
        return sources
    if dataset == "parkinson":
        meta_path = BENCHMARK_ROOT / "data" / "ground_truth" / "parkinson" / original_id / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
            pdf = meta.get("pdf_path")
            if isinstance(pdf, str) and pdf and Path(pdf).exists():
                sources.append(("_primary", Path(pdf)))
        return sources
    # rett: single resolved PDF from the selection index.
    recorded = entry.get("source_pdf_path")
    if isinstance(recorded, str) and recorded:
        resolved = BENCHMARK_ROOT.parent / recorded
        if resolved.exists():
            sources.append(("_primary", resolved))
    return sources


def _copy_pdf_files(
    entry: dict[str, Any],
    expected: dict[str, Any],
    dest: Path,
    source_language: str,
) -> tuple[list[str], str]:
    """Copy all available PDFs into the unified entry dir (self-contained).

    The primary PDF (matching ``source_language``, or the single ``_primary``
    file) becomes ``source.pdf``; every other language becomes
    ``source_{lang}.pdf``. Returns ``(copied_filenames, local_primary_relpath)``.
    """
    sources = _collect_pdf_sources(entry, expected, source_language)
    if not sources:
        return [], ""
    # Choose the primary: the source_language match, else "en", else "_primary",
    # else the first available.
    primary_lang = next(
        (lang for lang, _ in sources if lang == source_language),
        None,
    )
    if primary_lang is None:
        primary_lang = next((lang for lang, _ in sources if lang == "en"), None)
    if primary_lang is None:
        primary_lang = next((lang for lang, _ in sources if lang == "_primary"), None)
    if primary_lang is None:
        primary_lang = sources[0][0]
    copied: list[str] = []
    primary_local = ""
    for lang, pdf in sources:
        if lang == primary_lang or lang == "_primary":
            target = dest / "source.pdf"
            shutil.copy2(pdf, target)
            copied.append("source.pdf")
            primary_local = _relative(target)
        else:
            target = dest / f"source_{lang}.pdf"
            shutil.copy2(pdf, target)
            copied.append(f"source_{lang}.pdf")
    return copied, primary_local


def build_unified_dataset(selection_path: Path = SELECTION_PATH) -> Manifest:
    """Materialize the unified dataset from the gold-standard selection."""
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    entries = selection["entries"]
    logger.info("unifying {} gold-standard entries", len(entries))

    genes = {e.get("gene_symbol") for e in entries if e.get("gene_symbol")}
    # Also pull nested clinvar gene symbols via the original expected files.
    for entry in entries:
        expected_path = BENCHMARK_ROOT.parent / entry["expected_json_path"]
        if expected_path.exists():
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
            clingen = expected.get("clingen")
            if isinstance(clingen, dict) and clingen.get("gene_symbol"):
                genes.add(clingen["gene_symbol"])
    ctx = BuildContext(
        hgnc_aliases=load_hgnc_aliases(genes),
        clingen_records=load_clingen_records(),
        field_layer=load_field_layer(),
        pmid_cache=load_pmid_cache(),
    )
    asyncio.run(backfill_pmid_metadata(entries, ctx.pmid_cache))

    # Wipe and recreate the unified root for a clean, reproducible build.
    if UNIFIED_ROOT.exists():
        shutil.rmtree(UNIFIED_ROOT)
    UNIFIED_ROOT.mkdir(parents=True, exist_ok=True)

    manifest_entries: list[ManifestEntry] = []
    by_dataset: dict[str, int] = {}
    by_gold_source: dict[str, int] = {}
    backfill_counts: dict[str, int] = {}

    for entry in entries:
        expected_path = BENCHMARK_ROOT.parent / entry["expected_json_path"]
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        unified = unify_entry(entry, expected, ctx)
        dest = UNIFIED_ROOT / entry["unified_id"]
        dest.mkdir(parents=True, exist_ok=True)
        files = _copy_source_files(entry, dest)
        pdf_files, pdf_local = _copy_pdf_files(entry, expected, dest, unified.get("source_language", ""))
        if pdf_files:
            files.extend(pdf_files)
            if pdf_local and pdf_local != unified.get("source_pdf_path"):
                unified["source_pdf_path"] = pdf_local
                unified.setdefault("backfilled", {})["source_pdf_path"] = "materialized_local"
        files.append("expected.json")
        (dest / "expected.json").write_text(json.dumps(unified, ensure_ascii=False, indent=2), encoding="utf-8")
        by_dataset[entry["source_dataset"]] = by_dataset.get(entry["source_dataset"], 0) + 1
        by_gold_source[entry["gold_source"]] = by_gold_source.get(entry["gold_source"], 0) + 1
        for key in unified.get("backfilled", {}):
            backfill_counts[key] = backfill_counts.get(key, 0) + 1
        manifest_entries.append(
            ManifestEntry(
                unified_id=entry["unified_id"],
                original_entry_id=entry["original_entry_id"],
                source_dataset=entry["source_dataset"],
                gene_symbol=unified["gene_symbol"],
                hgnc_id=unified["hgnc_id"],
                disease_label=unified["disease_label"],
                mondo_id=unified["mondo_id"],
                source_pmid=unified.get("source_pmid") or "",
                source_doi=unified.get("source_doi") or "",
                source_pdf_path=unified.get("source_pdf_path") or "",
                files=files,
            )
        )

    import datetime as _dt

    manifest = Manifest(
        schema_version="1.0.0",
        generated_at=_dt.datetime.now(_dt.UTC).strftime("%Y%m%d_%H%M%S"),
        entry_count=len(entries),
        by_dataset=by_dataset,
        by_gold_source=by_gold_source,
        backfill_summary=backfill_counts,
        entries=manifest_entries,
    )
    (UNIFIED_ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "materialized {} entries to {} (backfills: {})",
        len(entries),
        UNIFIED_ROOT,
        backfill_counts,
    )
    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the unified gold-standard benchmark dataset.",
    )
    parser.add_argument(
        "--selection",
        type=Path,
        default=SELECTION_PATH,
        help="path to gold_standard_selection.json",
    )
    args = parser.parse_args(argv)
    manifest = build_unified_dataset(args.selection)
    print(f"\n=== Unified dataset: {manifest['entry_count']} entries ===")
    print(f"  location: {UNIFIED_ROOT}")
    for ds, count in sorted(manifest["by_dataset"].items()):
        print(f"  {ds}: {count}")
    print(f"  gold_source: {manifest['by_gold_source']}")
    print("  backfills:")
    for key, count in sorted(manifest["backfill_summary"].items(), key=lambda kv: -kv[1]):
        print(f"    {key}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
