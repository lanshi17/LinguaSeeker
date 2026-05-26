"""Terminology import parsers for Phase 3 reference data."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Iterator

from src.core.standardize_entities_and_align_knowledge.contracts import EntityType
from src.core.standardize_entities_and_align_knowledge.normalizers import (
    normalize_gene_symbol,
    normalize_lookup_text,
    normalize_variant_text,
)


ZERO_STAR_REVIEW_STATUSES = {
    "",
    "-",
    "no assertion criteria provided",
    "no classification provided",
    "no classification for the single variant",
    "no classifications from unflagged records",
}

CLINVAR_CORE_FIELDS = (
    "VariationID",
    "Name",
    "GeneSymbol",
    "ClinicalSignificance",
    "ReviewStatus",
    "RS# (dbSNP)",
    "PhenotypeIDS",
)


@dataclass(frozen=True)
class ImportEntry:
    """Normalized terminology entity staged for repository upsert."""

    entity_type: EntityType
    source_db: str
    external_id: str
    display_name: str
    normalized_name: str
    aliases: tuple[str, ...]
    raw_payload: dict[str, object]  # Heterogeneous source-specific import payload.
    version: str


@dataclass(frozen=True)
class ImportAlias:
    """Queryable alias staged for repository upsert."""

    external_id: str
    entity_type: EntityType
    source_db: str
    alias_text: str
    normalized_alias: str
    alias_type: str


@dataclass(frozen=True)
class ImportRelationship:
    """Structured terminology relationship staged for repository upsert."""

    subject_external_id: str
    object_external_id: str | None
    relationship_type: str
    source_db: str
    evidence_level: str | None
    raw_payload: dict[str, object]  # Heterogeneous relationship metadata by source.


@dataclass(frozen=True)
class ImportBatch:
    """Bundle of parsed terminology entities, aliases, and relationships."""

    entries: tuple[ImportEntry, ...] = ()
    aliases: tuple[ImportAlias, ...] = ()
    relationships: tuple[ImportRelationship, ...] = ()


def is_importable_clinvar_review_status(review_status: str) -> bool:
    """Return whether a ClinVar row should be kept for MVP import."""
    return normalize_lookup_text(review_status) not in ZERO_STAR_REVIEW_STATUSES


def parse_hgnc_rows(path: Path, version: str) -> ImportBatch:
    """Parse HGNC export rows into import entities and aliases."""
    entries: list[ImportEntry] = []
    aliases: list[ImportAlias] = []

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            hgnc_id = (row.get("HGNC ID") or "").strip()
            approved_symbol = (row.get("Approved symbol") or "").strip()
            approved_name = (row.get("Approved name") or "").strip()

            if not hgnc_id or not approved_symbol:
                continue

            external_id = f"HGNC:{hgnc_id}"
            alias_values = _collect_alias_values(
                approved_symbol,
                row.get("Alias symbols"),
                row.get("Previous symbols"),
            )
            entry = ImportEntry(
                entity_type=EntityType.GENE,
                source_db="HGNC",
                external_id=external_id,
                display_name=approved_symbol,
                normalized_name=normalize_gene_symbol(approved_symbol),
                aliases=tuple(alias_values),
                raw_payload={
                    "approved_name": approved_name,
                    "hgnc_id": hgnc_id,
                },
                version=version,
            )
            entries.append(entry)

            aliases.append(
                ImportAlias(
                    external_id=external_id,
                    entity_type=EntityType.GENE,
                    source_db="HGNC",
                    alias_text=approved_symbol,
                    normalized_alias=normalize_gene_symbol(approved_symbol),
                    alias_type="primary",
                ),
            )

            for alias_text in _split_comma_values(row.get("Alias symbols")):
                aliases.append(
                    ImportAlias(
                        external_id=external_id,
                        entity_type=EntityType.GENE,
                        source_db="HGNC",
                        alias_text=alias_text,
                        normalized_alias=normalize_gene_symbol(alias_text),
                        alias_type="alias",
                    ),
                )

            for alias_text in _split_comma_values(row.get("Previous symbols")):
                aliases.append(
                    ImportAlias(
                        external_id=external_id,
                        entity_type=EntityType.GENE,
                        source_db="HGNC",
                        alias_text=alias_text,
                        normalized_alias=normalize_gene_symbol(alias_text),
                        alias_type="previous_symbol",
                    ),
                )

    return ImportBatch(entries=tuple(entries), aliases=tuple(aliases))


def parse_omim_rows(root: Path, version: str) -> ImportBatch:
    """Parse OMIM title rows into disease entries and aliases."""
    path = root / "mimTitles.txt"
    if not path.exists():
        return ImportBatch()

    entries: list[ImportEntry] = []
    aliases: list[ImportAlias] = []

    for row in _iter_tsv_rows(path, header_prefix="Prefix\tMIM Number\tPreferred Title; symbol"):
        mim_number = (row.get("MIM Number") or "").strip()
        title = (row.get("Preferred Title; symbol") or "").strip()
        if not mim_number or not title:
            continue

        external_id = f"OMIM:{mim_number}"
        entries.append(
            ImportEntry(
                entity_type=EntityType.DISEASE,
                source_db="OMIM",
                external_id=external_id,
                display_name=title,
                normalized_name=normalize_lookup_text(title),
                aliases=(title,),
                raw_payload={"mim_number": mim_number},
                version=version,
            ),
        )
        aliases.append(
            ImportAlias(
                external_id=external_id,
                entity_type=EntityType.DISEASE,
                source_db="OMIM",
                alias_text=title,
                normalized_alias=normalize_lookup_text(title),
                alias_type="name",
            ),
        )

    return ImportBatch(entries=tuple(entries), aliases=tuple(aliases))


def parse_hpo_rows(root: Path, version: str) -> ImportBatch:
    """Parse HPO phenotype rows from JSON or OBO exports."""
    json_path = root / "hp.json"
    if json_path.exists():
        return _parse_hpo_json_rows(json_path, version)

    obo_path = root / "hp.obo"
    if obo_path.exists():
        return _parse_hpo_obo_rows(obo_path, version)

    return ImportBatch()


def parse_clingen_rows(root: Path, version: str) -> ImportBatch:
    """Parse ClinGen summary and dosage CSV exports."""
    entries: list[ImportEntry] = []
    aliases: list[ImportAlias] = []
    relationships: list[ImportRelationship] = []
    seen_entry_ids: set[str] = set()

    summary_path = root / "Clingen-Gene-Disease-Summary.csv"
    if summary_path.exists():
        with summary_path.open(encoding="utf-8", newline="") as handle:
            reader = _csv_dict_reader_from_header(
                handle,
                header_prefixes=(
                    "GENE SYMBOL,GENE ID (HGNC),DISEASE LABEL,DISEASE ID (MONDO)",
                    "GENE SYMBOL,DISEASE LABEL,DISEASE ID,CLASSIFICATION",
                ),
            )
            for row in reader:
                disease_id = (row.get("DISEASE ID") or row.get("DISEASE ID (MONDO)") or "").strip()
                disease_label = (row.get("DISEASE LABEL") or "").strip()
                gene_symbol = (row.get("GENE SYMBOL") or "").strip()
                classification = (row.get("CLASSIFICATION") or "").strip()

                if disease_id.startswith("MONDO:") and disease_id not in seen_entry_ids and disease_label:
                    entries.append(
                        ImportEntry(
                            entity_type=EntityType.DISEASE,
                            source_db="MONDO",
                            external_id=disease_id,
                            display_name=disease_label,
                            normalized_name=normalize_lookup_text(disease_label),
                            aliases=(disease_label,),
                            raw_payload={"source_limited": True, "source_db": "ClinGen"},
                            version=version,
                        ),
                    )
                    aliases.append(
                        ImportAlias(
                            external_id=disease_id,
                            entity_type=EntityType.DISEASE,
                            source_db="MONDO",
                            alias_text=disease_label,
                            normalized_alias=normalize_lookup_text(disease_label),
                            alias_type="name",
                        ),
                    )
                    seen_entry_ids.add(disease_id)

                if gene_symbol and disease_id:
                    relationships.append(
                        ImportRelationship(
                            subject_external_id=gene_symbol,
                            object_external_id=disease_id,
                            relationship_type="gene_associated_with_disease",
                            source_db="ClinGen",
                            evidence_level=normalize_lookup_text(classification) or None,
                            raw_payload=dict(row),
                        ),
                    )

    dosage_path = root / "Clingen-Dosage-Sensitivity.csv"
    if dosage_path.exists():
        with dosage_path.open(encoding="utf-8", newline="") as handle:
            reader = _csv_dict_reader_from_header(
                handle,
                header_prefixes=(
                    "GENE SYMBOL,HGNC ID,HAPLOINSUFFICIENCY,TRIPLOSENSITIVITY",
                    "Gene Symbol,Dosage Sensitivity Map,Score",
                ),
            )
            for row in reader:
                gene_symbol = (row.get("Gene Symbol") or row.get("GENE SYMBOL") or "").strip()
                score = (
                    row.get("Score")
                    or row.get("Haploinsufficiency Score")
                    or row.get("HAPLOINSUFFICIENCY")
                    or ""
                ).strip()
                if not gene_symbol:
                    continue
                relationships.append(
                    ImportRelationship(
                        subject_external_id=gene_symbol,
                        object_external_id=None,
                        relationship_type="gene_has_dosage_sensitivity",
                        source_db="ClinGen",
                        evidence_level=score or None,
                        raw_payload=dict(row),
                    ),
                )

    return ImportBatch(
        entries=tuple(entries),
        aliases=tuple(aliases),
        relationships=tuple(relationships),
    )


def parse_clinvar_rows(path: Path, version: str) -> ImportBatch:
    """Parse ClinVar variant summary rows into variant entries and review relationships."""
    batches = list(iter_clinvar_batches(path=path, version=version, chunk_size=50_000))
    entries = tuple(entry for batch in batches for entry in batch.entries)
    aliases = tuple(alias for batch in batches for alias in batch.aliases)
    relationships = tuple(relationship for batch in batches for relationship in batch.relationships)
    return ImportBatch(entries=entries, aliases=aliases, relationships=relationships)


def build_clinvar_core_tsv(source_path: Path, target_path: Path) -> int:
    """Write a reduced ClinVar TSV with only fields needed for Phase 3 alignment."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with source_path.open(encoding="utf-8", newline="") as source_handle, target_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as target_handle:
        header_line = _find_header_line(source_handle, comment_prefix="#")
        if header_line is None:
            return 0
        reader = csv.DictReader(chain([header_line], source_handle), delimiter="\t")
        writer = csv.writer(target_handle, delimiter="\t", lineterminator="\n")
        writer.writerow(CLINVAR_CORE_FIELDS)
        for row in reader:
            writer.writerow([str(row.get(field, "") or "").strip() for field in CLINVAR_CORE_FIELDS])
            rows_written += 1
    return rows_written


