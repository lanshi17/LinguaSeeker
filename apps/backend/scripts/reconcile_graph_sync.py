from __future__ import annotations

import argparse

from loguru import logger

from src.database.postgre_client import get_postgres_client
from src.database.models import EvidenceRecord
from src.domain.graph.sync import GraphSyncService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile Neo4j from PostgreSQL evidence records")
    parser.add_argument("--limit", type=int, default=0, help="Max records to sync (0 means all)")
    parser.add_argument("--init-schema", action="store_true", help="Initialize Neo4j schema before syncing")
    parser.add_argument("--dry-run", action="store_true", help="Only count records")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    pg = get_postgres_client()
    sync_service = GraphSyncService()

    if args.init_schema:
        sync_service._neo4j.initialize_schema()

    with pg.session_scope() as session:
        query = session.query(EvidenceRecord).order_by(EvidenceRecord.evidence_id.asc())
        if args.limit and args.limit > 0:
            query = query.limit(args.limit)
        records = query.all()

    logger.info("Fetched {} evidence record(s)", len(records))

    if args.dry_run:
        return

    synced = 0
    for rec in records:
        sync_service._sync_to_neo4j(
            document_id=rec.document_id,
            evidence_id=str(rec.evidence_id),
            gene_symbol=rec.gene_symbol or "",
            variant_hgvs_c=rec.variant_hgvs_c or "",
            variant_hgvs_p=rec.variant_hgvs_p or "",
            transcript_id=rec.transcript_id or "",
            disease_name=rec.disease_name or "",
            icd10=rec.icd10_code or "",
            phenotype_desc=rec.phenotype or "",
            species=rec.species or "",
            strength=rec.evidence_strength or "",
            classification=rec.evidence_classification or "",
            overall_conf=rec.overall_confidence or 0.0,
        )
        synced += 1

    logger.info("Synced {} record(s) to Neo4j", synced)


if __name__ == "__main__":
    main()
