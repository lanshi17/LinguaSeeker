"""Import benchmark ground truth evidence items and literature into PostgreSQL.

Reads ground truth entries (Rett, ClinGen, ClinVar Fused) and creates
dual-track (original + translated) evidence with full source span
traceability.

For entries with preprocessed ``extraction_result.json``, imports real
pipeline extraction data including text snippets, page offsets, and
confidence scores for both original and translated tracks.

For entries without preprocessed data, creates synthetic dual-track
evidence from ``expected.json`` ground truth values.

Idempotent: cleans up previous benchmark imports before re-importing.

Usage::

    cd backend
    uv run python ../scripts/import_benchmark_ground_truth.py
    uv run python ../scripts/import_benchmark_ground_truth.py --datasets rett
    uv run python ../scripts/import_benchmark_ground_truth.py --entry-id rett_006
    uv run python ../scripts/import_benchmark_ground_truth.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
import uuid
from decimal import Decimal
from pathlib import Path

from loguru import logger

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from src.core.config import get_config  # noqa: E402
from src.dao.postgresql.connection import (  # noqa: E402
    async_session_factory,
    build_async_engine,
)
from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository  # noqa: E402
from src.dao.postgresql.models import (  # noqa: E402
    CanonicalEvidenceItem,
    EvidenceEntityBinding,
    LiteratureProfile,
    NormalizedEntity,
    ProcessingRun,
    RunEvidenceItem,
    SourceDocument,
    SourceDocumentIdentifier,
)

from sqlalchemy import select  # noqa: E402


# ── Dataset discovery ────────────────────────────────────────────────────────

DATASET_DIRS = {
    "rett": "rett",
    "clingen": "clingen",
    "clinvar_fused": "clinvar_fused",
}


def discover_entries(gt_root: Path, datasets: list[str]) -> list[dict]:
    """Walk ground truth directories and collect entry paths."""
    entries = []
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
        }

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
    }


def _get_lit_id(norm: dict) -> tuple[str, str]:
    """Return (id_type, id_value) for document deduplication."""
    if norm.get("doi"):
        return ("doi", norm["doi"])
    if norm.get("pmid"):
        return ("pmid", str(norm["pmid"]))
    return ("benchmark_id", norm["entry_id"])


# ── Hash helpers ─────────────────────────────────────────────────────────────


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def _field_id_to_category(field_id: str) -> str:
    prefix = field_id.split(".")[0] if "." in field_id else field_id
    mapping = {
        "A": "Gene and Variant",
        "B": "Case and Phenotype",
        "C": "Segregation",
        "D": "Population",
        "E": "Computational",
        "F": "Functional",
        "G": "Case-Control",
        "H": "Contradiction",
        "I": "Gene Function",
        "J": "Authority",
    }
    return mapping.get(prefix, "Other")


# ── Preprocessed data reader ────────────────────────────────────────────────


def _read_preprocessed_tracks(extraction_path: Path) -> dict | None:
    """Read extraction_result.json and return {original: [...], translated: [...]}."""
    if not extraction_path.is_file():
        return None
    try:
        data = json.loads(extraction_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    result: dict[str, list] = {}
    for track_key in ("original_result", "translated_result"):
        track_data = data.get(track_key)
        if not track_data or track_data.get("status") != "completed":
            continue
        items = track_data.get("evidence_items") or []
        track_name = "original" if track_key == "original_result" else "translated"
        result[track_name] = items

    if not result.get("original"):
        return None
    return result


def _build_evidence_specs(tracks: dict | None, norm: dict) -> list[dict]:
    """Build a unified list of evidence specs from preprocessed or ground truth data.

    Each spec describes one evidence item for one track, with source span
    for traceability.
    """
    specs: list[dict] = []
    seen_keys: set[tuple] = set()

    if tracks:
        for track_name in ("original", "translated"):
            for item in tracks.get(track_name, []):
                field_id = item.get("field_id", "")
                if "." not in field_id:
                    continue
                status = item.get("status", "found")
                value = str(item.get("value", ""))
                if status != "found" and (not value or value == "None"):
                    continue
                group_id = item.get("group_id", "")
                dedup_key = (field_id, track_name, group_id)
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                specs.append({
                    "track": track_name,
                    "field_id": field_id,
                    "value": value,
                    "confidence": float(item.get("confidence", 1.0)),
                    "status": status,
                    "source_span": item.get("source") or {},
                    "raw_source": item.get("raw_source") or {},
                    "group_id": group_id,
                    "target_gene": item.get("target_gene", ""),
                    "target_disease": item.get("target_disease", ""),
                    "field_name": item.get("field_name", ""),
                    "category": item.get("category", ""),
                    "notes": item.get("notes", ""),
                    "evidence_role": item.get("evidence_role", "primary"),
                    "acmg_codes": item.get("assigned_acmg_codes") or [],
                    "article_language": item.get("article_language", ""),
                    "data_source": "preprocessed",
                })
    else:
        for ev in norm.get("expected_evidence", []):
            field_id = ev.get("field_id", "")
            value = str(ev.get("value", ""))
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
                    "article_language": norm.get("language", "en") if track_name == "original" else "en",
                    "data_source": "ground_truth",
                })

    return specs


# ── Core import ──────────────────────────────────────────────────────────────


async def _import_entry(
    session,
    norm: dict,
    dataset: str,
    entry_dir: Path,
) -> dict:
    """Import one ground truth entry with dual-track traceability.

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

    # ── Read source.md for article text storage ──
    source_md_path = entry_dir / "source.md"
    article_text_length = 0
    if source_md_path.is_file():
        try:
            article_text_length = len(source_md_path.read_text(encoding="utf-8"))
        except OSError:
            pass

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

    session.add(SourceDocument(
        source_document_id=source_document_id,
        raw_metadata={
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
            "has_preprocessed": has_preprocessed,
            "article_text_chars": article_text_length,
            "has_source_md": source_md_path.is_file(),
            "dual_track": True,
        },
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
    session.add(ProcessingRun(
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        parser_version="benchmark_ground_truth",
        extraction_version="benchmark_ground_truth",
        run_status="completed",
        input_artifacts={
            "dataset": dataset,
            "entry_id": entry_id,
            "data_source": "preprocessed" if has_preprocessed else "ground_truth",
        },
        output_artifacts={
            "evidence_count": evidence_count,
            "tracks": ["original", "translated"],
        },
    ))
    await session.flush()

    # ── Normalized entities ──
    gene_entity_id = await _upsert_entity(
        session, "gene", norm["hgnc_id"], norm["gene_symbol"],
        norm["gene_symbol"], {"hgnc_id": norm["hgnc_id"], "dataset": dataset},
    )
    disease_entity_id = await _upsert_entity(
        session, "disease", norm["mondo_id"], norm["disease_label"],
        norm["disease_label"], {"mondo_id": norm["mondo_id"], "dataset": dataset},
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
                "dataset": dataset,
            },
        )
        if eid:
            variant_entities[display] = eid

    # ── Dual-track evidence items ──
    track_counts = {"original": 0, "translated": 0}

    for spec in specs:
        track = spec["track"]
        field_id = spec["field_id"]
        value_str = spec["value"]
        group_id = spec.get("group_id") or f"gene={norm['gene_symbol']}|variant=__missing__"

        # Include track and group_id in position_hash so original/translated
        # and different groups are distinct canonical items.
        position_hash = _hash(entry_id, field_id, track, group_id)
        text_hash = _hash(value_str)
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
            value=value_str,
            confidence=Decimal(str(min(spec.get("confidence", 1.0), 1.0))),
            position_hash=position_hash,
            text_hash=text_hash,
            entity_scope_hash=entity_scope_hash,
            source_span=source_span,
            raw_payload={
                "dataset": dataset,
                "group_id": group_id,
                "target_gene": spec.get("target_gene", ""),
                "target_disease": spec.get("target_disease", ""),
                "notes": spec.get("notes", ""),
                "evidence_role": spec.get("evidence_role", "primary"),
                "acmg_codes": spec.get("acmg_codes", []),
                "article_language": spec.get("article_language", ""),
                "data_source": spec.get("data_source", ""),
                "raw_source": spec.get("raw_source", {}),
                "field_name": spec.get("field_name", ""),
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
                "value": value_str,
                "group_id": group_id,
                "track": track,
                "field_id": field_id,
                "field_name": spec.get("field_name", field_id),
                "source": "benchmark_ground_truth",
                "entity_id": str(gene_entity_id) if gene_entity_id else None,
                "status": spec.get("status", "found"),
                "confidence": spec.get("confidence", 1.0),
                "category": category,
                "text_snippet": (spec.get("source_span") or {}).get("text_snippet", ""),
                "page": (spec.get("source_span") or {}).get("page"),
                "data_source": spec.get("data_source", ""),
            },
        )
        session.add(canonical)
        await session.flush()

        # ── Evidence entity bindings ──
        bindings = [("gene", gene_entity_id, norm["gene_symbol"])]
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
        "original_count": track_counts.get("original", 0),
        "translated_count": track_counts.get("translated", 0),
    }