def iter_clinvar_batches(path: Path, version: str, chunk_size: int) -> Iterator[ImportBatch]:
    """Yield ClinVar import batches in bounded chunks for streaming import."""
    entries: list[ImportEntry] = []
    aliases: list[ImportAlias] = []
    relationships: list[ImportRelationship] = []

    def flush_batch() -> ImportBatch | None:
        if not entries and not aliases and not relationships:
            return None
        batch = ImportBatch(
            entries=tuple(entries),
            aliases=tuple(aliases),
            relationships=tuple(relationships),
        )
        entries.clear()
        aliases.clear()
        relationships.clear()
        return batch

    for row in _iter_tsv_rows(path):
        review_status = (row.get("ReviewStatus") or "").strip()
        if not is_importable_clinvar_review_status(review_status):
            continue

        variation_id = (row.get("VariationID") or "").strip()
        name = (row.get("Name") or "").strip()
        if not variation_id or not name:
            continue

        external_id = f"ClinVarVariation:{variation_id}"
        alias_values = [name]
        rs_value = _normalize_rsid(row.get("RS# (dbSNP)"))
        if rs_value:
            alias_values.append(rs_value)

        entries.append(
            ImportEntry(
                entity_type=EntityType.VARIANT,
                source_db="ClinVar",
                external_id=external_id,
                display_name=name,
                normalized_name=normalize_variant_text(name),
                aliases=tuple(alias_values),
                raw_payload={
                    "review_status": review_status,
                    "review_stars": _clinvar_review_stars(review_status),
                    "clinical_significance": (row.get("ClinicalSignificance") or "").strip(),
                    "gene_symbol": (row.get("GeneSymbol") or "").strip(),
                    "variation_id": variation_id,
                },
                version=version,
            ),
        )
        aliases.append(
            ImportAlias(
                external_id=external_id,
                entity_type=EntityType.VARIANT,
                source_db="ClinVar",
                alias_text=name,
                normalized_alias=normalize_variant_text(name),
                alias_type="name",
            ),
        )
        if rs_value:
            aliases.append(
                ImportAlias(
                    external_id=external_id,
                    entity_type=EntityType.VARIANT,
                    source_db="ClinVar",
                    alias_text=rs_value,
                    normalized_alias=normalize_variant_text(rs_value),
                    alias_type="rsid",
                ),
            )

        relationships.append(
            ImportRelationship(
                subject_external_id=external_id,
                object_external_id=None,
                relationship_type="variant_has_clinical_significance",
                source_db="ClinVar",
                evidence_level=_clinvar_review_stars(review_status),
                raw_payload={
                    "clinical_significance": (row.get("ClinicalSignificance") or "").strip(),
                    "review_status": review_status,
                    "review_stars": _clinvar_review_stars(review_status),
                    "variation_id": variation_id,
                    "phenotype_ids": (row.get("PhenotypeIDS") or "").strip(),
                    "phenotype_list": (row.get("PhenotypeList") or "").strip(),
                },
            ),
        )

        if len(entries) >= chunk_size:
            batch = flush_batch()
            if batch is not None:
                yield batch

    final_batch = flush_batch()
    if final_batch is not None:
        yield final_batch


