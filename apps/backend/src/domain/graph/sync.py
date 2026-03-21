"""
图数据同步模块
在 Pipeline 产出证据后，将结构化数据同步写入 Neo4j 图数据库和 PostgreSQL，
保持两侧数据的一致性。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy.exc import ProgrammingError as SAProgrammingError, SQLAlchemyError

from src.config import get_settings
from src.infrastructure.neo4j import get_neo4j_client, Neo4jClient
from src.infrastructure.postgres import get_postgres_client, PostgresClient
from src.domain.variant import get_variation_data_service, VariationDataService
from src.domain.graph.structural_variant_parser import (
    parse_structural_variant,
    StructuralVariantParseResult,
)
from src.utils.exceptions import ValidationException


class SchemaSyncError(RuntimeError):
    """Raised when the relational schema is not aligned with ORM expectations."""

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.context: Dict[str, Any] = context or {}
        self.original_exception = original


class GraphSyncService:
    """Neo4j ↔ PostgreSQL 证据同步服务"""

    _CORE_FIELD_LABELS: Dict[str, str] = {
        "gene_symbol": "gene_symbol",
        "variant_descriptor": "variant_hgvs",
        "transcript_id": "transcript_id",
        "disease_name": "disease_name",
    }
    _FIELD_ALIAS_MAP: Dict[str, List[str]] = {
        "gene_symbol": [
            "gene_symbol",
            "gene",
            "geneSymbol",
            "symbol",
            "gene_name",
            "hugo_symbol",
            "hgnc_symbol",
            "hgnc_gene_symbol",
            "approved_symbol",
            "official_gene_symbol",
            "gene_id",
            "GeneID",
            "GENEINFO",
            "GeneSymbol",
            "entrez_gene",
            "ncbi_gene",
            "locus",
            "locus_symbol",
            "gene_locus",
            "gene_abbreviation",
        ],
        "variant_hgvs_c": [
            "variant_hgvs_c",
            "hgvs_c",
            "c_hgvs",
            "cdna_change",
            "variant_descriptor",
            "CLNHGVS",
            "coding_change",
            "coding_dna_change",
            "c_notation",
            "c_dot",
            "cDNA_change",
            "cdna_variant",
            "cds_change",
            "nucleotide_change",
            "nucleotide_variant",
            "coding_sequence",
            "transcript_variant",
            "HGVSc",
            "hgvs_coding",
            "coding_hgvs",
            "c_nomenclature",
            "HGVSc_VEP",
            "HGVS_CODING",
            "dna_change",
            "mutation_cdna",
            "cdna_mutation",
            "coding_mutation",
            "transcript_change",
            "c_variant",
            "coding_variant",
        ],
        "variant_hgvs_p": [
            "variant_hgvs_p",
            "hgvs_p",
            "protein_change",
            "aa_change",
            "amino_acid_change",
            "amino_acid_substitution",
            "aa_substitution",
            "p_notation",
            "p_dot",
            "protein_variant",
            "protein_mutation",
            "aa_variant",
            "aa_mutation",
            "HGVSp",
            "hgvs_protein",
            "protein_hgvs",
            "p_nomenclature",
            "ProteinChange",
            "HGVSp_VEP",
            "HGVS_PROTEIN",
            "AAChange",
            "Protein_Change",
            "amino_acid_alteration",
            "peptide_change",
            "residue_change",
            "mutation_protein",
            "protein_alteration",
            "protein_consequence",
        ],
        "variant_descriptor": [
            "variant_descriptor",
            "hgvs",
            "hgvs_form",
            "variant_name",
            "variant_notation",
            "variant_id",
        ],
        "transcript_id": [
            "transcript_id",
            "transcript",
            "transcriptId",
            "refseq_id",
            "refseq",
            "refseq_transcript",
            "nm_number",
            "nm_id",
            "NM",
            "transcript_accession",
            "accession_number",
            "transcript_version",
            "mrna_accession",
            "mrna_id",
            "mrna",
            "mrna_reference",
            "ensembl_transcript",
            "ensembl_transcript_id",
            "ENST",
            "transcript_reference",
            "reference_transcript",
            "canonical_transcript",
            "transcript_name",
            "isoform",
            "isoform_id",
            "Feature",
            "Transcript_ID",
        ],
        "disease_name": [
            "disease_name",
            "disease",
            "condition",
            "diseaseLabel",
            "disorder",
            "clinical_diagnosis",
            "diagnosis",
            "clinical_phenotype",
            "disease_phenotype",
            "CLNDN",
            "PhenotypeList",
            "condition_name",
            "clinical_condition",
            "disease_term",
            "disease_label",
            "mondo_term",
            "mondo_label",
            "omim_phenotype",
            "omim_disorder",
            "orphanet_disorder",
            "indication",
            "presentation",
            "syndrome",
            "pathology",
            "medical_condition",
            "disorder_name",
            "disease_description",
        ],
    }
    _MISSING_FIELD_COUNTER: Counter[str] = Counter()
    _MISSING_FIELD_ALERT_THRESHOLD: int = 5
    _FAILURE_ARCHIVE_PATH: Path = Path(
        "logs/evidence_failure_archive.jsonl"
    ).expanduser()

    def __init__(self) -> None:
        cfg = get_settings()
        self._neo4j: Neo4jClient = get_neo4j_client()
        self._pg: PostgresClient = get_postgres_client()
        self._variants: VariationDataService = get_variation_data_service()
        self._validity_threshold: float = getattr(
            cfg, "evidence_validity_threshold", 85.0
        )
        self._review_floor: float = getattr(
            cfg, "evidence_review_floor", max(self._validity_threshold - 20, 0.0)
        )
        self._missing_field_alert_threshold: int = int(
            getattr(cfg, "evidence_failure_alert_threshold", 5)
        )
        self._failure_archive_path: Path = Path(
            getattr(
                cfg,
                "evidence_failure_archive_path",
                "logs/evidence_failure_archive.jsonl",
            )
        ).expanduser()
        logger.info("GraphSyncService initialized")

    # ==================== 核心同步入口 ====================

    def sync_evidence(
        self,
        document_id: str,
        evidence_output: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        将一次 Pipeline 运行的证据结果同步到 Neo4j 和 PostgreSQL。

        参数:
            document_id:     PostgreSQL documents 表中的文档 ID
            evidence_output: EvidenceOutput.dict() 格式

        返回:
            {"pg_evidence_id": int, "neo4j_synced": bool}
        """

        raw_document_id = str(document_id).strip()
        logger.info("Syncing evidence for document {}", raw_document_id)
        evidence_keys = (
            list(evidence_output.keys()) if isinstance(evidence_output, dict) else []
        )
        logger.debug("Full evidence_output keys: {}", evidence_keys)
        ps3 = self._normalize_ps3_payload(evidence_output.get("ps3_evidence"))
        extracted_payload = evidence_output.get("extracted_fields")
        if extracted_payload is None:
            nested_extracted = ps3.get("extracted_fields")
            if isinstance(nested_extracted, dict):
                extracted_payload = nested_extracted
                logger.debug(
                    "Using ps3_evidence.extracted_fields fallback for document {}",
                    raw_document_id,
                )
        extracted = self._sanitize_extracted_fields(
            extracted_payload,
            document_id=raw_document_id,
        )
        logger.debug("Extracted fields sanitized: {}", bool(extracted))
        evidence_quality = self._as_dict(ps3.get("evidence_quality"))
        classification = (
            self._normalize_string(evidence_output.get("evidence_classification"))
            or self._normalize_string(evidence_quality.get("evidence_classification"))
            or ""
        )
        overall_conf_source = evidence_output.get("overall_confidence")
        if overall_conf_source is None:
            overall_conf_source = evidence_quality.get("overall_confidence")
        overall_conf = self._coerce_confidence(overall_conf_source)
        acmg_levels_source = evidence_output.get("acmg_evidence_levels")
        if not isinstance(acmg_levels_source, list):
            acmg_levels_source = evidence_quality.get("acmg_evidence_levels")
        acmg_levels = (
            [
                level.strip()
                for level in acmg_levels_source
                if isinstance(level, str) and level.strip()
            ]
            if isinstance(acmg_levels_source, list)
            else []
        )
        strength = (
            self._normalize_string(evidence_output.get("final_evidence_strength")) or ""
        )
        arbitration_score = self._coerce_optional_float(
            evidence_output.get("arbitration_score")
        )

        # 提取各字段
        gene_info = self._as_dict(extracted.get("gene"))
        variant_info = self._as_dict(extracted.get("variant"))
        transcript_info = self._as_dict(extracted.get("transcript_id"))
        ref_genome_info = self._as_dict(extracted.get("reference_genome_version"))
        disease_chpo = self._as_dict(extracted.get("disease_chpo"))
        disease_icd10 = self._as_dict(extracted.get("disease_icd10"))
        disease_info = disease_chpo or disease_icd10
        species_info = self._as_dict(extracted.get("species"))
        phenotype_info = self._as_dict(extracted.get("phenotype"))

        extracted_candidates = {
            "gene_symbol": {
                "value": gene_info.get("symbol"),
                "source": "extracted_fields.gene.symbol",
                "section_present": bool(gene_info),
            },
            "variant_hgvs_c": {
                "value": variant_info.get("hgvs_c"),
                "source": "extracted_fields.variant.hgvs_c",
                "section_present": bool(variant_info),
            },
            "variant_hgvs_p": {
                "value": variant_info.get("hgvs_p"),
                "source": "extracted_fields.variant.hgvs_p",
                "section_present": bool(variant_info),
            },
            "transcript_id": {
                "value": transcript_info.get("transcript_id"),
                "source": "extracted_fields.transcript_id.transcript_id",
                "section_present": bool(transcript_info),
            },
            "disease_name": {
                "value": disease_info.get("disease_name"),
                "source": "extracted_fields.disease.disease_name",
                "section_present": bool(disease_info),
            },
            "variant_descriptor": {
                "value": variant_info.get("hgvs_c") or variant_info.get("hgvs_p"),
                "source": "extracted_fields.variant",
                "section_present": bool(variant_info),
            },
        }
        fused_core, resolution_details = self._resolve_core_fields(
            evidence_output, extracted_candidates
        )

        gene_symbol = fused_core.get("gene_symbol") or ""
        variant_hgvs_c = fused_core.get("variant_hgvs_c") or ""
        variant_hgvs_p = fused_core.get("variant_hgvs_p") or ""
        protein_change = variant_hgvs_p  # 同义
        transcript_id = fused_core.get("transcript_id") or ""
        ref_genome = self._normalize_string(ref_genome_info.get("version")) or ""
        disease_name = fused_core.get("disease_name") or ""
        structural_hint: Dict[str, Any] = {}
        structural_candidate = fused_core.get("_structural_variant")
        if isinstance(structural_candidate, dict):
            structural_hint = structural_candidate
            if isinstance(extracted, dict):
                extracted["_structural_variant"] = structural_candidate
        icd10 = (
            self._normalize_string(disease_info.get("icd10_code"))
            if disease_info
            else ""
        )
        species = self._normalize_string(species_info.get("species_name")) or ""
        phenotype_desc = (
            self._normalize_string(phenotype_info.get("phenotype_description")) or ""
        )

        variant_descriptor = (
            fused_core.get("variant_descriptor")
            or variant_hgvs_c
            or variant_hgvs_p
            or ""
        )
        validity_status, validity_reason = self._determine_validity_status(
            overall_conf, extracted
        )

        variation_id: Optional[int] = None
        if variant_hgvs_c:
            try:
                variation = self._variants.resolve_variation(variant_hgvs_c)
                if variation:
                    variation_id = int(variation.variation_id)
            except Exception as exc:
                logger.warning(
                    "ClinVar resolution failed for {}: {}", variant_hgvs_c, exc
                )

        logger.debug(
            "Evidence payload summary for document {} => gene={}, variant_c={}, variant_p={}, strength={}, classification={}, confidence={}",
            document_id,
            gene_symbol or "-",
            variant_hgvs_c or "-",
            variant_hgvs_p or "-",
            strength or "unknown",
            classification or "unknown",
            overall_conf,
        )
        logger.debug(
            "Evidence metadata detail for document {} => transcript={}, ref_genome={}, disease={}, icd10={}, phenotype={}, species={}",
            document_id,
            transcript_id or "-",
            ref_genome or "-",
            disease_name or "-",
            icd10 or "-",
            phenotype_desc or "-",
            species or "-",
        )
        logger.info(
            "Evidence confidence {:.2f} mapped to validity status={} (threshold={} review_floor={})",
            overall_conf,
            validity_status,
            self._validity_threshold,
            self._review_floor,
        )

        try:
            coerce_uuid = getattr(self._pg, "_coerce_uuid", None)
            if callable(coerce_uuid):
                uuid_document_id = coerce_uuid(raw_document_id)
            else:
                uuid_document_id = UUID(raw_document_id)
        except ValueError as exc:
            if raw_document_id.isdigit():
                uuid_document_id = UUID(int=int(raw_document_id))
            else:
                logger.error("Invalid document_id format: {}", raw_document_id)
                raise ValueError(
                    f"Invalid document_id format: {raw_document_id}"
                ) from exc

        canonical_document_id = str(uuid_document_id)
        document_id = canonical_document_id

        core_field_map = {
            "gene_symbol": gene_symbol,
            "variant_descriptor": variant_descriptor,
            "transcript_id": transcript_id,
            "disease_name": disease_name,
        }
        integrity_context = self._snapshot_context(
            canonical_document_id,
            gene_symbol=gene_symbol,
            variant_hgvs_c=variant_hgvs_c,
            variant_hgvs_p=variant_hgvs_p,
            transcript_id=transcript_id,
            disease_name=disease_name,
        )
        integrity_context["field_resolution"] = resolution_details
        integrity_context["validity_status"] = validity_status
        integrity_context["validity_reason"] = validity_reason
        if structural_hint:
            integrity_context["structural_variant"] = structural_hint

        manual_review_required = bool(structural_hint)
        manual_review_detail: Optional[Dict[str, Any]] = None
        missing_core_fields = self._missing_core_fields(core_field_map, structural_hint)
        if missing_core_fields:
            can_continue = self._can_continue_with_structural_fallback(
                missing_core_fields,
                structural_hint,
            )
            if not can_continue:
                field_diagnostics = {
                    field: {
                        "status": resolution_details.get(field, {}).get(
                            "status", "unknown"
                        ),
                        "aliases_checked": resolution_details.get(field, {}).get(
                            "aliases_checked",
                            [],
                        ),
                        "reasons": resolution_details.get(field, {}).get("reasons", []),
                        "source": resolution_details.get(field, {}).get("source"),
                    }
                    for field in missing_core_fields
                }
                logger.warning(
                    "Skipping evidence insert for document {} | "
                    "missing_core_fields={} | per_field_diagnostics={} | "
                    "structural_hint={} | validity={}",
                    canonical_document_id,
                    missing_core_fields,
                    field_diagnostics,
                    structural_hint,
                    validity_status,
                )
                self._log_document_summary(
                    canonical_document_id,
                    success=False,
                    summary={
                        "gene_symbol": gene_symbol,
                        "variant_hgvs_c": variant_hgvs_c,
                        "variant_hgvs_p": variant_hgvs_p,
                        "transcript_id": transcript_id,
                        "disease_name": disease_name,
                        "confidence": overall_conf,
                        "validity_status": validity_status,
                    },
                )
                self._archive_failure_case(
                    canonical_document_id,
                    reason="missing_core_fields",
                    missing_fields=missing_core_fields,
                    resolution_details=resolution_details,
                )
                self._track_missing_fields(missing_core_fields)
                if self._should_mark_manual_review_on_skip(
                    missing_core_fields,
                    gene_symbol,
                    disease_name,
                    transcript_id,
                ):
                    skip_detail = {
                        "reason": "missing_structural_variant",
                        "missing_fields": missing_core_fields,
                        "structural_hint": structural_hint,
                    }
                    self._mark_pending_manual_review(
                        uuid_document_id,
                        skip_detail,
                        resolution_details,
                    )
                retryable = any(
                    "not_provided" in details.get("reasons", [])
                    or "section_missing" in details.get("reasons", [])
                    or "empty_string" in details.get("reasons", [])
                    for field, details in resolution_details.items()
                    if field in self._CORE_FIELD_LABELS
                )
                return {
                    "pg_evidence_id": None,
                    "neo4j_synced": False,
                    "skipped": True,
                    "reason": "missing_core_fields",
                    "missing_fields": missing_core_fields,
                    "context": integrity_context,
                    "retryable": retryable,
                }
            manual_review_required = True
            manual_review_detail = {
                "reason": "structural_cnv_missing_hgvs",
                "missing_fields": list(missing_core_fields),
                "structural_hint": structural_hint,
            }
            missing_core_fields = []

        if structural_hint and manual_review_detail is None:
            manual_review_detail = {
                "reason": "synthetic_structural_descriptor",
                "missing_fields": [],
                "structural_hint": structural_hint,
            }
        if manual_review_detail:
            integrity_context["pending_manual_review"] = manual_review_detail

        # 1) --- PostgreSQL ---
        # Apply field length truncation as safety layer to prevent DB constraint violations
        gene_symbol_safe = (
            self._truncate_field(gene_symbol, 100) if gene_symbol else None
        )
        variant_hgvs_c_safe = (
            self._truncate_field(variant_hgvs_c, 500) if variant_hgvs_c else None
        )
        variant_hgvs_p_safe = (
            self._truncate_field(variant_hgvs_p, 500) if variant_hgvs_p else None
        )
        protein_change_safe = (
            self._truncate_field(protein_change, 500) if protein_change else None
        )
        transcript_id_safe = (
            self._truncate_field(transcript_id, 100) if transcript_id else None
        )
        ref_genome_safe = self._truncate_field(ref_genome, 50) if ref_genome else None
        disease_name_safe = (
            self._truncate_field(disease_name, 500) if disease_name else None
        )
        icd10_safe = self._truncate_field(icd10, 50) if icd10 else None
        species_safe = self._truncate_field(species, 100) if species else None
        strength_safe = self._truncate_field(strength, 50) if strength else None
        classification_safe = (
            self._truncate_field(classification, 100) if classification else None
        )

        try:
            logger.debug(
                "Attempting to create evidence record with extracted_fields: {}",
                bool(extracted),
            )
            pg_record = self._pg.create_evidence_record(
                document_id=uuid_document_id,
                gene_symbol=gene_symbol_safe,
                variant_hgvs_c=variant_hgvs_c_safe,
                variant_hgvs_p=variant_hgvs_p_safe,
                protein_change=protein_change_safe,
                clinvar_variation_id=variation_id,
                transcript_id=transcript_id_safe,
                reference_genome=ref_genome_safe,
                disease_name=disease_name_safe,
                icd10_code=icd10_safe,
                species=species_safe,
                phenotype=phenotype_desc or None,
                evidence_strength=strength_safe,
                evidence_classification=classification_safe,
                overall_confidence=overall_conf,
                arbitration_score=arbitration_score,
                is_valid=validity_status,
                acmg_levels={"levels": acmg_levels} if acmg_levels else None,
                extracted_fields=extracted or None,
                ps3_evidence=ps3 or None,
            )
            evidence_id = pg_record.evidence_id
            logger.info("PostgreSQL evidence_record created: id={}", evidence_id)
        except ValidationException as exc:
            logger.warning(
                "Validation error when creating evidence record for document {}: {} | context={}",
                canonical_document_id,
                exc,
                integrity_context,
            )
            return {
                "pg_evidence_id": None,
                "neo4j_synced": False,
                "skipped": True,
                "reason": "validation_exception",
                "error": str(exc),
                "context": integrity_context,
            }
        except SAProgrammingError as exc:
            logger.error(
                "Schema mismatch when creating evidence record for document {}: {} | context={}",
                canonical_document_id,
                exc,
                integrity_context,
            )
            raise SchemaSyncError(
                "Schema mismatch while writing evidence record",
                context=integrity_context,
                original=exc,
            ) from exc
        except SQLAlchemyError as exc:
            logger.error(
                "Database error when creating evidence record for document {}: {} | context={}",
                canonical_document_id,
                exc,
                integrity_context,
            )
            raise
        except Exception as exc:
            logger.error(
                "Unexpected error when creating evidence record for document {}: {} | context={}",
                canonical_document_id,
                exc,
                integrity_context,
            )
            raise

        if manual_review_required:
            review_detail = dict(manual_review_detail or {})
            review_detail.setdefault("missing_fields", [])
            review_detail.setdefault("structural_hint", structural_hint)
            review_detail["evidence_id"] = evidence_id
            self._mark_pending_manual_review(
                uuid_document_id,
                review_detail,
                resolution_details,
            )

        if variation_id is not None:
            doc_entity = None
            get_doc = getattr(self._pg, "get_document_by_id", None)
            if callable(get_doc):
                try:
                    doc_entity = get_doc(uuid_document_id)
                except Exception as exc:
                    logger.warning(
                        "Failed to fetch document %s metadata: %s",
                        canonical_document_id,
                        exc,
                    )
            self._variants.record_internal_citation(
                variation_id=variation_id,
                document_id=canonical_document_id,
                evidence_strength=strength,
                pmid=getattr(doc_entity, "pmid", None) if doc_entity else None,
                metadata={
                    "evidence_id": evidence_id,
                    "overall_confidence": overall_conf,
                },
            )

        # 2) --- Neo4j ---
        neo4j_ok = False
        try:
            self._sync_to_neo4j(
                document_id=canonical_document_id,
                evidence_id=str(evidence_id),
                gene_symbol=gene_symbol,
                variant_hgvs_c=variant_hgvs_c,
                variant_hgvs_p=variant_hgvs_p,
                variation_id=variation_id,
                transcript_id=transcript_id,
                disease_name=disease_name,
                icd10=icd10,
                phenotype_desc=phenotype_desc,
                species=species,
                strength=strength,
                classification=classification,
                overall_conf=overall_conf,
                structural_hint=structural_hint,
            )
            neo4j_ok = True
        except Exception as e:
            logger.error("Neo4j sync failed for evidence {}: {}", evidence_id, e)
        logger.info(
            "Sync complete for document {} (neo4j_ok={})",
            canonical_document_id,
            neo4j_ok,
        )
        self._log_document_summary(
            canonical_document_id,
            success=True,
            summary={
                "gene_symbol": gene_symbol,
                "variant_hgvs_c": variant_hgvs_c,
                "variant_hgvs_p": variant_hgvs_p,
                "transcript_id": transcript_id,
                "disease_name": disease_name,
                "confidence": overall_conf,
                "validity_status": validity_status,
            },
        )

        return {
            "pg_evidence_id": evidence_id,
            "neo4j_synced": neo4j_ok,
        }

    @staticmethod
    def _coerce_confidence(value: Any, default: float = 0.0) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid overall_confidence value {!r}, defaulting to {}",
                value,
                default,
            )
            return default

    @staticmethod
    def _coerce_optional_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            logger.warning("Invalid float-like value {!r}, defaulting to None", value)
            return None

    @staticmethod
    def _normalize_ps3_payload(payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            normalized = dict(payload)
        else:
            logger.warning(
                "ps3_evidence payload is not a dict (type={}), defaulting to empty JSON",
                type(payload),
            )
            normalized = {}
        normalized.setdefault("annotation_schema_version", "1.0")
        return normalized

    @classmethod
    def _missing_core_fields(
        cls,
        core_fields: Dict[str, Optional[str]],
        structural_hint: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        missing: List[str] = []
        structural_substitute = bool(
            structural_hint
            and structural_hint.get("exon_range")
            and structural_hint.get("transcript_id")
        )
        for key, label in cls._CORE_FIELD_LABELS.items():
            value = core_fields.get(key)
            if key == "variant_descriptor" and not value and structural_substitute:
                continue
            if not value:
                missing.append(label)
        return missing

    def _can_continue_with_structural_fallback(
        self,
        missing_fields: List[str],
        structural_hint: Optional[Dict[str, Any]],
    ) -> bool:
        if not structural_hint:
            return False
        if not structural_hint.get("exon_range") or not structural_hint.get(
            "transcript_id"
        ):
            return False
        return set(missing_fields).issubset({"variant_hgvs"})

    def _should_mark_manual_review_on_skip(
        self,
        missing_fields: List[str],
        gene_symbol: Optional[str],
        disease_name: Optional[str],
        transcript_id: Optional[str],
    ) -> bool:
        if not gene_symbol or not disease_name or not transcript_id:
            return False
        return set(missing_fields).issubset({"variant_hgvs"})

    @staticmethod
    def _snapshot_context(
        document_id: str, **fields: Optional[str]
    ) -> Dict[str, Optional[str]]:
        context = {"document_id": document_id}
        for key, value in fields.items():
            if isinstance(value, str) and len(value) > 256:
                context[key] = f"{value[:253]}..."
            else:
                context[key] = value
        return context

    def _sanitize_extracted_fields(
        self, payload: Any, document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        log_id = document_id or "unknown"
        if payload is None:
            logger.warning(
                "extracted_fields missing for document {}, defaulting to empty dict",
                log_id,
            )
        else:
            logger.warning(
                "extracted_fields payload is not a dict for document {} (type={}), defaulting to empty dict",
                log_id,
                type(payload),
            )
        return {}

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _normalize_string(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        try:
            cleaned = str(value).strip()
            return cleaned or None
        except Exception:
            return None

    @staticmethod
    def _truncate_field(value: Any, max_length: int) -> Optional[str]:
        """Truncate string field to max_length to prevent database constraint violations.

        Args:
            value: The string value to truncate
            max_length: Maximum allowed length

        Returns:
            Truncated string or None if input is None
        """
        normalized = GraphSyncService._normalize_string(value)
        if normalized is None:
            return None
        if len(normalized) > max_length:
            logger.warning(
                "Field value exceeds {} characters (len={}), truncating: {} → {}",
                max_length,
                len(normalized),
                normalized[:50] + "..." if len(normalized) > 50 else normalized,
                normalized[: max_length - 3] + "..."
                if max_length > 3
                else normalized[:max_length],
            )
            return normalized[:max_length]
        return normalized

    def _collect_fallback_contexts(self, evidence_output: Dict[str, Any]) -> List[Any]:
        contexts: List[Any] = []
        for key in (
            "metadata",
            "document_metadata",
            "contextual_metadata",
            "fallback_fields",
            "manual_annotations",
        ):
            value = evidence_output.get(key)
            if isinstance(value, (dict, list)):
                contexts.append(value)
        contexts.append(evidence_output)
        return contexts

    @staticmethod
    def _extract_structural_variant_hint(payload: Any) -> Optional[Dict[str, Any]]:
        if isinstance(payload, dict):
            hint = payload.get("_structural_variant")
            if isinstance(hint, dict):
                return hint
        return None

    def _resolve_core_fields(
        self,
        evidence_output: Dict[str, Any],
        extracted_candidates: Dict[str, Dict[str, Any]],
    ) -> tuple[Dict[str, Optional[str]], Dict[str, Dict[str, Any]]]:
        fused: Dict[str, Optional[str]] = {}
        details: Dict[str, Dict[str, Any]] = {}
        fallback_payloads = self._collect_fallback_contexts(evidence_output)
        for field, meta in extracted_candidates.items():
            raw_value = meta.get("value")
            normalized = self._normalize_string(raw_value)
            if normalized:
                fused[field] = normalized
                details[field] = {
                    "source": meta.get("source"),
                    "status": "resolved",
                }
                continue

            reasons: List[str] = []
            if not meta.get("section_present", True):
                reasons.append("section_missing")
            if raw_value is None:
                reasons.append("not_provided")
            elif isinstance(raw_value, str) and not raw_value.strip():
                reasons.append("empty_string")
            elif raw_value not in (None, ""):
                reasons.append("invalid_type")

            alias_value = self._search_aliases(
                fallback_payloads, self._FIELD_ALIAS_MAP.get(field, [])
            )
            if alias_value:
                fused[field] = alias_value
                details[field] = {
                    "source": "fallback",
                    "status": "resolved",
                    "aliases_checked": self._FIELD_ALIAS_MAP.get(field, []),
                }
                continue

            fused[field] = None
            details[field] = {
                "source": None,
                "status": "missing",
                "reasons": reasons or ["not_found"],
                "aliases_checked": self._FIELD_ALIAS_MAP.get(field, []),
            }

        # Phase 3: cross-field inference for still-missing core fields
        self._infer_missing_fields(fused, details, evidence_output)

        if not fused.get("variant_hgvs_c"):
            structural_hint = self._resolve_structural_hint(
                evidence_output,
                transcript_id=fused.get("transcript_id"),
                disease_name=fused.get("disease_name"),
            )
            if structural_hint:
                payload = structural_hint.to_payload()
                builder = payload.get("synthetic_hgvs")
                if builder:
                    fused["variant_hgvs_c"] = builder
                    if not fused.get("variant_descriptor"):
                        fused["variant_descriptor"] = builder
                fused["_structural_variant"] = payload
                variant_details = details.get("variant_hgvs_c", {}).copy()
                variant_details.update(
                    {
                        "source": payload.get("source"),
                        "status": "synthetic_structural",
                        "structural_hint": payload,
                    }
                )
                details["variant_hgvs_c"] = variant_details

        return fused, details

    _RE_TRANSCRIPT_FROM_HGVS = re.compile(
        r"((?:NM_|NR_|XM_|XR_|ENST)\d+(?:\.\d+)?)\s*:",
        re.IGNORECASE,
    )
    _RE_GENE_SYMBOL = re.compile(r"\b([A-Z][A-Z0-9]{1,12})\b")

    def _infer_missing_fields(
        self,
        fused: Dict[str, Optional[str]],
        details: Dict[str, Dict[str, Any]],
        evidence_output: Dict[str, Any],
    ) -> None:
        if not fused.get("transcript_id") and fused.get("variant_hgvs_c"):
            inferred = self._extract_transcript_from_hgvs(fused["variant_hgvs_c"])
            if inferred:
                fused["transcript_id"] = inferred
                details["transcript_id"] = {
                    "source": "inferred_from_hgvs_c",
                    "status": "inferred",
                    "inferred_from": fused["variant_hgvs_c"],
                }
                logger.info(
                    "Inferred transcript_id={} from variant_hgvs_c={}",
                    inferred,
                    fused["variant_hgvs_c"],
                )

        if not fused.get("disease_name"):
            disease_fields = evidence_output.get("extracted_fields", {})
            for section_key in ("disease_chpo", "disease_icd10"):
                section = disease_fields.get(section_key, {})
                if isinstance(section, dict):
                    for candidate_key in (
                        "disease_name",
                        "name",
                        "label",
                        "description",
                        "condition",
                        "diagnosis",
                        "disorder",
                    ):
                        val = self._normalize_string(section.get(candidate_key))
                        if val:
                            fused["disease_name"] = val
                            details["disease_name"] = {
                                "source": f"inferred_from_{section_key}.{candidate_key}",
                                "status": "inferred",
                            }
                            logger.info(
                                "Inferred disease_name={} from {}.{}",
                                val,
                                section_key,
                                candidate_key,
                            )
                            break
                if fused.get("disease_name"):
                    break

        if not fused.get("gene_symbol"):
            inferred_gene = self._extract_gene_from_context(evidence_output)
            if inferred_gene:
                fused["gene_symbol"] = inferred_gene
                details["gene_symbol"] = {
                    "source": "inferred_from_context",
                    "status": "inferred",
                }
                logger.info("Inferred gene_symbol={} from context", inferred_gene)

    @staticmethod
    def _extract_transcript_from_hgvs(hgvs_str: Optional[str]) -> Optional[str]:
        if not hgvs_str:
            return None
        match = GraphSyncService._RE_TRANSCRIPT_FROM_HGVS.search(hgvs_str)
        return match.group(1) if match else None

    def _extract_gene_from_context(
        self,
        evidence_output: Dict[str, Any],
    ) -> Optional[str]:
        extracted = evidence_output.get("extracted_fields", {})
        gene_section = extracted.get("gene", {})
        if isinstance(gene_section, dict):
            for key in ("name", "label", "gene_name", "hugo_symbol"):
                val = self._normalize_string(gene_section.get(key))
                if val and self._RE_GENE_SYMBOL.fullmatch(val):
                    return val

        variant_section = extracted.get("variant", {})
        if isinstance(variant_section, dict):
            quote = variant_section.get("evidence_quote", "")
            if isinstance(quote, str):
                match = self._RE_GENE_SYMBOL.search(quote)
                if match:
                    candidate = match.group(1)
                    if len(candidate) >= 2 and candidate not in (
                        "THE",
                        "AND",
                        "FOR",
                        "NOT",
                        "DNA",
                        "RNA",
                        "PCR",
                        "SNP",
                        "VUS",
                        "HET",
                        "HOM",
                    ):
                        return candidate
        return None

    def _resolve_structural_hint(
        self,
        evidence_output: Dict[str, Any],
        transcript_id: Optional[str],
        disease_name: Optional[str],
    ) -> Optional[StructuralVariantParseResult]:
        try:
            return parse_structural_variant(
                evidence_output,
                transcript_id=transcript_id,
                disease_name=disease_name,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Structural variant parser failed: {}", exc)
            return None

    def _search_aliases(self, payloads: List[Any], aliases: List[str]) -> Optional[str]:
        if not aliases:
            return None
        for payload in payloads:
            value = self._scan_payload(payload, aliases)
            if value:
                return value
        return None

    def _scan_payload(self, payload: Any, aliases: List[str]) -> Optional[str]:
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key in aliases:
                    if isinstance(value, str):
                        normalized = self._normalize_string(value)
                        if normalized:
                            return normalized
                    elif isinstance(value, (int, float, bool)):
                        normalized = self._normalize_string(str(value))
                        if normalized:
                            return normalized
                if isinstance(value, (dict, list)):
                    nested = self._scan_payload(value, aliases)
                    if nested:
                        return nested
        elif isinstance(payload, list):
            for item in payload:
                nested = self._scan_payload(item, aliases)
                if nested:
                    return nested
        return None

    def _determine_validity_status(
        self,
        overall_conf: float,
        extracted_fields: Dict[str, Any],
    ) -> tuple[str, str]:
        if overall_conf >= self._validity_threshold:
            return "true", "meets_threshold"
        if overall_conf <= 0 and not extracted_fields:
            return "missing", "no_structured_fields"
        if overall_conf <= 0:
            return "false", "zero_confidence"
        if overall_conf >= self._review_floor:
            return "review", "below_threshold"
        return "review", "low_confidence"

    def _archive_failure_case(
        self,
        document_id: str,
        reason: str,
        missing_fields: List[str],
        resolution_details: Dict[str, Dict[str, Any]],
    ) -> None:
        try:
            payload = {
                "document_id": document_id,
                "reason": reason,
                "missing_fields": missing_fields,
                "resolution_details": resolution_details,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            self._failure_archive_path.parent.mkdir(parents=True, exist_ok=True)
            with self._failure_archive_path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.warning(
                "Failed to archive failure case for {}: {}", document_id, exc
            )

    def _track_missing_fields(self, missing_fields: List[str]) -> None:
        if not missing_fields:
            return
        for field in missing_fields:
            self._MISSING_FIELD_COUNTER[field] += 1
            count = self._MISSING_FIELD_COUNTER[field]
            threshold = max(1, self._missing_field_alert_threshold)
            if threshold and count % threshold == 0:
                logger.warning(
                    "Core field {} missing {} times; consider targeted extraction tuning",
                    field,
                    count,
                )

    def _mark_pending_manual_review(
        self,
        document_id: UUID,
        detail: Dict[str, Any],
        resolution_details: Dict[str, Dict[str, Any]],
    ) -> None:
        try:
            self._pg.update_document(document_id, status="pending_manual_review")
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.warning(
                "Failed to mark document {} pending review: {}", document_id, exc
            )

        log_payload = {
            "category": "non_standard_variant",
            "detail": detail,
            "field_resolution": resolution_details,
        }
        task_record = None
        try:
            task_record = self._pg.create_task(
                document_id=document_id,
                task_type="manual_review",
                status="pending_manual_review",
                result=log_payload,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Failed to enqueue manual review task for {}: {}", document_id, exc
            )

        append_log = getattr(self._pg, "append_task_log", None)
        if callable(append_log):
            try:
                append_log(
                    document_id=document_id,
                    status="pending_manual_review",
                    category="manual_review",
                    payload=log_payload,
                    missing_fields_detail=detail,
                    task_id=getattr(task_record, "task_id", None),
                )
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "Failed to append manual review log for {}: {}", document_id, exc
                )

    def _log_document_summary(
        self, document_id: str, success: bool, summary: Dict[str, Any]
    ) -> None:
        log = logger.info if success else logger.warning
        log(
            "Document {} sync summary status={} gene={} variant_c={} variant_p={} disease={} transcript={} confidence={} validity={}",
            document_id,
            "success" if success else "failed",
            summary.get("gene_symbol") or "-",
            summary.get("variant_hgvs_c") or "-",
            summary.get("variant_hgvs_p") or "-",
            summary.get("disease_name") or "-",
            summary.get("transcript_id") or "-",
            summary.get("confidence"),
            summary.get("validity_status"),
        )

    # ==================== Neo4j 写入 ====================

    def _sync_to_neo4j(
        self,
        document_id: str,
        evidence_id: str,
        gene_symbol: str,
        variant_hgvs_c: str,
        variant_hgvs_p: str,
        variation_id: Optional[int],
        transcript_id: str,
        disease_name: str,
        icd10: str,
        phenotype_desc: str,
        species: str,
        strength: str,
        classification: str,
        overall_conf: float,
        structural_hint: Optional[Dict[str, Any]] = None,
    ) -> None:
        """将实体和关系写入 Neo4j"""
        logger.info(
            "Neo4j syncing evidence {} (doc {}) gene={} variant={} classification={} strength={}",
            evidence_id,
            document_id,
            gene_symbol or "-",
            variant_hgvs_c or "-",
            classification or "-",
            strength or "-",
        )
        logger.debug("Ensuring document node {} exists", document_id)
        neo = self._neo4j
        variant_structural_key = None
        variant_exon_range = None
        variant_structural_type = None
        variant_transcript = transcript_id
        if isinstance(structural_hint, dict):
            variant_structural_key = structural_hint.get("structural_key")
            variant_exon_range = structural_hint.get("exon_range")
            variant_structural_type = structural_hint.get("structural_type")
            variant_transcript = (
                structural_hint.get("transcript_id") or variant_transcript
            )

        neo.upsert_document(str(document_id))

        if gene_symbol:
            logger.debug("Upserting gene node {}", gene_symbol)
            neo.upsert_gene(gene_symbol)

        variant_node_present = bool(
            variant_hgvs_c
            or variant_structural_key
            or (variant_transcript and variant_exon_range)
        )
        if variant_node_present:
            logger.debug(
                "Upserting variant node {} (hgvs_p={}) variation_id={} structural_key={} exon_range={}",
                variant_hgvs_c or variant_structural_key or "-",
                variant_hgvs_p or "-",
                variation_id or "-",
                variant_structural_key or "-",
                variant_exon_range or "-",
            )
            neo.upsert_variant(
                variant_hgvs_c or None,
                variation_id=variation_id,
                hgvs_p=variant_hgvs_p or None,
                structural_key=variant_structural_key,
                transcript_id=variant_transcript or None,
                exon_range=variant_exon_range,
                structural_type=variant_structural_type,
            )
            if gene_symbol:
                logger.debug(
                    "Linking gene {} to variant {} (variation_id={})",
                    gene_symbol,
                    variant_hgvs_c or variant_structural_key or "-",
                    variation_id or "-",
                )
                neo.link_gene_variant(
                    gene_symbol,
                    variant_hgvs_c or None,
                    variation_id=variation_id,
                    structural_key=variant_structural_key,
                    transcript_id=variant_transcript or None,
                    exon_range=variant_exon_range,
                )
            entity_key = None
            entity_value = None
            if variant_hgvs_c:
                entity_key = "hgvs_c"
                entity_value = variant_hgvs_c
            elif variant_structural_key:
                entity_key = "structural_key"
                entity_value = variant_structural_key
            if entity_key and entity_value:
                logger.debug(
                    "Linking document {} to variant {} via {}",
                    document_id,
                    entity_value,
                    entity_key,
                )
                neo.link_document_entity(
                    str(document_id), "Variant", entity_key, entity_value
                )

        if transcript_id and gene_symbol:
            logger.debug(
                "Upserting transcript {} and linking to gene {}",
                transcript_id,
                gene_symbol,
            )
            neo.upsert_transcript(transcript_id)
            neo.link_gene_transcript(gene_symbol, transcript_id)

        if disease_name:
            logger.debug("Upserting disease {} (icd10={})", disease_name, icd10 or "-")
            neo.upsert_disease(disease_name, icd10_code=icd10 or None)
            if gene_symbol:
                logger.debug(
                    "Linking disease {} with gene {}", disease_name, gene_symbol
                )
                neo.link_disease_gene(disease_name, gene_symbol)
            neo.link_document_entity(str(document_id), "Disease", "name", disease_name)

        if phenotype_desc:
            logger.debug("Upserting phenotype {}", phenotype_desc)
            neo.upsert_phenotype(phenotype_desc)
            if variant_node_present:
                logger.debug(
                    "Linking variant {} (variation_id={}) with phenotype {}",
                    variant_hgvs_c or variant_structural_key or "-",
                    variation_id or "-",
                    phenotype_desc,
                )
                neo.link_variant_phenotype(
                    variant_hgvs_c or None,
                    phenotype_desc,
                    variation_id=variation_id,
                    structural_key=variant_structural_key,
                    transcript_id=variant_transcript or None,
                    exon_range=variant_exon_range,
                )
            neo.link_document_entity(
                str(document_id), "Phenotype", "description", phenotype_desc
            )

        if species:
            logger.debug("Upserting species {}", species)
            neo.upsert_species(species)

        logger.debug(
            "Upserting evidence node {} with strength={}, classification={}, confidence={}",
            evidence_id,
            strength or "-",
            classification or "-",
            overall_conf,
        )
        neo.upsert_evidence(
            evidence_id,
            evidence_strength=strength,
            classification=classification,
            confidence=overall_conf,
        )
        if variant_node_present:
            logger.debug(
                "Linking variant {} (variation_id={}) to evidence {}",
                variant_hgvs_c or variant_structural_key or "-",
                variation_id or "-",
                evidence_id,
            )
            neo.link_variant_evidence(
                variant_hgvs_c or None,
                evidence_id,
                variation_id=variation_id,
                structural_key=variant_structural_key,
                transcript_id=variant_transcript or None,
                exon_range=variant_exon_range,
            )
        logger.debug("Linking evidence {} to document {}", evidence_id, document_id)
        neo.link_evidence_document(evidence_id, str(document_id))

        if gene_symbol:
            logger.debug("Linking document {} to gene {}", document_id, gene_symbol)
            neo.link_document_entity(str(document_id), "Gene", "symbol", gene_symbol)

        logger.debug("Neo4j entity writes completed for evidence {}", evidence_id)

    # ==================== 批量同步 ====================

    def sync_batch(
        self,
        document_id: str,
        evidence_outputs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """批量同步多条证据（同一文档的多条提取结果）"""
        logger.info(
            "Batch syncing {} evidence item(s) for document {}",
            len(evidence_outputs),
            document_id,
        )
        results = []
        for idx, ev in enumerate(evidence_outputs):
            logger.debug("Batch sync started for document {} item {}", document_id, idx)
            try:
                r = self.sync_evidence(document_id, ev)
                logger.debug(
                    "Batch sync completed for document {} item {}: {}",
                    document_id,
                    idx,
                    r,
                )
                results.append(r)
            except Exception as e:
                logger.error("Batch sync failed at index {}: {}", idx, e)
                results.append(
                    {"pg_evidence_id": None, "neo4j_synced": False, "error": str(e)}
                )
        return results

    # ==================== 重新同步 ====================

    def resync_document(self, document_id: str) -> Dict[str, Any]:
        """
        从 PostgreSQL 重新同步某文档的所有证据到 Neo4j。
        用于修复 Neo4j 数据不一致。
        """
        logger.info("Resyncing document {}", document_id)
        records = self._pg.get_evidence_for_document(document_id)
        synced = 0
        failed = 0
        for rec in records:
            logger.debug(
                "Resyncing evidence {} for document {} (gene={}, variant={}, classification={})",
                rec.evidence_id,
                document_id,
                getattr(rec, "gene_symbol", "") or "-",
                getattr(rec, "variant_hgvs_c", "") or "-",
                getattr(rec, "evidence_classification", "") or "-",
            )
            try:
                structural_hint = self._extract_structural_variant_hint(
                    getattr(rec, "extracted_fields", None)
                )
                self._sync_to_neo4j(
                    document_id=document_id,
                    evidence_id=str(rec.evidence_id),
                    gene_symbol=getattr(rec, "gene_symbol", "") or "",
                    variant_hgvs_c=getattr(rec, "variant_hgvs_c", "") or "",
                    variant_hgvs_p=getattr(rec, "variant_hgvs_p", "") or "",
                    variation_id=getattr(rec, "clinvar_variation_id", None),
                    transcript_id=getattr(rec, "transcript_id", "") or "",
                    disease_name=getattr(rec, "disease_name", "") or "",
                    icd10=getattr(rec, "icd10_code", "") or "",
                    phenotype_desc=getattr(rec, "phenotype", "") or "",
                    species=getattr(rec, "species", "") or "",
                    strength=getattr(rec, "evidence_strength", "") or "",
                    classification=getattr(rec, "evidence_classification", "") or "",
                    overall_conf=getattr(rec, "overall_confidence", 0.0) or 0.0,
                    structural_hint=structural_hint,
                )
                synced += 1
            except Exception as e:
                logger.error("Resync failed for evidence {}: {}", rec.evidence_id, e)
                failed += 1

        logger.info(
            "Resync document {}: {}/{} ok, {} failed",
            document_id,
            synced,
            len(records),
            failed,
        )
        return {"total": len(records), "synced": synced, "failed": failed}


# ==================== 工厂 ====================

_sync_service: Optional[GraphSyncService] = None


def get_graph_sync_service() -> GraphSyncService:
    global _sync_service
    if _sync_service is None:
        _sync_service = GraphSyncService()
    return _sync_service