# ── Entity helpers ───────────────────────────────────────────────────────────


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
        from src.dao.postgresql.models import ChatMessage, ReviewAuditEvent
        await session.execute(
            ReviewAuditEvent.__table__.delete()
            .where(ReviewAuditEvent.canonical_evidence_id.in_(canonical_ids))
        )
        await session.execute(
            ChatMessage.__table__.delete()
            .where(ChatMessage.evidence_id.in_(canonical_ids))
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
        description="Import benchmark ground truth into DB with dual-track traceability"
    )
    parser.add_argument(
        "--datasets", nargs="+",
        default=["rett", "clingen", "clinvar_fused"],
        choices=list(DATASET_DIRS.keys()),
    )
    parser.add_argument(
        "--ground-truth-root",
        default=str(REPO_ROOT / "benchmark" / "data" / "ground_truth"),
    )
    parser.add_argument("--entry-id", help="Import only one specific entry")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be imported")
    return parser.parse_args()


def _configure_logger() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")


async def main() -> None:
    _configure_logger()
    args = parse_args()
    started_at = time.perf_counter()

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
                n_orig = len(tracks.get("original", []))
                n_trans = len(tracks.get("translated", []))
                logger.info(
                    "  {} [{}] {} ({}={}, preprocessed: {} orig + {} trans)",
                    e["entry_dir"].name, e["dataset"],
                    norm["title"][:50], id_type, id_value,
                    n_orig, n_trans,
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
        return

    if not entries:
        logger.warning("No entries found to import.")
        return

    cfg = get_config()
    engine = build_async_engine(cfg)
    factory = async_session_factory(engine)

    imported = 0
    failed = 0
    stats = {"preprocessed": 0, "ground_truth": 0, "original_items": 0, "translated_items": 0}

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
                    stats["original_items"] += result["original_count"]
                    stats["translated_items"] += result["translated_count"]
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
        "  Original track: {} items | Translated track: {} items",
        stats["original_items"], stats["translated_items"],
    )


if __name__ == "__main__":
    asyncio.run(main())