def _parse_clinvar_rows_legacy(path: Path, version: str) -> ImportBatch:
    """Legacy monolithic ClinVar parser retained for reference-compatible behavior."""
    entries: list[ImportEntry] = []
    aliases: list[ImportAlias] = []
    relationships: list[ImportRelationship] = []

    for row in _iter_tsv_rows(path):
        review_status = (row.get("ReviewStatus") or "").strip()
        if not is_importable_clinvar_review_status(review_status):
            continue

        variation_id = (row.get("VariationID") or "").strip()
        name = (row.get("Name") or "").strip()
        if not variation_id or not name:
            continue

        external_id = f"ClinVarVariation:{variation_id}"
        alias_values = [name]
        rs_value = _normalize_rsid(row.get("RS# (dbSNP)"))
        if rs_value:
            alias_values.append(rs_value)

        entries.append(
            ImportEntry(
                entity_type=EntityType.VARIANT,
                source_db="ClinVar",
                external_id=external_id,
                display_name=name,
                normalized_name=normalize_variant_text(name),
                aliases=tuple(alias_values),
                raw_payload={
                    "review_status": review_status,
                    "review_stars": _clinvar_review_stars(review_status),
                    "clinical_significance": (row.get("ClinicalSignificance") or "").strip(),
                    "gene_symbol": (row.get("GeneSymbol") or "").strip(),
                    "variation_id": variation_id,
                },
                version=version,
            ),
        )
        aliases.append(
            ImportAlias(
                external_id=external_id,
                entity_type=EntityType.VARIANT,
                source_db="ClinVar",
                alias_text=name,
                normalized_alias=normalize_variant_text(name),
                alias_type="name",
            ),
        )
        if rs_value:
            aliases.append(
                ImportAlias(
                    external_id=external_id,
                    entity_type=EntityType.VARIANT,
                    source_db="ClinVar",
                    alias_text=rs_value,
                    normalized_alias=normalize_variant_text(rs_value),
                    alias_type="rsid",
                ),
            )

        relationships.append(
            ImportRelationship(
                subject_external_id=external_id,
                object_external_id=None,
                relationship_type="variant_has_clinical_significance",
                source_db="ClinVar",
                evidence_level=_clinvar_review_stars(review_status),
                raw_payload={
                    "clinical_significance": (row.get("ClinicalSignificance") or "").strip(),
                    "review_status": review_status,
                    "review_stars": _clinvar_review_stars(review_status),
                    "variation_id": variation_id,
                    "phenotype_ids": (row.get("PhenotypeIDS") or "").strip(),
                    "phenotype_list": (row.get("PhenotypeList") or "").strip(),
                },
            ),
        )

    return ImportBatch(entries=tuple(entries), aliases=tuple(aliases), relationships=tuple(relationships))


