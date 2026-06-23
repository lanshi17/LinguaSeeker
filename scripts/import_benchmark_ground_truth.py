"""Import benchmark ground truth evidence items and literature into PostgreSQL.

Reads ``expected.json`` from each ground truth entry directory (Rett, ClinGen,
ClinVar Fused) and creates the corresponding database records:

- ``source_documents`` with literature metadata
- ``source_document_identifiers`` (PMID, DOI, PMC)
- ``processing_runs`` (synthetic benchmark import run)
- ``run_evidence_items`` (ground truth evidence, confidence=1.0)
- ``canonical_evidence_items`` (canonical records, review_status=approved)
- ``normalized_entities`` (gene, disease, variant entities)
- ``evidence_entity_bindings``
- ``literature_profiles`` (refreshed via LiteratureProfileRepository)

Idempotent: cleans up previous benchmark imports before re-importing.

Usage::

    cd backend
    uv run python ../scripts/import_benchmark_ground_truth.py
    uv run python ../scripts/import_benchmark_ground_truth.py --datasets rett
    uv run python ../scripts/import_benchmark_ground_truth.py --entry-id rett_001
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
    """Walk ground truth directories and collect expected.json paths."""
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
                })
    return entries


# ── Data normalization ───────────────────────────────────────────────────────


def _normalize_entry(data: dict, dataset: str) -> dict:
    """Normalize different expected.json schemas into a uniform structure."""
    entry_id = data["entry_id"]

    if dataset == "rett":
        variants = []
        for v in data.get("variants", []):
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


def _build_group_id(gene_symbol: str, field_id: str, ev: dict) -> str:
    """Build a group_id consistent with the pipeline format."""
    variant_value = ""
    if "variant" in field_id.lower():
        variant_value = str(ev.get("value", ""))
    elif ev.get("candidates"):
        variant_value = ""
    if variant_value:
        return f"gene={gene_symbol}|variant={variant_value}"
    return f"gene={gene_symbol}|variant=__missing__"


# ── Core import ──────────────────────────────────────────────────────────────


async def _import_entry(session, norm: dict, dataset: str) -> None:
    """Import one ground truth entry into the database."""
    entry_id = norm["entry_id"]
    id_type, id_value = _get_lit_id(norm)

    # Find existing source document by identifier.
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

    source_document_id = uuid.uuid4()
    processing_run_id = uuid.uuid4()

    # ── SourceDocument ──
    year_val = None
    if norm.get("year"):
        try:
            year_val = int(norm["year"])
        except (ValueError, TypeError):
            pass

    source_doc = SourceDocument(
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
        },
    )
    session.add(source_doc)
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
    session.add(ProcessingRun(
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        parser_version="benchmark_ground_truth",
        extraction_version="benchmark_ground_truth",
        run_status="completed",
        input_artifacts={"dataset": dataset, "entry_id": entry_id},
        output_artifacts={"evidence_count": len(norm["expected_evidence"])},
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

    # ── RunEvidenceItem + CanonicalEvidenceItem + bindings ──
    for ev in norm["expected_evidence"]:
        field_id = ev["field_id"]
        value_str = str(ev.get("value", ""))
        group_id = _build_group_id(norm["gene_symbol"], field_id, ev)

        position_hash = _hash(entry_id, field_id)
        text_hash = _hash(value_str)
        entity_scope_hash = _hash(norm["gene_symbol"], norm.get("disease_label", ""))

        run_ev_item = RunEvidenceItem(
            processing_run_id=processing_run_id,
            source_document_id=source_document_id,
            track="ground_truth",
            field_id=field_id,
            status="found",
            value=value_str,
            confidence=Decimal("1.0000"),
            position_hash=position_hash,
            text_hash=text_hash,
            entity_scope_hash=entity_scope_hash,
            source_span={"source": "benchmark_ground_truth", "entry_id": entry_id},
            raw_payload={
                "dataset": dataset,
                "evaluation_type": ev.get("evaluation_type", ""),
                "candidates": ev.get("candidates", []),
            },
        )
        session.add(run_ev_item)
        await session.flush()

        canonical = CanonicalEvidenceItem(
            source_document_id=source_document_id,
            field_id=field_id,
            position_hash=position_hash,
            text_hash=text_hash,
            entity_scope_hash=entity_scope_hash,
            current_best_run_evidence_id=run_ev_item.run_evidence_item_id,
            current_best_status="found",
            current_best_confidence=Decimal("1.0000"),
            conflict_flag=False,
            review_status="approved",
            active_payload={
                "value": value_str,
                "group_id": group_id,
                "track": "ground_truth",
                "field_id": field_id,
                "field_name": field_id,
                "source": "benchmark_ground_truth",
                "entity_id": str(gene_entity_id) if gene_entity_id else None,
                "status": "found",
                "confidence": 1.0,
                "category": _field_id_to_category(field_id),
            },
        )
        session.add(canonical)
        await session.flush()

        # Evidence entity bindings.
        bindings = [("gene", gene_entity_id, norm["gene_symbol"])]
        if disease_entity_id:
            bindings.append(("disease", disease_entity_id, norm["disease_label"]))
        for vname, veid in variant_entities.items():
            bindings.append(("variant", veid, vname))

        for rank, (role, eid, raw_text) in enumerate(bindings):
            if eid is None:
                continue
            session.add(EvidenceEntityBinding(
                run_evidence_item_id=run_ev_item.run_evidence_item_id,
                entity_id=eid,
                entity_type=role,
                role=role,
                binding_rank=rank,
                raw_entity_text=raw_text,
            ))

    await session.flush()

    # ── LiteratureProfile ──
    repo = LiteratureProfileRepository(session)
    await repo.refresh_for_document(source_document_id)


def _field_id_to_category(field_id: str) -> str:
    """Map field_id prefix to ACMG evidence category name."""
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
    parser = argparse.ArgumentParser(description="Import benchmark ground truth into DB")
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
        for e in entries:
            data = json.loads(e["expected_path"].read_text())
            norm = _normalize_entry(data, e["dataset"])
            id_type, id_value = _get_lit_id(norm)
            logger.info(
                "  {} [{}] {} ({}={}, {} evidence items)",
                e["entry_dir"].name,
                e["dataset"],
                norm["title"][:60],
                id_type,
                id_value,
                len(norm["expected_evidence"]),
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

    async with factory() as session:
        async with session.begin():
            for entry_info in entries:
                data = json.loads(entry_info["expected_path"].read_text())
                norm = _normalize_entry(data, entry_info["dataset"])
                try:
                    await _import_entry(session, norm, entry_info["dataset"])
                    imported += 1
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
        imported,
        failed,
        time.perf_counter() - started_at,
    )


if __name__ == "__main__":
    asyncio.run(main())
