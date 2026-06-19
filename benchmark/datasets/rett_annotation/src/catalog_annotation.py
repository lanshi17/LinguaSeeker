"""Catalog-driven annotation helpers for the Rett benchmark dataset."""
from __future__ import annotations

import ast
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .models import ArticleVariant, ExpectedEvidenceField, RettExpectedJson
from .utils import classify_variant_type, infer_domain, normalize_hgvs

_RETT_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _RETT_ROOT.parents[2]
_CATALOG_PATH = _PROJECT_ROOT / "knowledges" / "evidence-field-catalog.json"

_VARIANT_FIELD_IDS = {
    "A.variant_hgvs_c",
    "A.variant_hgvs_p",
    "A.variant_hgvs_g",
    "A.variant_legacy_name",
    "A.variant_type",
    "A.null_variant_detail",
    "A.protein_effect",
    "A.same_amino_acid_known_variant",
    "A.same_residue_other_missense",
    "A.functional_domain_or_hotspot",
    "A.protein_length_change",
    "A.repeat_region_status",
    "A.splice_or_synonymous_effect",
    "A.variant_consequence_class",
    "A.identity_by_descent_variant",
}

_EVALUATION_GROUPS = {
    "A": "variant_fields",
    "B": "clinical_fields",
    "C": "segregation_fields",
    "D": "population_fields",
    "E": "computational_fields",
    "F": "functional_fields",
    "G": "case_control_fields",
    "H": "contradiction_fields",
    "I": "gene_function_fields",
    "J": "authority_fields",
}

_CATEGORY_NAMES = {
    "A": "Variant Information",
    "B": "Case/Phenotype Information",
    "C": "Segregation/Family Information",
    "D": "Population/Frequency Information",
    "E": "Computational/Prediction Evidence",
    "F": "Functional Evidence",
    "G": "Case-Control Evidence",
    "H": "Contradiction/Exclusion Evidence",
    "I": "Gene Function/Experimental Evidence",
    "J": "Authority/Time Validity",
}


@dataclass(frozen=True)
class CatalogField:
    """One literature-extractable evidence field from the main catalog."""

    field_id: str
    category_id: str
    category_name: str
    field_name: str
    description: str
    required_for_scorable: bool = False


def load_literature_catalog(catalog_path: Path = _CATALOG_PATH) -> tuple[CatalogField, ...]:
    """Load current A-J evidence fields from the project field catalog."""
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    fields: list[CatalogField] = []
    for item in payload["items"]:
        category_id = str(item["category_id"])
        if category_id == "K":
            continue
        fields.append(
            CatalogField(
                field_id=str(item["field_id"]),
                category_id=category_id,
                category_name=str(item["category_name"]),
                field_name=str(item["field_name"]),
                description=str(item["description"]),
                required_for_scorable=bool(item.get("required_for_scorable", False)),
            )
        )
    return tuple(fields)


def build_catalog_prompt(fields: tuple[CatalogField, ...] | None = None) -> str:
    """Build the LLM system prompt from the current A-J field catalog."""
    fields = fields or load_literature_catalog()
    grouped: dict[str, list[CatalogField]] = defaultdict(list)
    for field in fields:
        grouped[field.category_id].append(field)

    field_lines: list[str] = []
    for category_id in sorted(grouped):
        category_name = _CATEGORY_NAMES.get(category_id, grouped[category_id][0].category_name)
        field_lines.append(f"\n### Category {category_id}: {category_name}")
        for field in grouped[category_id]:
            required = " Required for scoring." if field.required_for_scorable else ""
            field_lines.append(
                f"- {field.field_id}: {field.field_name}. {field.description}.{required}"
            )

    field_count = len(fields)
    return f"""\
You are a medical genetics expert extracting structured evidence from Rett syndrome literature.
Extract only facts explicitly present in the article. Do not infer unstated database values.

The target dataset is Rett syndrome / MECP2 literature, but articles may discuss CDKL5,
FOXG1, MECP2 duplication, atypical Rett, or articles that exclude Rett syndrome.

Return one valid JSON object with exactly these top-level keys:
- metadata: object
- variants: array of variant objects
- field_values: object keyed by field_id

metadata keys:
- gene_symbol
- hgnc_id
- disease_diagnosis
- mondo_id
- mode_of_inheritance
- source_pmid
- source_doi
- source_title
- source_journal
- source_year

variants objects may contain:
- hgvs_c
- hgvs_p
- hgvs_g
- variant_type
- clinical_significance
- exon
- domain
- protein_effect
- null_variant_detail
- protein_length_change
- same_amino_acid_known_variant

field_values must contain all {field_count} A-J field_ids below. Use an empty string for fields not
reported in the article. For repeated values, use a JSON array of strings. Exclude all K.* curation
fields because they are cross-paper fields, not single-paper labels.

Common Rett HPO mappings when phenotypes are stated:
- Seizures / epilepsy -> HP:0001250
- Global developmental delay -> HP:0001263
- Intellectual disability -> HP:0001249
- Hand stereotypies / hand-wringing -> HP:0002072
- Developmental regression -> HP:0002376
- Microcephaly -> HP:0000252
- Progressive microcephaly -> HP:0000253
- Hypotonia -> HP:0001252
- Spasticity -> HP:0001257
- Ataxia / gait ataxia -> HP:0001251
- Breathing abnormalities / hyperventilation / apnea -> HP:0012759
- Autistic behavior -> HP:0000756
- Scoliosis -> HP:0002650
- Sleep disturbance -> HP:0002360
- Bruxism -> HP:0003763
- Delayed motor development -> HP:0002194
- Absent speech -> HP:0001344

Fields:
{"\n".join(field_lines)}
"""