def _collect_alias_values(primary_symbol: str, *fields: str | None) -> list[str]:
    """Collect stable alias payload values preserving first-seen order."""
    values: list[str] = []
    seen: set[str] = set()

    for alias_text in [primary_symbol, *[value for field in fields for value in _split_comma_values(field)]]:
        if alias_text not in seen:
            values.append(alias_text)
            seen.add(alias_text)
    return values


def _split_comma_values(value: str | None) -> list[str]:
    """Split comma-delimited source fields into trimmed, non-empty values."""
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _iter_tsv_rows(path: Path, header_prefix: str | None = None) -> Iterator[dict[str, str]]:
    """Yield TSV rows while stripping a leading hash from the header if present."""
    with path.open(encoding="utf-8", newline="") as handle:
        header_line = _find_header_line(handle, header_prefix=header_prefix, comment_prefix="#")
        if header_line is None:
            return
        reader = csv.DictReader(chain([header_line], handle), delimiter="\t")
        for row in reader:
            yield dict(row)


def _csv_dict_reader_from_header(handle, *, header_prefixes: tuple[str, ...]) -> csv.DictReader:
    """Build a CSV DictReader after skipping preamble lines before the actual header."""
    header_line = _find_csv_header_line(handle, header_prefixes=header_prefixes)
    if header_line is None:
        return csv.DictReader([])
    return csv.DictReader(chain([header_line], handle))


