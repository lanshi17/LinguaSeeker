"""Select ClinGen x ClinVar fused entries for benchmark evaluation.

Selection strategy:
1. ClinGen: filter to Definitive + Strong gene-disease pairs
2. ClinVar: filter to high-confidence germline Pathogenic/LP variants (>=2 stars)
3. JOIN on GeneSymbol + MONDO ID (ClinVar PhenotypeIDS contains MONDO ID)
4. For each fused group, keep top-3 variants by review stars
5. Score and rank by diversity (MOI, GCEP, variant count)
6. Select top N entries (default 50 for pilot)
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from benchmark.datasets.clinvar_fused.hgvs_normalize import (
    _parse_hgvs_from_clinvar_name,
    normalize_variant_type,
)

# Paths — resolve to main repo root (database/ may not exist in worktrees)
_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
_MAIN_REPO = Path("/data/[redacted-user]/Projects/01_ACMG_Lingua")
_DATABASE_ROOT = _MAIN_REPO / "database" / "terminology_database"
CLINGEN_CSV = _DATABASE_ROOT / "clingen" / "Clingen-Gene-Disease-Summary.csv"
CLINVAR_TSV = _DATABASE_ROOT / "clinvar" / "variant_summary.txt"
OUTPUT_DIR = Path(__file__).resolve().parent / "ground_truth"

# ── ClinGen filtering ──────────────────────────────────────────────────

CLINGEN_CLASSIFICATIONS = {"Definitive", "Strong"}


def parse_clingen_csv() -> list[dict[str, str]]:
    """Parse ClinGen CSV, keeping only Definitive + Strong entries."""
    rows: list[dict[str, str]] = []
    with open(CLINGEN_CSV, encoding="utf-8") as f:
        lines = f.readlines()

    header_idx: int | None = None
    for i, line in enumerate(lines):
        if "GENE SYMBOL" in line and "CLASSIFICATION" in line:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Could not find header row in ClinGen CSV")

    header = [h.strip().strip('"') for h in lines[header_idx].strip().split(",")]
    for line in lines[header_idx + 1 :]:
        line = line.strip()
        if not line or "+++" in line:
            continue
        reader = csv.reader([line])
        values = next(reader)
        if len(values) < 7:
            continue
        row = {header[j]: values[j].strip() for j in range(min(len(header), len(values)))}
        if row.get("CLASSIFICATION", "") in CLINGEN_CLASSIFICATIONS:
            rows.append(row)
    return rows


# ── ClinVar filtering ──────────────────────────────────────────────────

ACCEPTED_REVIEW_STATUSES = {
    "practice guideline",
    "reviewed by expert panel",
    "criteria provided, multiple submitters, no conflicts",
}

ACCEPTED_CLIN_SIG = {
    "pathogenic",
    "likely pathogenic",
    "pathogenic/likely pathogenic",
}

REVIEW_STAR_MAP = {
    "practice guideline": 4,
    "reviewed by expert panel": 3,
    "criteria provided, multiple submitters, no conflicts": 2,
    "criteria provided, single submitter": 1,
    "no assertion criteria provided": 0,
    "no classification provided": 0,
    "no assertion provided": 0,
}


def _review_stars(status: str) -> int:
    """Map ClinVar ReviewStatus to star count."""
    status_lower = status.strip().lower()
    for key, stars in REVIEW_STAR_MAP.items():
        if key in status_lower:
            return stars
    return 0


def _extract_mondo_ids(phenotype_ids: str) -> set[str]:
    """Extract MONDO IDs from ClinVar PhenotypeIDS field.

    PhenotypeIDS format: MONDO:MONDO:0003582,OMIM:604370,MedGen:C0676282||MedGen:C3661900
    Returns set of normalized MONDO IDs (e.g. "MONDO:0003582").
    """
    mondo_ids: set[str] = set()
    for part in re.split(r"[,|]", phenotype_ids):
        part = part.strip()
        # Match MONDO:MONDO:XXXXXXX or MONDO:XXXXXXX
        m = re.search(r"MONDO:(?:MONDO:)?(\d+)", part)
        if m:
            mondo_ids.add(f"MONDO:{m.group(1)}")
    return mondo_ids


@dataclass
class ClinVarVariant:
    """Parsed ClinVar variant entry."""

    variation_id: int
    name: str
    gene_symbol: str
    hgnc_id: str
    clinical_significance: str
    review_status: str
    review_stars: int
    rsid: str
    phenotype_ids: str
    phenotype_list: str
    variant_type: str
    origin: str
    mondo_ids: set[str] = field(default_factory=set)
    hgvs_c: str = ""
    hgvs_p: str = ""

    def to_dict(self) -> dict:
        return {
            "variation_id": self.variation_id,
            "hgvs_name": self.name,
            "hgvs_c": self.hgvs_c,
            "hgvs_p": self.hgvs_p,
            "variant_type": self.variant_type,
            "clinical_significance": self.clinical_significance,
            "review_status": self.review_status,
            "review_stars": self.review_stars,
            "rsid": self.rsid,
            "phenotype_ids": self.phenotype_ids,
            "phenotype_list": self.phenotype_list,
        }


def parse_clinvar_tsv() -> dict[str, list[ClinVarVariant]]:
    """Parse ClinVar variant_summary.txt, filter and group by gene symbol.

    Returns dict mapping gene_symbol -> list of ClinVarVariant.
    """
    by_gene: dict[str, list[ClinVarVariant]] = {}
    skipped = {"sig": 0, "review": 0, "origin": 0, "parsed": 0}

    with open(CLINVAR_TSV, encoding="utf-8") as f:
        header_line = f.readline()  # skip header
        headers = header_line.strip().split("\t")
        header_idx = {h: i for i, h in enumerate(headers)}

        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 10:
                continue

            # Filter: ClinicalSignificance
            clin_sig = parts[header_idx["ClinicalSignificance"]].strip().lower()
            if clin_sig not in ACCEPTED_CLIN_SIG:
                skipped["sig"] += 1
                continue

            # Filter: ReviewStatus (>= 2 stars)
            review_status = parts[header_idx["ReviewStatus"]].strip()
            stars = _review_stars(review_status)
            if stars < 2:
                skipped["review"] += 1
                continue

            # Filter: OriginSimple (germline only)
            origin_simple = parts[header_idx["OriginSimple"]].strip().lower()
            if "germline" not in origin_simple:
                skipped["origin"] += 1
                continue

            gene_symbol = parts[header_idx["GeneSymbol"]].strip()
            if not gene_symbol:
                continue

            # Parse HGVS name
            name = parts[header_idx["Name"]].strip()
            hgvs = _parse_hgvs_from_clinvar_name(name)

            variant_type_raw = parts[header_idx.get("Type", 0)].strip()
            variant_type = normalize_variant_type(variant_type_raw)

            rsid_raw = parts[header_idx["RS# (dbSNP)"]].strip()
            rsid = f"rs{rsid_raw}" if rsid_raw and rsid_raw != "-" else ""

            phenotype_ids = parts[header_idx["PhenotypeIDS"]].strip()
            phenotype_list = parts[header_idx["PhenotypeList"]].strip()
            mondo_ids = _extract_mondo_ids(phenotype_ids)

            hgnc_id = parts[header_idx["HGNC_ID"]].strip()

            try:
                variation_id = int(parts[header_idx["VariationID"]])
            except (ValueError, KeyError):
                skipped["parsed"] += 1
                continue

            variant = ClinVarVariant(
                variation_id=variation_id,
                name=name,
                gene_symbol=gene_symbol,
                hgnc_id=hgnc_id,
                clinical_significance=parts[header_idx["ClinicalSignificance"]].strip(),
                review_status=review_status,
                review_stars=stars,
                rsid=rsid,
                phenotype_ids=phenotype_ids,
                phenotype_list=phenotype_list,
                variant_type=variant_type,
                origin=parts[header_idx["Origin"]].strip(),
                mondo_ids=mondo_ids,
                hgvs_c=hgvs.get("hgvs_c", ""),
                hgvs_p=hgvs.get("hgvs_p", ""),
            )
            by_gene.setdefault(gene_symbol, []).append(variant)

    print(f"  ClinVar: {sum(len(v) for v in by_gene.values())} variants across {len(by_gene)} genes")
    print(f"  Skipped: sig={skipped['sig']}, review={skipped['review']}, origin={skipped['origin']}, parse={skipped['parsed']}")
    return by_gene


# ── Fusion ─────────────────────────────────────────────────────────────


@dataclass
class FusedEntry:
    """A fused ClinGen + ClinVar benchmark entry."""

    clingen: dict[str, str]
    clinvar_variants: list[ClinVarVariant]

    @property
    def gene_symbol(self) -> str:
        return self.clingen.get("GENE SYMBOL", "")

    @property
    def mondo_id(self) -> str:
        return self.clingen.get("DISEASE ID (MONDO)", "")

    @property
    def classification(self) -> str:
        return self.clingen.get("CLASSIFICATION", "")


def fuse_entries(
    clingen_rows: list[dict[str, str]],
    clinvar_by_gene: dict[str, list[ClinVarVariant]],
    max_variants_per_entry: int = 3,
) -> list[FusedEntry]:
    """Join ClinGen and ClinVar on GeneSymbol + MONDO ID."""
    fused: list[FusedEntry] = []
    no_match = 0

    for cg in clingen_rows:
        gene = cg.get("GENE SYMBOL", "")
        mondo_id = cg.get("DISEASE ID (MONDO)", "")

        # Find ClinVar variants for this gene
        gene_variants = clinvar_by_gene.get(gene, [])
        if not gene_variants:
            no_match += 1
            continue

        # Filter: variant's PhenotypeIDS must contain this MONDO ID
        matching = [v for v in gene_variants if mondo_id in v.mondo_ids]
        if not matching:
            # Fallback: try without MONDO match (same gene, any phenotype)
            # Only if the gene has variants but none match this specific disease
            no_match += 1
            continue

        # Sort by review stars (desc), then by variation_id (asc, deterministic)
        matching.sort(key=lambda v: (-v.review_stars, v.variation_id))

        # Dedup by variation_id
        seen_ids: set[int] = set()
        unique: list[ClinVarVariant] = []
        for v in matching:
            if v.variation_id not in seen_ids:
                seen_ids.add(v.variation_id)
                unique.append(v)

        top_variants = unique[:max_variants_per_entry]
        fused.append(FusedEntry(clingen=cg, clinvar_variants=top_variants))

    print(f"  Fused: {len(fused)} entries ({no_match} ClinGen entries had no ClinVar match)")
    return fused


# ── Selection ──────────────────────────────────────────────────────────


def select_entries(
    fused: list[FusedEntry],
    target_count: int = 50,
) -> list[FusedEntry]:
    """Select top entries by diversity score.

    Scoring:
    - Prefer diverse MOI
    - Prefer diverse GCEP
    - Prefer higher ClinVar review stars
    - Prefer more variants per entry
    """
    mois_seen: Counter[str] = Counter()
    gceps_seen: set[str] = set()
    scored: list[tuple[float, FusedEntry]] = []

    for fe in fused:
        moi = fe.clingen.get("MOI", "")
        gcep = fe.clingen.get("GCEP", "")
        max_stars = max((v.review_stars for v in fe.clinvar_variants), default=0)
        variant_count = len(fe.clinvar_variants)

        # Lower score = higher priority
        moi_penalty = mois_seen.get(moi, 0) * 2
        gcep_penalty = 3 if gcep in gceps_seen else 0
        star_bonus = -max_stars  # Higher stars = lower score
        variant_bonus = -variant_count * 0.5

        score = moi_penalty + gcep_penalty + star_bonus + variant_bonus
        scored.append((score, fe))

    scored.sort(key=lambda x: x[0])

    selected: list[FusedEntry] = []
    for _, fe in scored:
        if len(selected) >= target_count:
            break
        selected.append(fe)
        mois_seen[fe.clingen.get("MOI", "")] += 1
        gceps_seen.add(fe.clingen.get("GCEP", ""))

    return selected


# ── Output ─────────────────────────────────────────────────────────────


def _map_classification_to_relationship(classification: str) -> str:
    mapping = {
        "Definitive": "causative",
        "Strong": "causative",
        "Moderate": "causative",
        "Limited": "uncertain",
        "Disputed": "disputed",
        "Refuted": "refuted",
    }
    return mapping.get(classification, "unknown")


def build_gold_json(entries: list[FusedEntry]) -> list[dict]:
    """Build fused gold standard JSON for each entry."""
    gold_entries: list[dict] = []

    for i, fe in enumerate(entries):
        cg = fe.clingen
        gene = cg.get("GENE SYMBOL", "")
        hgnc_id = cg.get("GENE ID (HGNC)", "")
        disease = cg.get("DISEASE LABEL", "")
        mondo_id = cg.get("DISEASE ID (MONDO)", "")
        moi = cg.get("MOI", "")
        classification = cg.get("CLASSIFICATION", "")
        gcep = cg.get("GCEP", "")
        report_url = cg.get("ONLINE REPORT", "")
        date = cg.get("CLASSIFICATION DATE", "")

        # Build variant candidates
        variant_candidates_c: list[str] = []
        variant_candidates_p: list[str] = []
        variant_type_values: list[str] = []
        clin_sig_values: list[str] = []
        variation_ids: list[str] = []
        variant_entities: list[dict] = []

        for v in fe.clinvar_variants:
            if v.hgvs_c:
                variant_candidates_c.append(v.hgvs_c)
            if v.hgvs_p:
                variant_candidates_p.append(v.hgvs_p)
            variant_type_values.append(v.variant_type)
            clin_sig_values.append(v.clinical_significance)
            variation_ids.append(f"ClinVarVariation:{v.variation_id}")
            variant_entities.append({
                "text": v.hgvs_c or v.hgvs_p or v.name,
                "variation_id": f"ClinVarVariation:{v.variation_id}",
                "rsid": v.rsid,
            })

        # Expected evidence fields
        expected_evidence = [
            # Gene-disease layer (precision_recall)
            {
                "field_id": "A.gene_symbol",
                "value": gene,
                "source": "clingen",
                "evaluation_type": "precision_recall",
            },
            {
                "field_id": "B.disease_diagnosis",
                "value": disease,
                "source": "clingen",
                "evaluation_type": "precision_recall",
            },
            {
                "field_id": "A.gene_disease_relationship",
                "value": _map_classification_to_relationship(classification),
                "source": "clingen",
                "evaluation_type": "precision_recall",
            },
            {
                "field_id": "B.mode_of_inheritance_reported",
                "value": moi,
                "source": "clingen",
                "evaluation_type": "precision_recall",
            },
            # Variant layer (precision_only)
            {
                "field_id": "A.variant_hgvs_c",
                "value": variant_candidates_c[0] if variant_candidates_c else "",
                "candidates": variant_candidates_c,
                "source": "clinvar",
                "evaluation_type": "precision_only",
            },
            {
                "field_id": "A.variant_hgvs_p",
                "value": variant_candidates_p[0] if variant_candidates_p else "",
                "candidates": variant_candidates_p,
                "source": "clinvar",
                "evaluation_type": "precision_only",
            },
            {
                "field_id": "A.variant_type",
                "value": variant_type_values[0] if variant_type_values else "",
                "candidates": variant_type_values,
                "source": "clinvar",
                "evaluation_type": "precision_only",
            },
            {
                "field_id": "J.clinvar_assertion",
                "value": clin_sig_values[0] if clin_sig_values else "",
                "candidates": clin_sig_values,
                "source": "clinvar",
                "evaluation_type": "precision_only",
            },
        ]

        # Remove fields with empty values
        expected_evidence = [e for e in expected_evidence if e.get("value")]

        gold = {
            "entry_id": f"fused_{i:03d}",
            "source": "clingen_clinvar_fused",
            "clingen": {
                "gene_symbol": gene,
                "hgnc_id": hgnc_id,
                "disease_label": disease,
                "mondo_id": mondo_id,
                "moi": moi,
                "classification": classification,
                "gcep": gcep,
                "classification_date": date,
                "report_url": report_url,
            },
            "clinvar_variants": [v.to_dict() for v in fe.clinvar_variants],
            "expected_evidence": expected_evidence,
            "expected_standardization": {
                "gene": hgnc_id,
                "disease": mondo_id,
                "variant_candidates": variation_ids,
            },
            "expected_entities": {
                "gene": {"text": gene, "hgnc_id": hgnc_id},
                "disease": {"text": disease, "mondo_id": mondo_id},
                "variants": variant_entities,
            },
            "evaluation_config": {
                "gene_disease_fields": [
                    "A.gene_symbol",
                    "B.disease_diagnosis",
                    "A.gene_disease_relationship",
                    "B.mode_of_inheritance_reported",
                ],
                "variant_fields": [
                    f["field_id"]
                    for f in expected_evidence
                    if f.get("evaluation_type") == "precision_only"
                ],
                "standardization_fields": ["gene", "disease", "variant"],
            },
            # Literature placeholders (filled by fetch_variant_literature.py)
            "source_pmid": None,
            "source_pmc": None,
            "source_pdf_url": None,
            "source_title": None,
            "source_journal": None,
            "source_year": None,
            "notes": "",
        }
        gold_entries.append(gold)

    return gold_entries


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Parse ClinGen
    print("Step 1: Parsing ClinGen CSV...")
    clingen_rows = parse_clingen_csv()
    print(f"  ClinGen: {len(clingen_rows)} Definitive/Strong entries")
    cls_counts = Counter(r.get("CLASSIFICATION") for r in clingen_rows)
    print(f"  By classification: {dict(cls_counts)}")

    # Step 2: Parse ClinVar
    print("Step 2: Parsing ClinVar variant_summary.txt...")
    clinvar_by_gene = parse_clinvar_tsv()

    # Step 3: Fuse
    print("Step 3: Fusing ClinGen x ClinVar...")
    fused = fuse_entries(clingen_rows, clinvar_by_gene)

    # Step 4: Select
    print("Step 4: Selecting top entries...")
    selected = select_entries(fused, target_count=75)
    print(f"  Selected: {len(selected)} entries")

    # Print selection summary
    moi_counts = Counter(fe.clingen.get("MOI") for fe in selected)
    star_dist = Counter(
        max(v.review_stars for v in fe.clinvar_variants)
        for fe in selected
    )
    variant_count_dist = Counter(len(fe.clinvar_variants) for fe in selected)
    print(f"  By MOI: {dict(moi_counts)}")
    print(f"  By max review stars: {dict(star_dist)}")
    print(f"  By variant count: {dict(variant_count_dist)}")

    # Step 5: Build gold JSON
    print("Step 5: Building fused gold JSON...")
    gold_entries = build_gold_json(selected)

    # Save selection.json
    selection_path = OUTPUT_DIR / "selection.json"
    selection_path.write_text(
        json.dumps(gold_entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Saved {selection_path}")

    # Save individual entries
    for gold in gold_entries:
        entry_dir = OUTPUT_DIR / gold["entry_id"]
        entry_dir.mkdir(parents=True, exist_ok=True)
        (entry_dir / "expected.json").write_text(
            json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"  Created {len(gold_entries)} entry directories")

    print("Done.")


if __name__ == "__main__":
    main()
