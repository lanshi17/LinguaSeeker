"""Import benchmark ground truth evidence items and literature into PostgreSQL.

Reads ground truth entries (Rett, ClinGen, ClinVar Fused, Parkinson, Merged-73)
and imports dual-track (original + translated) and reconciled evidence with
full source span traceability. Literature metadata, evidence items, and entity
metadata are all imported — nothing is dropped.

For entries with preprocessed ``extraction_result.json``, imports real pipeline
extraction data including text snippets, page offsets, and confidence scores
for original, translated, and reconciled tracks. Evidence item values are
preserved as native JSONB (strings, lists, dicts) — not stringified.

For entries without preprocessed data, creates synthetic dual-track evidence
from ``expected.json`` ground truth values.

Database initialization: ``--init-db`` drops and recreates all tables EXCEPT
the terminology library (terminology_entries, terminology_aliases,
terminology_relationships, terminology_embeddings).

Default environment: development. Override with ``--environment``.

Usage::

    cd backend
    # Initialize DB (drop non-terminology tables) and import everything
    uv run python ../scripts/data/import/import_benchmark_ground_truth.py --init-db
    # Import specific datasets only
    uv run python ../scripts/data/import/import_benchmark_ground_truth.py --datasets rett clingen
    # Import one entry
    uv run python ../scripts/data/import/import_benchmark_ground_truth.py --entry-id rett_006
    # Dry run (no DB writes)
    uv run python ../scripts/data/import/import_benchmark_ground_truth.py --dry-run
    # Use production environment instead of development
    uv run python ../scripts/data/import/import_benchmark_ground_truth.py --environment production
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from decimal import Decimal
from pathlib import Path

# ── Environment selection (must happen before config import) ─────────────────


def _parse_env_from_argv() -> str:
    """Extract --environment from argv before config module is imported."""
    for i, arg in enumerate(sys.argv):
        if arg == "--environment" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if arg.startswith("--environment="):
            return arg.split("=", 1)[1]
    return "development"


os.environ["ENVIRONMENT"] = _parse_env_from_argv()

from loguru import logger  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from src.core.config import get_config  # noqa: E402
from src.dao.postgresql.connection import (  # noqa: E402
    async_session_factory,
    build_async_engine,
)
from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository  # noqa: E402
from src.dao.postgresql.models import (  # noqa: E402
    Base,
    CanonicalEvidenceItem,
    ChatMessage,
    ChatSession,
    DocumentProcessingCache,
    EvidenceEntityBinding,
    LiteratureProfile,
    NormalizedEntity,
    PipelineRunState,
    ProcessingRun,
    ReviewAuditEvent,
    RunEvidenceItem,
    SourceDocument,
    SourceDocumentIdentifier,
)
from sqlalchemy import select, text  # noqa: E402


# ── Terminology tables preserved during --init-db ────────────────────────────

TERMINOLOGY_TABLES = frozenset({
    "terminology_entries",
    "terminology_aliases",
    "terminology_relationships",
    "terminology_embeddings",
})

# ── Dataset discovery ────────────────────────────────────────────────────────

DATASET_DIRS = {
    "rett": "rett",
    "clingen": "clingen",
    "clinvar_fused": "clinvar_fused",
    "parkinson": "parkinson",
    "merged_73": "merged_73",
}


def discover_entries(gt_root: Path, datasets: list[str]) -> list[dict]:
    """Walk ground truth directories and collect entry paths."""
    entries: list[dict] = []
    for ds in datasets:
        ds_dir = gt_root / DATASET_DIRS[ds]
        if not ds_dir.is_dir():
            logger.warning("Dataset directory not found: {}", ds_dir)
            continue
        for entry_dir in sorted(ds_dir.iterdir()):
            expected = entry_dir / "expected.json"
            if expected.is_file():
                entries.append({
                    "dataset": ds,
                    "expected_path": expected,
                    "entry_dir": entry_dir,
                    "extraction_path": entry_dir / "preprocessed" / "phase_2" / "extraction_result.json",
                    "source_md_path": entry_dir / "source.md",
                    "source_zh_md_path": entry_dir / "source_zh.md",
                    "meta_json_path": entry_dir / "meta.json",
                })
    return entries


# ── Data normalization ───────────────────────────────────────────────────────


def _normalize_entry(data: dict, dataset: str) -> dict:
    """Normalize different expected.json schemas into a uniform structure."""
    entry_id = data["entry_id"]

    if dataset == "rett":
        variants = []
        for v in data.get("variants") or []:
            variants.append({
                "hgvs_c": v.get("hgvs_c") or "",
                "hgvs_p": v.get("hgvs_p") or "",
                "variant_type": v.get("variant_type") or "",
                "clinical_significance": v.get("clinical_significance") or "",
                "exon": v.get("exon") or "",
                "domain": v.get("domain") or "",
            })
        return {
            "entry_id": entry_id,
            "gene_symbol": data.get("gene_symbol") or "",
            "hgnc_id": data.get("hgnc_id") or "",
            "disease_label": data.get("disease_label") or "",
            "mondo_id": data.get("mondo_id") or "",
            "moi": data.get("moi") or "",
            "classification": data.get("classification") or "",
            "pmid": data.get("source_pmid"),
            "doi": data.get("source_doi"),
            "pmc": None,
            "title": data.get("source_title") or "",
            "journal": data.get("source_journal") or "",
            "year": data.get("source_year"),
            "language": data.get("source_language") or "en",
            "variants": variants,
            "expected_evidence": data.get("expected_evidence") or [],
            "expected_entities": data.get("expected_entities") or {},
            "expected_standardization": data.get("expected_standardization") or {},
            "notes": data.get("notes") or "",
            "gcep": data.get("gcep") or "",
        }

    if dataset == "clingen":
        return {
            "entry_id": entry_id,
            "gene_symbol": data.get("gene_symbol") or "",
            "hgnc_id": data.get("hgnc_id") or "",
            "disease_label": data.get("disease_label") or "",
            "mondo_id": data.get("mondo_id") or "",
            "moi": data.get("moi") or "",
            "classification": data.get("classification") or "",
            "pmid": data.get("source_pmid"),
            "doi": None,
            "pmc": data.get("source_pmc"),
            "title": data.get("source_title") or "",
            "journal": data.get("source_journal") or "",
            "year": data.get("source_year"),
            "language": "en",
            "variants": [],
            "expected_evidence": data.get("expected_evidence") or [],
            "expected_entities": data.get("expected_entities") or {},
            "expected_standardization": data.get("expected_standardization") or {},
            "notes": data.get("notes") or "",
            "gcep": data.get("gcep") or "",
        }

    if dataset == "clinvar_fused":
        clingen = data.get("clingen") or {}
        clinvar_variants = data.get("clinvar_variants") or []
        variants = []
        for v in clinvar_variants:
            variants.append({
                "hgvs_c": v.get("hgvs_c") or "",
                "hgvs_p": v.get("hgvs_p") or "",
                "variant_type": v.get("variant_type") or "",
                "clinical_significance": v.get("clinical_significance") or "",
                "variation_id": v.get("variation_id"),
                "rsid": v.get("rsid"),
            })
        return {
            "entry_id": entry_id,
            "gene_symbol": clingen.get("gene_symbol") or "",
            "hgnc_id": clingen.get("hgnc_id") or "",
            "disease_label": clingen.get("disease_label") or "",
            "mondo_id": clingen.get("mondo_id") or "",
            "moi": clingen.get("moi") or "",
            "classification": clingen.get("classification") or "",
            "pmid": data.get("source_pmid"),
            "doi": None,
            "pmc": data.get("source_pmc"),
            "title": data.get("source_title") or "",
            "journal": data.get("source_journal") or "",
            "year": data.get("source_year"),
            "language": "en",
            "variants": variants[:5],
            "expected_evidence": data.get("expected_evidence") or [],
            "expected_entities": data.get("expected_entities") or {},
            "expected_standardization": data.get("expected_standardization") or {},
            "notes": data.get("notes") or "",
            "gcep": clingen.get("gcep") or "",
        }

    if dataset == "parkinson":
        return {
            "entry_id": entry_id,
            "gene_symbol": data.get("gene_symbol") or "",
            "hgnc_id": "",
            "disease_label": data.get("disease_label") or "",
            "mondo_id": data.get("mondo_id") or "",
            "moi": "",
            "classification": "",
            "pmid": data.get("source_pmid"),
            "doi": data.get("source_doi"),
            "pmc": None,
            "title": data.get("source_title") or "",
            "journal": data.get("source_journal") or "",
            "year": data.get("source_year"),
            "language": "en",
            "variants": [],
            "expected_evidence": data.get("expected_evidence") or [],
            "expected_entities": data.get("expected_entities") or {},
            "expected_standardization": data.get("expected_standardization") or {},
            "notes": data.get("notes") or "",
            "gcep": "",
        }

    # merged_73: detect source format from entry_id prefix
    if entry_id.startswith("parkinson_"):
        return _normalize_entry(data, "parkinson")
    if entry_id.startswith("rett_"):
        return _normalize_entry(data, "rett")
    if entry_id.startswith("clingen_"):
        return _normalize_entry(data, "clingen")
    if entry_id.startswith("fused_"):
        return _normalize_entry(data, "clinvar_fused")

    # Fallback: treat as generic entry with minimal fields
    logger.warning("Unknown entry_id prefix for merged_73: {}", entry_id)
    return {
        "entry_id": entry_id,
        "gene_symbol": data.get("gene_symbol") or "",
        "hgnc_id": data.get("hgnc_id") or "",
        "disease_label": data.get("disease_label") or "",
        "mondo_id": data.get("mondo_id") or "",
        "moi": data.get("moi") or "",
        "classification": data.get("classification") or "",
        "pmid": data.get("source_pmid"),
        "doi": data.get("source_doi"),
        "pmc": data.get("source_pmc"),
        "title": data.get("source_title") or "",
        "journal": data.get("source_journal") or "",
        "year": data.get("source_year"),
        "language": "en",
        "variants": data.get("variants") or [],
        "expected_evidence": data.get("expected_evidence") or [],
        "expected_entities": data.get("expected_entities") or {},
        "expected_standardization": data.get("expected_standardization") or {},
        "notes": data.get("notes") or "",
        "gcep": data.get("gcep") or "",
    }


def _get_lit_id(norm: dict) -> tuple[str, str]:
    """Return (id_type, id_value) for document deduplication."""
    if norm.get("doi"):
        return ("doi", str(norm["doi"]))
    if norm.get("pmid"):
        return ("pmid", str(norm["pmid"]))
    if norm.get("pmc"):
        return ("pmc", str(norm["pmc"]))
    return ("benchmark_id", norm["entry_id"])


def _read_meta(meta_path: Path) -> dict:
    """Read meta.json for additional literature metadata."""
    if not meta_path.is_file():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# ── Hash helpers ─────────────────────────────────────────────────────────────


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def _value_to_hash_str(value: object) -> str:
    """Normalize a structured value to a deterministic string for hashing."""
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value) if value is not None else ""


def _field_id_to_category(field_id: str) -> str:
    prefix = field_id.split(".")[0] if "." in field_id else field_id
    mapping = {
        "A": "GeneVariant",
        "B": "ClinicalPhenotype",
        "C": "CaseEvidence",
        "D": "FunctionalAssay",
        "E": "PopulationFrequency",
        "F": "Segregation",
        "G": "CaseAggregate",
        "H": "DeNovo",
        "I": "Summary",
        "J": "Authority",
    }
    return mapping.get(prefix, "Other")


# ── Preprocessed data reader ────────────────────────────────────────────────


def _read_preprocessed_tracks(extraction_path: Path) -> dict | None:
    """Read extraction_result.json and return {original: [...], translated: [...], reconciled: [...]}.

    Returns None only if the file doesn't exist or has no usable tracks.
    A track is included if its status is 'completed' and it has evidence items.
    """
    if not extraction_path.is_file():
        return None
    try:
        data = json.loads(extraction_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    result: dict[str, list] = {}
    for track_key, track_name in (
        ("original_result", "original"),
        ("translated_result", "translated"),
        ("reconciled_result", "reconciled"),
    ):
        track_data = data.get(track_key)
        if not track_data or track_data.get("status") != "completed":
            continue
        items = track_data.get("evidence_items") or []
        # Also include phenotype_evidence items (same structure, different category)
        pheno_items = track_data.get("phenotype_evidence") or []
        all_items = items + pheno_items
        if all_items:
            result[track_name] = all_items

    if not result:
        return None

    # Attach full track metadata for ProcessingRun output_artifacts
    result["_meta"] = {
        "document_id": data.get("document_id"),
        "alignment_records": data.get("alignment_records") or [],
        "tracks_present": [k for k in ("original", "translated", "reconciled") if k in result],
    }
    # Attach quality_report and evidence_chains per track
    for track_key, track_name in (
        ("original_result", "original"),
        ("translated_result", "translated"),
        ("reconciled_result", "reconciled"),
    ):
        track_data = data.get(track_key)
        if track_data:
            result["_meta"][f"{track_name}_quality_report"] = track_data.get("quality_report") or {}
            result["_meta"][f"{track_name}_evidence_chains"] = track_data.get("evidence_chains") or []
            result["_meta"][f"{track_name}_evidence_map"] = track_data.get("evidence_map") or {}
            result["_meta"][f"{track_name}_extraction_target"] = track_data.get("extraction_target") or {}

    return result


def _build_evidence_specs(tracks: dict | None, norm: dict) -> list[dict]:
    """Build a unified list of evidence specs from preprocessed or ground truth data.

    Each spec describes one evidence item for one track, with source span
    for traceability. Values are preserved as native Python types (str, list)
    for proper JSONB storage.
    """
    specs: list[dict] = []
    seen_keys: set[tuple] = set()

    if tracks:
        for track_name in ("original", "translated", "reconciled"):
            for item in tracks.get(track_name, []):
                field_id = item.get("field_id", "")
                if not field_id:
                    continue
                status = item.get("status", "found")
                value = item.get("value", "")
                group_id = item.get("group_id", "")
                dedup_key = (field_id, track_name, group_id, _value_to_hash_str(value))
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                source = item.get("source") or {}
                raw_source = item.get("raw_source") or {}
                specs.append({
                    "track": track_name,
                    "field_id": field_id,
                    "value": value,
                    "confidence": float(item.get("confidence", 1.0)),
                    "status": status,
                    "source_span": source,
                    "raw_source": raw_source,
                    "group_id": group_id,
                    "target_gene": item.get("target_gene", ""),
                    "target_disease": item.get("target_disease", ""),
                    "field_name": item.get("field_name", ""),
                    "category": item.get("category", ""),
                    "notes": item.get("notes", ""),
                    "evidence_role": item.get("evidence_role", "primary"),
                    "acmg_codes": item.get("assigned_acmg_codes") or [],
                    "clingen_modules": item.get("assigned_clingen_modules") or [],
                    "article_language": item.get("article_language", ""),
                    "inference_basis": item.get("inference_basis") or [],
                    "requires_external_completion": item.get("requires_external_completion", False),
                    "external_completion_note": item.get("external_completion_note", ""),
                    "is_english": item.get("is_english"),
                    "requires_translation": item.get("requires_translation"),
                    "evidence_source_language": item.get("evidence_source_language", ""),
                    "data_source": "preprocessed",
                })
    else:
        for ev in norm.get("expected_evidence", []):
            field_id = ev.get("field_id", "")
            value = ev.get("value", "")
            base_span = {
                "source": "benchmark_ground_truth",
                "entry_id": norm["entry_id"],
            }
            for track_name in ("original", "translated"):
                specs.append({
                    "track": track_name,
                    "field_id": field_id,
                    "value": value,
                    "confidence": 1.0,
                    "status": "found",
                    "source_span": {**base_span, "track": track_name},
                    "raw_source": {},
                    "group_id": "",
                    "target_gene": norm["gene_symbol"],
                    "target_disease": norm["disease_label"],
                    "field_name": field_id,
                    "category": _field_id_to_category(field_id),
                    "notes": "",
                    "evidence_role": "primary",
                    "acmg_codes": [],
                    "clingen_modules": [],
                    "article_language": norm.get("language", "en") if track_name == "original" else "en",
                    "inference_basis": [],
                    "requires_external_completion": False,
                    "external_completion_note": "",
                    "is_english": None,
                    "requires_translation": None,
                    "evidence_source_language": "",
                    "data_source": "ground_truth",
                })

    return specs


# ── Database initialization ──────────────────────────────────────────────────
# Tables excluded from --init-db (preserved across re-initialization).


async def _init_database(engine) -> None:
    """Drop and recreate all non-terminology tables.

    Terminology tables (terminology_entries, terminology_aliases,
    terminology_relationships, terminology_embeddings) are preserved.
    """
    logger.info("Initializing database: dropping non-terminology tables...")

    non_term_tables = [
        t for t in Base.metadata.sorted_tables
        if t.name not in TERMINOLOGY_TABLES
    ]

    async with engine.begin() as conn:
        # Drop in reverse dependency order (sorted_tables is already topological)
        for table in reversed(non_term_tables):
            await conn.execute(text(f'DROP TABLE IF EXISTS "{table.name}" CASCADE'))
        logger.info("Dropped {} non-terminology tables", len(non_term_tables))

        # Create in forward dependency order
        for table in non_term_tables:
            await conn.run_sync(
                lambda sync_conn, tbl=table: tbl.create(sync_conn, checkfirst=True)
            )
        logger.info("Created {} non-terminology tables", len(non_term_tables))

    logger.info("Database initialization complete (terminology tables preserved)")


# ── Core import ──────────────────────────────────────────────────────────────


async def _import_entry(
    session,
    norm: dict,
    dataset: str,
    entry_dir: Path,
) -> dict:
    """Import one ground truth entry with full track traceability.

    Returns stats dict with counts.
    """
    entry_id = norm["entry_id"]
    id_type, id_value = _get_lit_id(norm)

    # ── Cleanup existing ──
    result = await session.execute(
        select(SourceDocumentIdentifier.source_document_id)
        .where(
            SourceDocumentIdentifier.identifier_type == id_type,
            SourceDocumentIdentifier.identifier_value == id_value,
        )
    )
    existing_doc_id = result.scalar_one_or_none()
    if existing_doc_id:
        await _delete_doc_cascade(session, existing_doc_id)

    # ── Read preprocessed data ──
    extraction_path = entry_dir / "preprocessed" / "phase_2" / "extraction_result.json"
    tracks = _read_preprocessed_tracks(extraction_path)
    has_preprocessed = tracks is not None
    track_meta = tracks.get("_meta", {}) if tracks else {}

    # ── Read source text ──
    source_md_path = entry_dir / "source.md"
    original_text = None
    if source_md_path.is_file():
        try:
            original_text = source_md_path.read_text(encoding="utf-8")
        except OSError:
            pass

    source_zh_md_path = entry_dir / "source_zh.md"
    translated_text = None
    if source_zh_md_path.is_file():
        try:
            translated_text = source_zh_md_path.read_text(encoding="utf-8")
        except OSError:
            pass

    # ── Read meta.json ──
    meta = _read_meta(entry_dir / "meta.json")

    # ── Build evidence specs ──
    specs = _build_evidence_specs(tracks, norm)

    source_document_id = uuid.uuid4()
    processing_run_id = uuid.uuid4()

    # ── SourceDocument ──
    year_val = None
    if norm.get("year"):
        try:
            year_val = int(norm["year"])
        except (ValueError, TypeError):
            pass

    # Merge expected_entities into raw_metadata for full traceability
    raw_metadata = {
        "title": norm["title"],
        "journal": norm["journal"],
        "publication_year": year_val,
        "language": norm["language"],
        "authors": [],
        "entry_id": entry_id,
        "dataset": dataset,
        "gene_symbol": norm["gene_symbol"],
        "hgnc_id": norm["hgnc_id"],
        "disease_label": norm["disease_label"],
        "mondo_id": norm["mondo_id"],
        "moi": norm["moi"],
        "classification": norm["classification"],
        "gcep": norm.get("gcep") or "",
        "notes": norm.get("notes") or "",
        "has_preprocessed": has_preprocessed,
        "article_text_chars": len(original_text) if original_text else 0,
        "translated_text_chars": len(translated_text) if translated_text else 0,
        "has_source_md": source_md_path.is_file(),
        "has_source_zh_md": source_zh_md_path.is_file(),
        "has_meta_json": bool(meta),
        "dual_track": True,
        "expected_entities": norm.get("expected_entities") or {},
        "expected_standardization": norm.get("expected_standardization") or {},
        "meta": meta,
    }

    session.add(SourceDocument(
        source_document_id=source_document_id,
        raw_metadata=raw_metadata,
        original_text=original_text,
        translated_text=translated_text,
    ))
    await session.flush()

    # ── SourceDocumentIdentifier ──
    for itype, ival in [
        ("doi", norm.get("doi")),
        ("pmid", norm.get("pmid")),
        ("pmc", norm.get("pmc")),
        ("benchmark_id", entry_id),
    ]:
        if ival is not None and str(ival).strip():
            session.add(SourceDocumentIdentifier(
                source_document_id=source_document_id,
                identifier_type=itype,
                identifier_value=str(ival),
            ))
    await session.flush()

    # ── ProcessingRun ──
    evidence_count = len(specs)
    track_names = track_meta.get("tracks_present", ["original", "translated"]) if has_preprocessed else ["original", "translated"]
    output_artifacts = {
        "evidence_count": evidence_count,
        "tracks": track_names,
    }
    # Attach quality reports and evidence chains per track
    for tn in track_names:
        if f"{tn}_quality_report" in track_meta:
            output_artifacts[f"{tn}_quality_report"] = track_meta[f"{tn}_quality_report"]
        if f"{tn}_evidence_chains" in track_meta:
            output_artifacts[f"{tn}_evidence_chains"] = track_meta[f"{tn}_evidence_chains"]
        if f"{tn}_evidence_map" in track_meta:
            output_artifacts[f"{tn}_evidence_map"] = track_meta[f"{tn}_evidence_map"]
        if f"{tn}_extraction_target" in track_meta:
            output_artifacts[f"{tn}_extraction_target"] = track_meta[f"{tn}_extraction_target"]
    if "alignment_records" in track_meta:
        output_artifacts["alignment_records"] = track_meta["alignment_records"]

    session.add(ProcessingRun(
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        parser_version="benchmark_ground_truth",
        extraction_version="benchmark_ground_truth",
        fusion_version="benchmark_ground_truth" if "reconciled" in track_names else None,
        run_status="completed",
        input_artifacts={
            "dataset": dataset,
            "entry_id": entry_id,
            "data_source": "preprocessed" if has_preprocessed else "ground_truth",
            "document_id": track_meta.get("document_id") if has_preprocessed else None,
        },
        output_artifacts=output_artifacts,
    ))
    await session.flush()

    # ── Normalized entities (from expected_entities and variants) ──
    gene_entity_id = await _upsert_entity_from_expected(
        session, "gene", norm,
        norm.get("expected_entities", {}).get("gene") or {},
        norm.get("expected_standardization", {}).get("gene") or norm.get("hgnc_id") or "",
    )
    disease_entity_id = await _upsert_entity_from_expected(
        session, "disease", norm,
        norm.get("expected_entities", {}).get("disease") or {},
        norm.get("expected_standardization", {}).get("disease") or norm.get("mondo_id") or "",
    )

    variant_entities: dict[str, uuid.UUID] = {}
    for vi, variant in enumerate(norm["variants"]):
        ext_id = None
        if variant.get("variation_id"):
            ext_id = f"ClinVarVariation:{variant['variation_id']}"
        elif variant.get("hgvs_c"):
            ext_id = variant["hgvs_c"]
        elif variant.get("hgvs_p"):
            ext_id = variant["hgvs_p"]
        display = variant.get("hgvs_c") or variant.get("hgvs_p") or f"variant_{vi}"
        eid = await _upsert_entity(
            session, "variant", ext_id, display, display,
            {
                "hgvs_c": variant.get("hgvs_c", ""),
                "hgvs_p": variant.get("hgvs_p", ""),
                "variant_type": variant.get("variant_type", ""),
                "clinical_significance": variant.get("clinical_significance", ""),
                "exon": variant.get("exon", ""),
                "domain": variant.get("domain", ""),
                "variation_id": variant.get("variation_id"),
                "rsid": variant.get("rsid"),
                "dataset": dataset,
            },
        )
        if eid:
            variant_entities[display] = eid

    # ── Evidence items (all tracks) ──
    track_counts: dict[str, int] = {}

    for spec in specs:
        track = spec["track"]
        field_id = spec["field_id"]
        value = spec["value"]
        group_id = spec.get("group_id") or f"gene={norm['gene_symbol']}|variant=__missing__"

        text_hash = _hash(_value_to_hash_str(value))
        position_hash = _hash(entry_id, field_id, track, group_id, text_hash)
        entity_scope_hash = _hash(
            spec.get("target_gene") or norm["gene_symbol"],
            spec.get("target_disease") or norm.get("disease_label", ""),
        )

        # Build source_span with full traceability data
        source_span = dict(spec.get("source_span") or {})
        source_span.setdefault("track", track)
        source_span.setdefault("entry_id", entry_id)

        run_ev = RunEvidenceItem(
            processing_run_id=processing_run_id,
            source_document_id=source_document_id,
            track=track,
            field_id=field_id,
            status=spec.get("status", "found"),
            value=value,
            confidence=Decimal(str(min(spec.get("confidence", 1.0), 1.0))),
            position_hash=position_hash,
            text_hash=text_hash,
            source_span=source_span,
            entity_scope_hash=entity_scope_hash,
            raw_payload={
                "dataset": dataset,
                "group_id": group_id,
                "target_gene": spec.get("target_gene", ""),
                "target_disease": spec.get("target_disease", ""),
                "notes": spec.get("notes", ""),
                "evidence_role": spec.get("evidence_role", "primary"),
                "acmg_codes": spec.get("acmg_codes", []),
                "clingen_modules": spec.get("clingen_modules", []),
                "article_language": spec.get("article_language", ""),
                "data_source": spec.get("data_source", ""),
                "raw_source": spec.get("raw_source", {}),
                "field_name": spec.get("field_name", ""),
                "inference_basis": spec.get("inference_basis", []),
                "requires_external_completion": spec.get("requires_external_completion", False),
                "external_completion_note": spec.get("external_completion_note", ""),
                "evidence_source_language": spec.get("evidence_source_language", ""),
                "is_english": spec.get("is_english"),
                "requires_translation": spec.get("requires_translation"),
                "category": spec.get("category", ""),
            },
        )
        session.add(run_ev)
        await session.flush()

        # ── CanonicalEvidenceItem ──
        category = spec.get("category") or _field_id_to_category(field_id)
        canonical = CanonicalEvidenceItem(
            source_document_id=source_document_id,
            field_id=field_id,
            position_hash=position_hash,
            text_hash=text_hash,
            entity_scope_hash=entity_scope_hash,
            current_best_run_evidence_id=run_ev.run_evidence_item_id,
            current_best_status=spec.get("status", "found"),
            current_best_confidence=Decimal(str(min(spec.get("confidence", 1.0), 1.0))),
            conflict_flag=False,
            review_status="approved",
            active_payload={
                "value": value,
                "group_id": group_id,
                "track": track,
                "field_id": field_id,
                "field_name": spec.get("field_name", field_id),
                "source": "benchmark_ground_truth",
                "entity_id": str(gene_entity_id) if gene_entity_id else None,
                "status": spec.get("status", "found"),
                "confidence": spec.get("confidence", 1.0),
                "category": category,
                "acmg_codes": spec.get("acmg_codes", []),
                "clingen_modules": spec.get("clingen_modules", []),
                "text_snippet": (spec.get("source_span") or {}).get("text_snippet", ""),
                "page": (spec.get("source_span") or {}).get("page"),
                "data_source": spec.get("data_source", ""),
                "notes": spec.get("notes", ""),
            },
        )
        session.add(canonical)
        await session.flush()

        # ── Evidence entity bindings ──
        bindings: list[tuple[str, uuid.UUID | None, str]] = []
        if gene_entity_id:
            bindings.append(("gene", gene_entity_id, norm["gene_symbol"]))
        if disease_entity_id:
            bindings.append(("disease", disease_entity_id, norm["disease_label"]))
        for vname, veid in variant_entities.items():
            bindings.append(("variant", veid, vname))

        for rank, (role, eid, raw_text) in enumerate(bindings):
            if eid is None:
                continue
            session.add(EvidenceEntityBinding(
                run_evidence_item_id=run_ev.run_evidence_item_id,
                entity_id=eid,
                entity_type=role,
                role=role,
                binding_rank=rank,
                raw_entity_text=raw_text,
            ))

        track_counts[track] = track_counts.get(track, 0) + 1

    await session.flush()

    # ── LiteratureProfile ──
    repo = LiteratureProfileRepository(session)
    await repo.refresh_for_document(source_document_id)

    return {
        "has_preprocessed": has_preprocessed,
        "track_counts": track_counts,
        "evidence_count": len(specs),
    }


# ── Entity helpers ───────────────────────────────────────────────────────────


async def _upsert_entity_from_expected(
    session,
    entity_type: str,
    norm: dict,
    entity_data: dict,
    standardization_id: str,
) -> uuid.UUID | None:
    """Find or create a NormalizedEntity from expected_entities data.

    Args:
        entity_data: Dict from expected_entities, e.g. {"text": "ABCA3", "hgnc_id": "HGNC:33"}.
        standardization_id: The standardized ID from expected_standardization, e.g. "HGNC:33".
    """
    raw_text = entity_data.get("text") or ""
    if not raw_text:
        # Fall back to norm fields
        if entity_type == "gene":
            raw_text = norm.get("gene_symbol") or ""
        elif entity_type == "disease":
            raw_text = norm.get("disease_label") or ""
    if not raw_text:
        return None

    # Determine external_id from entity_data or standardization_id
    external_id = None
    if entity_type == "gene":
        external_id = entity_data.get("hgnc_id") or standardization_id or norm.get("hgnc_id") or None
    elif entity_type == "disease":
        external_id = entity_data.get("mondo_id") or standardization_id or norm.get("mondo_id") or None

    payload = {
        "entity_type": entity_type,
        "source": "benchmark_ground_truth",
        "dataset": norm.get("entry_id", ""),
    }
    if entity_type == "gene":
        payload["hgnc_id"] = norm.get("hgnc_id") or ""
    elif entity_type == "disease":
        payload["mondo_id"] = norm.get("mondo_id") or ""

    return await _upsert_entity(session, entity_type, external_id, raw_text, raw_text, payload)


async def _upsert_entity(
    session,
    entity_type: str,
    external_id: str | None,
    raw_text: str,
    display_name: str,
    payload: dict,
) -> uuid.UUID | None:
    """Find or create a NormalizedEntity. Returns entity_id or None."""
    if not raw_text:
        return None

    if external_id:
        result = await session.execute(
            select(NormalizedEntity.entity_id)
            .where(
                NormalizedEntity.entity_type == entity_type,
                NormalizedEntity.external_id == external_id,
                NormalizedEntity.standardization_status == "standardized",
            )
        )
        eid = result.scalar_one_or_none()
        if eid:
            return eid

        entity = NormalizedEntity(
            entity_type=entity_type,
            external_id=external_id,
            normalized_raw_text=raw_text,
            display_name=display_name,
            aliases=[],
            standardization_status="standardized",
            raw_payload=payload,
        )
        session.add(entity)
        await session.flush()
        return entity.entity_id

    result = await session.execute(
        select(NormalizedEntity.entity_id)
        .where(
            NormalizedEntity.entity_type == entity_type,
            NormalizedEntity.normalized_raw_text == raw_text,
            NormalizedEntity.standardization_status == "unmapped",
        )
    )
    eid = result.scalar_one_or_none()
    if eid:
        return eid

    entity = NormalizedEntity(
        entity_type=entity_type,
        normalized_raw_text=raw_text,
        display_name=display_name,
        aliases=[],
        standardization_status="unmapped",
        raw_payload=payload,
    )
    session.add(entity)
    await session.flush()
    return entity.entity_id


async def _delete_doc_cascade(session, source_document_id: uuid.UUID) -> None:
    """Delete all records for one source document (for re-import)."""
    run_ids_result = await session.execute(
        select(ProcessingRun.processing_run_id)
        .where(ProcessingRun.source_document_id == source_document_id)
    )
    run_ids = [r[0] for r in run_ids_result.all()]

    if run_ids:
        ev_ids_result = await session.execute(
            select(RunEvidenceItem.run_evidence_item_id)
            .where(RunEvidenceItem.processing_run_id.in_(run_ids))
        )
        ev_ids = [r[0] for r in ev_ids_result.all()]
        if ev_ids:
            await session.execute(
                EvidenceEntityBinding.__table__.delete()
                .where(EvidenceEntityBinding.run_evidence_item_id.in_(ev_ids))
            )

    canonical_ids_result = await session.execute(
        select(CanonicalEvidenceItem.canonical_evidence_id)
        .where(CanonicalEvidenceItem.source_document_id == source_document_id)
    )
    canonical_ids = [r[0] for r in canonical_ids_result.all()]
    if canonical_ids:
        await session.execute(
            ReviewAuditEvent.__table__.delete()
            .where(ReviewAuditEvent.canonical_evidence_id.in_(canonical_ids))
        )
        await session.execute(
            ChatMessage.__table__.delete()
            .where(ChatMessage.evidence_id.in_(canonical_ids))
        )

    # Delete chat sessions linked to this document's runs
    if run_ids:
        await session.execute(
            ChatSession.__table__.delete()
            .where(ChatSession.processing_run_id.in_(run_ids))
        )

    await session.execute(
        PipelineRunState.__table__.delete()
        .where(PipelineRunState.source_document_id == source_document_id)
    )
    await session.execute(
        DocumentProcessingCache.__table__.delete()
        .where(DocumentProcessingCache.processing_run_id == source_document_id)
    )
    await session.execute(
        CanonicalEvidenceItem.__table__.delete()
        .where(CanonicalEvidenceItem.source_document_id == source_document_id)
    )
    await session.execute(
        RunEvidenceItem.__table__.delete()
        .where(RunEvidenceItem.source_document_id == source_document_id)
    )
    await session.execute(
        ProcessingRun.__table__.delete()
        .where(ProcessingRun.source_document_id == source_document_id)
    )
    await session.execute(
        LiteratureProfile.__table__.delete()
        .where(LiteratureProfile.source_document_id == source_document_id)
    )
    await session.execute(
        SourceDocumentIdentifier.__table__.delete()
        .where(SourceDocumentIdentifier.source_document_id == source_document_id)
    )
    await session.execute(
        SourceDocument.__table__.delete()
        .where(SourceDocument.source_document_id == source_document_id)
    )
    await session.flush()


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import benchmark ground truth into DB with full track traceability"
    )
    parser.add_argument(
        "--datasets", nargs="+",
        default=["rett", "clingen", "clinvar_fused", "parkinson", "merged_73"],
        choices=list(DATASET_DIRS.keys()),
    )
    parser.add_argument(
        "--ground-truth-root",
        default=str(REPO_ROOT / "benchmark" / "data" / "ground_truth"),
    )
    parser.add_argument("--entry-id", help="Import only one specific entry")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be imported")
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Drop and recreate all non-terminology tables before import",
    )
    parser.add_argument(
        "--environment",
        default="development",
        choices=["development", "staging", "production"],
        help="Database environment to use (default: development)",
    )
    return parser.parse_args()


def _configure_logger() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")


async def main() -> None:
    _configure_logger()
    args = parse_args()
    started_at = time.perf_counter()

    cfg = get_config()
    logger.info(
        "Environment: {} | DB: {}@{}:{}/{}",
        cfg.environment,
        cfg.postgresql.user or "(none)",
        cfg.postgresql.host,
        cfg.postgresql.port,
        cfg.postgresql.db,
    )

    engine = build_async_engine(cfg)

    # ── Database initialization ──
    if args.init_db:
        await _init_database(engine)

    gt_root = Path(args.ground_truth_root)
    entries = discover_entries(gt_root, args.datasets)

    if args.entry_id:
        entries = [e for e in entries if e["entry_dir"].name == args.entry_id]

    logger.info(
        "Discovered {} entries from datasets: {}",
        len(entries),
        ", ".join(args.datasets),
    )

    if args.dry_run:
        preprocessed_count = 0
        for e in entries:
            has_pre = e["extraction_path"].is_file()
            if has_pre:
                preprocessed_count += 1
            data = json.loads(e["expected_path"].read_text())
            norm = _normalize_entry(data, e["dataset"])
            id_type, id_value = _get_lit_id(norm)
            tracks = _read_preprocessed_tracks(e["extraction_path"])
            if tracks:
                track_names = tracks.get("_meta", {}).get("tracks_present", [])
                counts = {t: len(tracks.get(t, [])) for t in track_names}
                logger.info(
                    "  {} [{}] {} ({}={}, preprocessed: {})",
                    e["entry_dir"].name, e["dataset"],
                    norm["title"][:50], id_type, id_value,
                    counts,
                )
            else:
                n_ev = len(norm["expected_evidence"])
                logger.info(
                    "  {} [{}] {} ({}={}, ground_truth: {} x2 tracks)",
                    e["entry_dir"].name, e["dataset"],
                    norm["title"][:50], id_type, id_value,
                    n_ev,
                )
        logger.info(
            "Summary: {} entries ({} with preprocessed, {} ground truth only)",
            len(entries), preprocessed_count, len(entries) - preprocessed_count,
        )
        await engine.dispose()
        return

    if not entries:
        logger.warning("No entries found to import.")
        await engine.dispose()
        return

    factory = async_session_factory(engine)

    imported = 0
    failed = 0
    stats: dict[str, int] = {
        "preprocessed": 0,
        "ground_truth": 0,
        "original_items": 0,
        "translated_items": 0,
        "reconciled_items": 0,
    }

    async with factory() as session:
        async with session.begin():
            for entry_info in entries:
                data = json.loads(entry_info["expected_path"].read_text())
                norm = _normalize_entry(data, entry_info["dataset"])
                try:
                    async with session.begin_nested():
                        result = await _import_entry(
                            session, norm, entry_info["dataset"], entry_info["entry_dir"],
                        )
                    imported += 1
                    if result["has_preprocessed"]:
                        stats["preprocessed"] += 1
                    else:
                        stats["ground_truth"] += 1
                    tc = result["track_counts"]
                    stats["original_items"] += tc.get("original", 0)
                    stats["translated_items"] += tc.get("translated", 0)
                    stats["reconciled_items"] += tc.get("reconciled", 0)
                    if imported % 10 == 0:
                        logger.info("Imported {}/{} entries", imported, len(entries))
                except Exception:
                    logger.exception(
                        "Failed to import {}: {}",
                        entry_info["entry_dir"].name,
                        entry_info["expected_path"],
                    )
                    failed += 1

    logger.info(
        "Import complete: {} imported, {} failed ({:.2f}s)",
        imported, failed, time.perf_counter() - started_at,
    )
    logger.info(
        "  Preprocessed: {} entries | Ground truth: {} entries",
        stats["preprocessed"], stats["ground_truth"],
    )
    logger.info(
        "  Original: {} | Translated: {} | Reconciled: {} items",
        stats["original_items"], stats["translated_items"], stats["reconciled_items"],
    )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