def _find_header_line(
    handle,
    *,
    header_prefix: str | None = None,
    header_prefixes: tuple[str, ...] = (),
    comment_prefix: str | None = None,
) -> str | None:
    """Return the first line that matches the expected header prefix."""
    expected_prefixes = header_prefixes or ((header_prefix,) if header_prefix is not None else ())
    for line in handle:
        candidate = line[1:] if comment_prefix and line.startswith(comment_prefix) else line
        stripped = candidate.lstrip("\ufeff").strip().strip('"')
        if not stripped:
            continue
        if not expected_prefixes or any(stripped.startswith(prefix) for prefix in expected_prefixes):
            return candidate
    return None


def _find_csv_header_line(handle, *, header_prefixes: tuple[str, ...]) -> str | None:
    """Return the first CSV line whose parsed cells match any expected header prefix."""
    for line in handle:
        stripped = line.lstrip("\ufeff").strip()
        if not stripped:
            continue
        cells = next(csv.reader([line]))
        normalized = ",".join(cell.strip() for cell in cells)
        if any(normalized.startswith(prefix) for prefix in header_prefixes):
            return line
    return None


def _parse_hpo_json_rows(path: Path, version: str) -> ImportBatch:
    """Parse HPO JSON graph nodes into phenotype entries."""
    data = json.loads(path.read_text(encoding="utf-8"))
    graphs = data.get("graphs", [])
    entries: list[ImportEntry] = []
    aliases: list[ImportAlias] = []

    for graph in graphs:
        for node in graph.get("nodes", []):
            node_id = str(node.get("id", ""))
            label = str(node.get("lbl", "")).strip()
            if "HP_" not in node_id or not label:
                continue
            external_id = node_id.rsplit("/", maxsplit=1)[-1].replace("_", ":")
            entries.append(
                ImportEntry(
                    entity_type=EntityType.PHENOTYPE,
                    source_db="HPO",
                    external_id=external_id,
                    display_name=label,
                    normalized_name=normalize_lookup_text(label),
                    aliases=(label,),
                    raw_payload={"source": "hp.json"},
                    version=version,
                ),
            )
            aliases.append(
                ImportAlias(
                    external_id=external_id,
                    entity_type=EntityType.PHENOTYPE,
                    source_db="HPO",
                    alias_text=label,
                    normalized_alias=normalize_lookup_text(label),
                    alias_type="name",
                ),
            )

    return ImportBatch(entries=tuple(entries), aliases=tuple(aliases))