def evaluation_type_for_field(field_id: str) -> str:
    """Return benchmark evaluation type for one field."""
    if field_id in _VARIANT_FIELD_IDS or field_id.startswith("D.") or field_id.startswith("J."):
        return "precision_only"
    return "precision_recall"


def build_evaluation_config(fields: tuple[CatalogField, ...] | None = None) -> dict[str, list[str]]:
    """Build evaluation_config partition keys directly from the catalog."""
    fields = fields or load_literature_catalog()
    config: dict[str, list[str]] = {name: [] for name in _EVALUATION_GROUPS.values()}
    for field in fields:
        group = _EVALUATION_GROUPS[field.category_id]
        config[group].append(field.field_id)
    config["standardization_fields"] = ["gene", "disease"]
    return config


def build_expected_json(
    entry_id: str,
    language: str,
    parsed: Mapping[str, Any],
    fields: tuple[CatalogField, ...] | None = None,
) -> RettExpectedJson:
    """Convert an LLM JSON response into the Rett expected.json schema."""
    fields = fields or load_literature_catalog()
    metadata = _mapping(parsed.get("metadata"))
    field_values = _mapping(parsed.get("field_values"))
    variants = [_build_variant(item) for item in _list(parsed.get("variants")) if isinstance(item, Mapping)]
    evidence = _build_evidence(field_values, fields)

    gene_symbol = _first_text(metadata.get("gene_symbol"), field_values.get("A.gene_symbol"), "MECP2")
    disease_label = _first_text(
        metadata.get("disease_diagnosis"),
        field_values.get("B.disease_diagnosis"),
        "Rett syndrome",
    )
    moi = _first_text(
        metadata.get("mode_of_inheritance"),
        field_values.get("B.mode_of_inheritance_reported"),
        "XD",
    )

    return RettExpectedJson(
        entry_id=entry_id,
        gene_symbol=gene_symbol,
        hgnc_id=_first_text(metadata.get("hgnc_id"), "HGNC:6992"),
        disease_label=disease_label,
        mondo_id=_first_text(metadata.get("mondo_id"), "MONDO:0010726"),
        moi=moi,
        source_pmid=_optional_text(metadata.get("source_pmid")),
        source_doi=_optional_text(metadata.get("source_doi")),
        source_title=_optional_text(metadata.get("source_title")),
        source_journal=_optional_text(metadata.get("source_journal")),
        source_year=_optional_text(metadata.get("source_year")),
        source_language=language,
        variants=variants,
        expected_evidence=evidence,
        evaluation_config=build_evaluation_config(fields),
    )


def parse_llm_json(content: str) -> dict[str, Any] | None:
    """Parse the first JSON object returned by a chat model."""
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end < start:
        return None
    payload = content[start : end + 1]
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(payload)
        except (SyntaxError, ValueError):
            return None
    return parsed if isinstance(parsed, dict) else None


def _build_evidence(
    field_values: Mapping[str, Any],
    fields: tuple[CatalogField, ...],
) -> list[ExpectedEvidenceField]:
    out: list[ExpectedEvidenceField] = []
    for field in fields:
        value = field_values.get(field.field_id)
        value_text, candidates = _value_and_candidates(value)
        if not value_text:
            continue
        out.append(
            ExpectedEvidenceField(
                field_id=field.field_id,
                value=value_text,
                candidates=candidates,
                source="article",
                evaluation_type=evaluation_type_for_field(field.field_id),
            )
        )
    return out


def _build_variant(raw: Mapping[str, Any]) -> ArticleVariant:
    hgvs_c = _first_text(raw.get("hgvs_c"), "")
    hgvs_p = _first_text(raw.get("hgvs_p"), "")
    return ArticleVariant(
        hgvs_c=normalize_hgvs(hgvs_c),
        hgvs_p=normalize_hgvs(hgvs_p),
        hgvs_g=normalize_hgvs(_first_text(raw.get("hgvs_g"), "")),
        variant_type=_first_text(raw.get("variant_type"), "") or classify_variant_type(hgvs_c, hgvs_p),
        clinical_significance=_first_text(raw.get("clinical_significance"), ""),
        exon=_first_text(raw.get("exon"), ""),
        domain=_first_text(raw.get("domain"), "") or infer_domain(hgvs_p),
        protein_effect=_first_text(raw.get("protein_effect"), ""),
        null_variant_detail=_first_text(raw.get("null_variant_detail"), ""),
        protein_length_change=_first_text(raw.get("protein_length_change"), ""),
        same_amino_acid_known_variant=_first_text(raw.get("same_amino_acid_known_variant"), ""),
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _value_and_candidates(value: Any) -> tuple[str, list[str]]:
    if isinstance(value, list):
        candidates = [_stringify(item) for item in value]
        candidates = [item for item in candidates if item]
        return "; ".join(candidates), candidates
    text = _stringify(value)
    return text, []


def _first_text(*values: Any) -> str:
    for value in values:
        text = _stringify(value)
        if text:
            return text
    return ""


def _optional_text(value: Any) -> str | None:
    text = _stringify(value)
    return text or None


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