def _parse_hpo_obo_rows(path: Path, version: str) -> ImportBatch:
    """Parse a minimal subset of HPO OBO terms into phenotype entries."""
    entries: list[ImportEntry] = []
    aliases: list[ImportAlias] = []
    current_id = ""
    current_name = ""
    current_is_obsolete = False
    in_term_stanza = False

    def flush_current() -> None:
        nonlocal current_id, current_name, current_is_obsolete, in_term_stanza
        if not current_id or not current_name or current_is_obsolete:
            current_id = ""
            current_name = ""
            current_is_obsolete = False
            in_term_stanza = False
            return
        entries.append(
            ImportEntry(
                entity_type=EntityType.PHENOTYPE,
                source_db="HPO",
                external_id=current_id,
                display_name=current_name,
                normalized_name=normalize_lookup_text(current_name),
                aliases=(current_name,),
                raw_payload={"source": "hp.obo"},
                version=version,
            ),
        )
        aliases.append(
            ImportAlias(
                external_id=current_id,
                entity_type=EntityType.PHENOTYPE,
                source_db="HPO",
                alias_text=current_name,
                normalized_alias=normalize_lookup_text(current_name),
                alias_type="name",
            ),
        )
        current_id = ""
        current_name = ""
        current_is_obsolete = False
        in_term_stanza = False

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            flush_current()
            in_term_stanza = line == "[Term]"
            continue
        if not in_term_stanza:
            continue
        if line.startswith("id: HP:"):
            current_id = line.removeprefix("id: ").strip()
        elif line.startswith("name: "):
            current_name = line.removeprefix("name: ").strip()
        elif line == "is_obsolete: true":
            current_is_obsolete = True
    flush_current()

    return ImportBatch(entries=tuple(entries), aliases=tuple(aliases))


def _normalize_rsid(value: str | None) -> str | None:
    """Normalize a ClinVar dbSNP field into an rsID alias when present."""
    raw_value = (value or "").strip()
    if not raw_value or raw_value == "-":
        return None
    return raw_value if raw_value.startswith("rs") else f"rs{raw_value}"


def _clinvar_review_stars(review_status: str) -> str | None:
    """Map ClinVar review status text to the documented MVP evidence-level label."""
    normalized = normalize_lookup_text(review_status)
    if normalized == "practice guideline":
        return "4_star"
    if normalized == "reviewed by expert panel":
        return "3_star"
    if normalized == "criteria provided, multiple submitters, no conflicts":
        return "2_star"
    if normalized:
        return "1_star"
    return None
