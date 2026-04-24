# Gold Standard JSON to Evidence JSON Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert JSON files in `benchmark/Gold-Standard-Json/` into this project’s actual `EvidenceOutput` JSON format.

**Architecture:** Add a small deterministic converter in the backend domain layer that maps each gold-standard assay/readout result into one project `EvidenceOutput` record. Keep the converter independent of LLM, database, and network services, then add a CLI script that can batch-convert all benchmark JSON files into JSON outputs validated by `src.domain.models.EvidenceOutput`.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, existing backend models in `apps/backend/src/domain/models.py`.

---

## Observed Formats

### Source format

Representative source file: `benchmark/Gold-Standard-Json/14749723.json`.

Top-level keys:

```json
{
  "Variants Include": [
    {
      "Gene": "PRKN",
      "variants": [
        {
          "HGVS": "NM_004562.3:c.1252T>C",
          "cDNA Change": {
            "transcript": "NM_003976.2",
            "ref": "T",
            "alt": "C",
            "position": "1252"
          },
          "Protein Change": {
            "ref": "C",
            "alt": "R",
            "position": "418"
          },
          "Description in input context": "C418R"
        }
      ]
    }
  ],
  "Described Disease": {
    "Described Disease": "Autosomal recessive juvenile Parkinson’s disease (AR-JP)",
    "MONDO": "MONDO:0010820"
  },
  "Experiment Method": [
    {
      "Assay Method": "Caspase-3 activity measurements",
      "Material used": {
        "Material Source": "Cell line",
        "Material Name": "TSM1 neurons, SH-SY5Y cells",
        "Description": "Cells were grown in 6-well plates..."
      },
      "Readout type": "Quantitative",
      "Readout description": [
        {
          "Variant": "NM_004562.3:c.1252T>C",
          "Conclusion": "Abnormal",
          "Molecular Effect": "complete loss-of function",
          "Result Description": "Caspase-3 activity was measured..."
        }
      ],
      "Biological replicates": {"Biological replicates": "Yes", "Description": "..."},
      "Technical replicates": {"Technical replicates": "Yes", "Description": "..."},
      "Basic positive control": {"Basic positive control": "Yes", "Description": "..."},
      "Basic negative control": {"Basic negative control": "N.D.", "Description": "N.D."},
      "Validation controls P/LP": {"Validation controls P/LP": "N.D.", "Counts": "N.D."},
      "Validation controls B/LB": {"Validation controls B/LB": "N.D.", "Counts": "N.D."},
      "Statistical analysis method": {"Statistical analysis method": "..."},
      "Threshold for normal readout": {"Threshold for normal readout": "N.D.", "Source": "N.D."},
      "Threshold for abnormal readout": {"Threshold for abnormal readout": "N.D.", "Source": "N.D."},
      "Approved assay": {"Approved assay": "Yes"}
    }
  ]
}
```

Important source quirks to support:

- `Readout description[*].Variant` sometimes includes parenthetical protein names, e.g. `NM_007262.5:c.497T>C (L166P)` in `benchmark/Gold-Standard-Json/19801972.json`.
- Readouts can mention variants that are absent from `Variants Include`, e.g. `NM_007262.5:c.155G>C` in `19801972.json`; converter must still emit a record with partial variant data.
- Some values that are usually strings can be dictionaries, e.g. `Basic negative control.Description` in `19801972.json`.
- `N.D.` means missing/unknown and should not be treated as affirmative evidence.

### Target format

Canonical target model: `apps/backend/src/domain/models.py:117-137`, `EvidenceOutput`.

Golden target fixture: `apps/backend/tests/fixtures/golden_evidence_output.json`.

Required/important target keys:

```json
{
  "ps3_evidence": {
    "ps3_step_1": {"score": 0.0, "summary": "..."},
    "ps3_step_2": {"score": 0.0, "summary": "..."},
    "ps3_step_3": {"score": 0.0, "summary": "..."},
    "ps3_step_4": {
      "score": 0.0,
      "final_evidence_strength": "PS3_supporting",
      "oddspath_data": {
        "computable": false,
        "functional_evidence_aim": "pathogenic"
      }
    },
    "overall_assessment": {"total_score": 0.0, "reasoning": "..."}
  },
  "arbitration_confidence": null,
  "image_descriptions": [],
  "evidence_sources": [],
  "final_evidence_strength": "PS3_supporting",
  "status": "success",
  "origin_format_md": null,
  "en_format_md": null,
  "extracted_fields": {
    "gene": {"symbol": "PRKN", "confidence": 100.0},
    "transcript_id": {"transcript_id": "NM_004562.3", "confidence": 100.0},
    "reference_genome_version": {"version": "unknown", "confidence": 0.0},
    "experiment_data": {
      "assay_type": "Caspase-3 activity measurements",
      "method_description": "...",
      "key_findings": ["..."],
      "statistical_data": {"statistical_analysis_method": "..."},
      "cell_line": "TSM1 neurons, SH-SY5Y cells",
      "model_organism": null,
      "confidence": 100.0
    },
    "disease_chpo": {"disease_name": "...", "confidence": 100.0},
    "disease_icd10": {"disease_name": "...", "confidence": 100.0},
    "species": {"species_name": "Homo sapiens", "is_human": true, "confidence": 50.0},
    "phenotype": {"phenotype_description": "...", "confidence": 80.0},
    "variant": {
      "hgvs_c": "NM_004562.3:c.1252T>C",
      "hgvs_p": "p.Cys418Arg",
      "ref_allele": "T",
      "alt_allele": "C",
      "variant_type": "missense",
      "confidence": 100.0
    },
    "negative_positive_control": {
      "has_negative_control": false,
      "has_positive_control": true,
      "negative_control_description": null,
      "positive_control_description": "WT should be used as a basic positive control.",
      "total_control_count": 0,
      "confidence": 100.0
    },
    "pedigree_information": {"has_pedigree": false, "confidence": 0.0}
  },
  "field_confidence_scores": {"gene": 100.0},
  "overall_confidence": 80.0,
  "evidence_classification": "Pathogenic",
  "acmg_evidence_levels": ["PS3"]
}
```

`EvidenceOutput` has a single `variant` field, so this plan emits one output record per source readout row (`Experiment Method[*].Readout description[*]`) rather than one output per paper.

---

## Mapping Rules

### Record granularity

For each input file:

1. Build a lookup of source variants from `Variants Include[*].variants[*]`.
2. Iterate each assay in `Experiment Method`.
3. Iterate each row in `assay["Readout description"]`.
4. Emit one `EvidenceOutput` object per readout row.
5. Batch converter writes a JSON array for each input file.

Output file naming:

- Input: `benchmark/Gold-Standard-Json/14749723.json`
- Output: `benchmark/evidence-json/14749723.evidence.json`

### Source-to-target field mapping

| Source | Target |
| --- | --- |
| input filename stem | `evidence_sources`, e.g. `["PMID:14749723"]` |
| `Variants Include[*].Gene` | `extracted_fields.gene.symbol` |
| matched variant `HGVS` or readout `Variant` | `extracted_fields.variant.hgvs_c` |
| matched `cDNA Change.transcript` | `extracted_fields.transcript_id.transcript_id` |
| matched `cDNA Change.ref` | `extracted_fields.variant.ref_allele` |
| matched `cDNA Change.alt` | `extracted_fields.variant.alt_allele` |
| matched `Protein Change` | `extracted_fields.variant.hgvs_p` as three-letter HGVS protein when possible, e.g. `p.Cys418Arg`; fallback to `p.C418R` |
| `Described Disease.Described Disease` | `extracted_fields.disease_chpo.disease_name`, `disease_icd10.disease_name`, `phenotype.phenotype_description` |
| `Described Disease.MONDO` | store under disease `evidence_quote` or omit; do not invent CHPO/ICD-10 IDs |
| `Assay Method` | `extracted_fields.experiment_data.assay_type` |
| `Material used.Description` | `extracted_fields.experiment_data.method_description` |
| `Material used.Material Name` | `extracted_fields.experiment_data.cell_line` if material source mentions `Cell line`; otherwise `model_organism` if material source mentions animal terms |
| `Readout type` | `extracted_fields.experiment_data.statistical_data.readout_type` |
| `Readout description[*].Result Description` | `extracted_fields.experiment_data.key_findings[0]` |
| `Statistical analysis method.Statistical analysis method` | `extracted_fields.experiment_data.statistical_data.statistical_analysis_method` |
| `Biological replicates`, `Technical replicates` | `ps3_evidence.ps3_step_3.checkpoint_3a.replicates_used` and summary |
| `Basic positive control` | `extracted_fields.negative_positive_control.has_positive_control` and description |
| `Basic negative control` | `extracted_fields.negative_positive_control.has_negative_control` and description |
| `Validation controls P/LP.Counts` | `ps3_evidence.ps3_step_4.control_count_data.pathogenic_count` |
| `Validation controls B/LB.Counts` | `ps3_evidence.ps3_step_4.control_count_data.benign_count` |
| `Approved assay.Approved assay` | `ps3_evidence.ps3_step_2.assay_suitable` |
| `Readout description[*].Conclusion` and `Molecular Effect` | `ps3_evidence.ps3_step_4.oddspath_data.functional_evidence_aim`, `evidence_classification` |

### Normalization helpers

Implement these helpers in the converter:

```python
def is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "n.d.", "nd", "n/a", "na", "not determined", "unknown"}
    return False
```

```python
def yes_no_to_bool(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() in {"yes", "true", "1", "present", "approved"}
```

```python
def stringify(value: object) -> str | None:
    if is_missing(value):
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            text = stringify(item)
            if text:
                parts.append(f"{key}: {text}")
        return "; ".join(parts) if parts else None
    if isinstance(value, list):
        parts = [stringify(item) for item in value]
        parts = [item for item in parts if item]
        return "; ".join(parts) if parts else None
    return str(value)
```

```python
def normalize_variant_key(value: str) -> str:
    # Drop parenthetical suffixes and whitespace.
    # "NM_007262.5:c.497T>C (L166P)" -> "NM_007262.5:c.497T>C"
    return re.sub(r"\s*\([^)]*\)\s*$", "", value.strip())
```

```python
AA3 = {
    "A": "Ala", "R": "Arg", "N": "Asn", "D": "Asp", "C": "Cys",
    "Q": "Gln", "E": "Glu", "G": "Gly", "H": "His", "I": "Ile",
    "L": "Leu", "K": "Lys", "M": "Met", "F": "Phe", "P": "Pro",
    "S": "Ser", "T": "Thr", "W": "Trp", "Y": "Tyr", "V": "Val",
    "*": "Ter",
}

def protein_hgvs(change: dict[str, object] | None, fallback: str | None) -> str | None:
    if not change:
        return f"p.{fallback}" if fallback and re.match(r"^[A-Z*]\d+[A-Z*]$", fallback) else None
    ref = stringify(change.get("ref"))
    alt = stringify(change.get("alt"))
    position = stringify(change.get("position"))
    if ref and alt and position:
        return f"p.{AA3.get(ref, ref)}{position}{AA3.get(alt, alt)}"
    return None
```

### Confidence rules

These benchmark files are gold-standard annotations, not LLM predictions. Use deterministic confidences:

- Present direct annotation fields: `100.0`
- Inferred/default species: `50.0`
- Missing/unknown fields: `0.0`
- `overall_confidence`: computed by `ExtractedEvidenceFields.compute_overall_confidence()`.
- `field_confidence_scores`: computed by `ExtractedEvidenceFields.compute_field_confidence_scores()`.

### PS3/BS3 scoring rules

Use conservative deterministic scoring, not LLM scoring:

- `ps3_step_1.score`: `20.0` if disease name is present, else `0.0`.
- `ps3_step_2.score`: `20.0` if approved assay is `Yes`, else `0.0`.
- `ps3_step_3.score`:
  - `20.0` if positive control, negative control, and biological or technical replicates are present.
  - `15.0` if positive control and any replicate are present.
  - `10.0` if positive control or negative control is present.
  - `0.0` otherwise.
- `ps3_step_4.score`: `20.0` if readout conclusion is non-missing and not `Normal`, else `0.0`.
- `overall_assessment.total_score`: sum of steps, capped at `100.0`.

Evidence direction:

- If `Conclusion` contains `Abnormal`, `Molecular Effect` contains `loss`, or result describes reduced/impaired function, set `functional_evidence_aim = "pathogenic"`.
- If `Conclusion` contains `Normal`, no functional impact, or wild-type-like, set `functional_evidence_aim = "benign"`.
- Otherwise default to `"pathogenic"` because these benchmark files are functional evidence annotations.

Evidence strength:

- If `Conclusion` is missing or `N.D.`, use `"Inconclusive"`, empty `acmg_evidence_levels`, and `evidence_classification = "Uncertain Significance"`.
- If direction is pathogenic and total score >= 70, use `"PS3"`, `acmg_evidence_levels = ["PS3"]`, `evidence_classification = "Pathogenic"`.
- If direction is pathogenic and total score >= 50, use `"PS3_moderate"`, `acmg_evidence_levels = ["PM1"]`, `evidence_classification = "Likely Pathogenic"`.
- If direction is pathogenic and total score > 0, use `"PS3_supporting"`, `acmg_evidence_levels = ["PP3"]`, `evidence_classification = "Likely Pathogenic"`.
- If direction is benign and total score >= 70, use `"BS3"`, `acmg_evidence_levels = ["BS3"]`, `evidence_classification = "Benign"`.
- If direction is benign and total score >= 50, use `"BS3_moderate"`, `acmg_evidence_levels = ["BS2"]`, `evidence_classification = "Likely Benign"`.
- If direction is benign and total score > 0, use `"BS3_supporting"`, `acmg_evidence_levels = ["BP4"]`, `evidence_classification = "Likely Benign"`.

---

### Task 1: Add converter test fixture

**Files:**
- Create: `apps/backend/tests/fixtures/gold_standard_source_minimal.json`

**Step 1: Create the fixture**

Create `apps/backend/tests/fixtures/gold_standard_source_minimal.json`:

```json
{
  "Variants Include": [
    {
      "Gene": "PRKN",
      "variants": [
        {
          "HGVS": "NM_004562.3:c.1252T>C",
          "cDNA Change": {
            "transcript": "NM_004562.3",
            "ref": "T",
            "alt": "C",
            "position": "1252"
          },
          "Protein Change": {
            "ref": "C",
            "alt": "R",
            "position": "418"
          },
          "Description in input context": "C418R"
        }
      ]
    }
  ],
  "Described Disease": {
    "Described Disease": "Autosomal recessive juvenile Parkinson’s disease (AR-JP)",
    "MONDO": "MONDO:0010820"
  },
  "Experiment Method": [
    {
      "Assay Method": "Caspase-3 activity measurements",
      "Material used": {
        "Material Source": "Cell line",
        "Material Name": "TSM1 neurons, SH-SY5Y cells",
        "Description": "Cells were incubated with staurosporine."
      },
      "Readout type": "Quantitative",
      "Readout description": [
        {
          "Variant": "NM_004562.3:c.1252T>C",
          "Conclusion": "Abnormal",
          "Molecular Effect": "complete loss-of function",
          "Result Description": "Caspase-3 activity was measured in cells overexpressing parkin mutant C418R."
        }
      ],
      "Biological replicates": {
        "Biological replicates": "Yes",
        "Description": "3 independent experiments"
      },
      "Technical replicates": {
        "Technical replicates": "Yes",
        "Description": "triplicate"
      },
      "Basic positive control": {
        "Basic positive control": "Yes",
        "Description": "WT should be used as a basic positive control."
      },
      "Basic negative control": {
        "Basic negative control": "N.D.",
        "Description": "N.D."
      },
      "Validation controls P/LP": {
        "Validation controls P/LP": "N.D.",
        "Counts": "N.D."
      },
      "Validation controls B/LB": {
        "Validation controls B/LB": "N.D.",
        "Counts": "N.D."
      },
      "Statistical analysis method": {
        "Statistical analysis method": "Student t-test"
      },
      "Threshold for normal readout": {
        "Threshold for normal readout": "N.D.",
        "Source": "N.D."
      },
      "Threshold for abnormal readout": {
        "Threshold for abnormal readout": "N.D.",
        "Source": "N.D."
      },
      "Approved assay": {
        "Approved assay": "Yes"
      }
    }
  ]
}
```

**Step 2: Commit**

```bash
git add apps/backend/tests/fixtures/gold_standard_source_minimal.json
git commit -m "test: add gold standard converter fixture"
```

---

### Task 2: Write failing unit tests for single-record conversion

**Files:**
- Create: `apps/backend/tests/unit/test_gold_standard_converter.py`
- Fixture: `apps/backend/tests/fixtures/gold_standard_source_minimal.json`

**Step 1: Write failing tests**

Create `apps/backend/tests/unit/test_gold_standard_converter.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.domain.models import EvidenceOutput, ExtractedEvidenceFields
from src.domain.evidence.gold_standard_converter import convert_gold_standard_payload


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def test_convert_gold_standard_payload_emits_valid_evidence_output() -> None:
    payload = json.loads((FIXTURES_DIR / "gold_standard_source_minimal.json").read_text())

    records = convert_gold_standard_payload(payload, source_id="14749723")

    assert len(records) == 1
    output = EvidenceOutput.model_validate(records[0])
    fields = ExtractedEvidenceFields.model_validate(output.extracted_fields)

    assert output.status == "success"
    assert output.evidence_sources == ["PMID:14749723"]
    assert output.final_evidence_strength == "PS3_supporting"
    assert output.acmg_evidence_levels == ["PP3"]
    assert output.evidence_classification == "Likely Pathogenic"
    assert fields.gene is not None
    assert fields.gene.symbol == "PRKN"
    assert fields.transcript_id is not None
    assert fields.transcript_id.transcript_id == "NM_004562.3"
    assert fields.variant is not None
    assert fields.variant.hgvs_c == "NM_004562.3:c.1252T>C"
    assert fields.variant.hgvs_p == "p.Cys418Arg"
    assert fields.variant.ref_allele == "T"
    assert fields.variant.alt_allele == "C"
    assert fields.experiment_data is not None
    assert fields.experiment_data.assay_type == "Caspase-3 activity measurements"
    assert fields.experiment_data.cell_line == "TSM1 neurons, SH-SY5Y cells"
    assert fields.negative_positive_control is not None
    assert fields.negative_positive_control.has_positive_control is True
    assert fields.negative_positive_control.has_negative_control is False


def test_convert_gold_standard_payload_populates_ps3_scoring() -> None:
    payload = json.loads((FIXTURES_DIR / "gold_standard_source_minimal.json").read_text())

    records = convert_gold_standard_payload(payload, source_id="14749723")

    ps3 = records[0]["ps3_evidence"]
    assert ps3["ps3_step_1"]["score"] == pytest.approx(20.0)
    assert ps3["ps3_step_2"]["score"] == pytest.approx(20.0)
    assert ps3["ps3_step_3"]["score"] == pytest.approx(15.0)
    assert ps3["ps3_step_4"]["score"] == pytest.approx(20.0)
    assert ps3["overall_assessment"]["total_score"] == pytest.approx(75.0)
    assert ps3["ps3_step_3"]["checkpoint_3a"]["replicates_used"] is True
    assert ps3["ps3_step_3"]["checkpoint_3a"]["positive_controls_present"] is True
    assert ps3["ps3_step_3"]["checkpoint_3a"]["negative_controls_present"] is False
    assert ps3["ps3_step_4"]["oddspath_data"]["computable"] is False
    assert ps3["ps3_step_4"]["oddspath_data"]["functional_evidence_aim"] == "pathogenic"
```

**Step 2: Run test to verify it fails**

Run from `apps/backend`:

```bash
uv run pytest tests/unit/test_gold_standard_converter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.domain.evidence.gold_standard_converter'`.

**Step 3: Commit**

Do not commit yet; failing tests and implementation should be committed together in Task 3.

---

### Task 3: Implement minimal converter for one readout row

**Files:**
- Create: `apps/backend/src/domain/evidence/gold_standard_converter.py`
- Test: `apps/backend/tests/unit/test_gold_standard_converter.py`

**Step 1: Write minimal implementation**

Create `apps/backend/src/domain/evidence/gold_standard_converter.py`:

```python
from __future__ import annotations

import re
from typing import Any

from src.domain.models import EvidenceOutput, ExtractedEvidenceFields


AA3 = {
    "A": "Ala",
    "R": "Arg",
    "N": "Asn",
    "D": "Asp",
    "C": "Cys",
    "Q": "Gln",
    "E": "Glu",
    "G": "Gly",
    "H": "His",
    "I": "Ile",
    "L": "Leu",
    "K": "Lys",
    "M": "Met",
    "F": "Phe",
    "P": "Pro",
    "S": "Ser",
    "T": "Thr",
    "W": "Trp",
    "Y": "Tyr",
    "V": "Val",
    "*": "Ter",
}


def is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "n.d.", "nd", "n/a", "na", "not determined", "unknown"}
    return False


def yes_no_to_bool(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() in {"yes", "true", "1", "present", "approved"}


def stringify(value: object) -> str | None:
    if is_missing(value):
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            text = stringify(item)
            if text:
                parts.append(f"{key}: {text}")
        return "; ".join(parts) if parts else None
    if isinstance(value, list):
        parts = [stringify(item) for item in value]
        present = [item for item in parts if item]
        return "; ".join(present) if present else None
    return str(value)


def normalize_variant_key(value: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", value.strip())


def protein_hgvs(change: dict[str, object] | None, fallback: str | None) -> str | None:
    if change:
        ref = stringify(change.get("ref"))
        alt = stringify(change.get("alt"))
        position = stringify(change.get("position"))
        if ref and alt and position:
            return f"p.{AA3.get(ref, ref)}{position}{AA3.get(alt, alt)}"
    if fallback and re.match(r"^[A-Z*]\d+[A-Z*]$", fallback):
        return f"p.{fallback}"
    return None


def convert_gold_standard_payload(payload: dict[str, Any], source_id: str | None = None) -> list[dict[str, Any]]:
    variant_lookup = _build_variant_lookup(payload)
    disease = _read_disease(payload)
    records: list[dict[str, Any]] = []

    for assay in payload.get("Experiment Method", []):
        if not isinstance(assay, dict):
            continue
        for readout in assay.get("Readout description", []):
            if not isinstance(readout, dict):
                continue
            records.append(_convert_readout(assay, readout, variant_lookup, disease, source_id))

    return records


def _build_variant_lookup(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for group in payload.get("Variants Include", []):
        if not isinstance(group, dict):
            continue
        gene = stringify(group.get("Gene"))
        for variant in group.get("variants", []):
            if not isinstance(variant, dict):
                continue
            hgvs = stringify(variant.get("HGVS"))
            if not hgvs:
                continue
            item = dict(variant)
            item["Gene"] = gene
            lookup[normalize_variant_key(hgvs)] = item
    return lookup


def _read_disease(payload: dict[str, Any]) -> str | None:
    disease = payload.get("Described Disease")
    if not isinstance(disease, dict):
        return None
    return stringify(disease.get("Described Disease"))


def _convert_readout(
    assay: dict[str, Any],
    readout: dict[str, Any],
    variant_lookup: dict[str, dict[str, Any]],
    disease: str | None,
    source_id: str | None,
) -> dict[str, Any]:
    variant_text = stringify(readout.get("Variant")) or ""
    normalized_variant = normalize_variant_key(variant_text)
    variant = variant_lookup.get(normalized_variant, {})

    extracted_fields = _build_extracted_fields(assay, readout, variant, normalized_variant, disease)
    fields_model = ExtractedEvidenceFields.model_validate(extracted_fields)
    field_scores = fields_model.compute_field_confidence_scores()
    ps3 = _build_ps3_evidence(assay, readout, disease)
    strength, classification, acmg_levels = _classify(ps3, readout)

    output = EvidenceOutput(
        ps3_evidence=ps3,
        arbitration_confidence=None,
        image_descriptions=[],
        evidence_sources=[f"PMID:{source_id}"] if source_id else [],
        final_evidence_strength=strength,
        status="success",
        origin_format_md=None,
        en_format_md=None,
        extracted_fields=fields_model.model_dump(mode="json", exclude_none=True),
        field_confidence_scores=field_scores,
        overall_confidence=fields_model.compute_overall_confidence(),
        evidence_classification=classification,
        acmg_evidence_levels=acmg_levels,
    )
    return output.model_dump(mode="json")


def _build_extracted_fields(
    assay: dict[str, Any],
    readout: dict[str, Any],
    variant: dict[str, Any],
    normalized_variant: str,
    disease: str | None,
) -> dict[str, Any]:
    material = assay.get("Material used") if isinstance(assay.get("Material used"), dict) else {}
    cdna = variant.get("cDNA Change") if isinstance(variant.get("cDNA Change"), dict) else {}
    protein = variant.get("Protein Change") if isinstance(variant.get("Protein Change"), dict) else {}
    gene = stringify(variant.get("Gene")) or "unknown"
    transcript = stringify(cdna.get("transcript")) or _transcript_from_hgvs(normalized_variant) or "unknown"
    result = stringify(readout.get("Result Description"))
    material_source = stringify(material.get("Material Source")) or ""
    material_name = stringify(material.get("Material Name"))
    material_description = stringify(material.get("Description"))
    statistical_method = assay.get("Statistical analysis method")
    statistical_text = None
    if isinstance(statistical_method, dict):
        statistical_text = stringify(statistical_method.get("Statistical analysis method"))

    return {
        "gene": {"symbol": gene, "confidence": 100.0 if gene != "unknown" else 0.0},
        "transcript_id": {"transcript_id": transcript, "confidence": 100.0 if transcript != "unknown" else 0.0},
        "reference_genome_version": {"version": "unknown", "confidence": 0.0},
        "experiment_data": {
            "assay_type": stringify(assay.get("Assay Method")) or "unknown",
            "method_description": material_description,
            "key_findings": [result] if result else None,
            "statistical_data": {
                "readout_type": stringify(assay.get("Readout type")),
                "statistical_analysis_method": statistical_text,
            },
            "cell_line": material_name if "cell" in material_source.lower() else None,
            "model_organism": material_name if "cell" not in material_source.lower() else None,
            "confidence": 100.0,
        },
        "disease_chpo": {"disease_name": disease or "unknown", "confidence": 100.0 if disease else 0.0},
        "disease_icd10": {"disease_name": disease or "unknown", "confidence": 100.0 if disease else 0.0},
        "species": {"species_name": "Homo sapiens", "is_human": True, "confidence": 50.0},
        "phenotype": {"phenotype_description": disease or result or "unknown", "confidence": 80.0 if disease or result else 0.0},
        "variant": {
            "hgvs_c": normalized_variant or None,
            "hgvs_p": protein_hgvs(protein, stringify(variant.get("Description in input context"))),
            "ref_allele": stringify(cdna.get("ref")),
            "alt_allele": stringify(cdna.get("alt")),
            "variant_type": "missense" if protein else None,
            "confidence": 100.0 if normalized_variant else 0.0,
        },
        "negative_positive_control": _build_control_info(assay),
        "pedigree_information": {"has_pedigree": False, "confidence": 0.0},
    }


def _transcript_from_hgvs(hgvs: str) -> str | None:
    if ":" not in hgvs:
        return None
    return hgvs.split(":", 1)[0]


def _build_control_info(assay: dict[str, Any]) -> dict[str, Any]:
    positive = assay.get("Basic positive control") if isinstance(assay.get("Basic positive control"), dict) else {}
    negative = assay.get("Basic negative control") if isinstance(assay.get("Basic negative control"), dict) else {}
    has_positive = yes_no_to_bool(positive.get("Basic positive control"))
    has_negative = yes_no_to_bool(negative.get("Basic negative control"))
    return {
        "has_negative_control": has_negative,
        "has_positive_control": has_positive,
        "negative_control_description": stringify(negative.get("Description")),
        "positive_control_description": stringify(positive.get("Description")),
        "control_variants": None,
        "total_control_count": 0,
        "confidence": 100.0,
    }


def _build_ps3_evidence(assay: dict[str, Any], readout: dict[str, Any], disease: str | None) -> dict[str, Any]:
    approved = assay.get("Approved assay") if isinstance(assay.get("Approved assay"), dict) else {}
    biological = assay.get("Biological replicates") if isinstance(assay.get("Biological replicates"), dict) else {}
    technical = assay.get("Technical replicates") if isinstance(assay.get("Technical replicates"), dict) else {}
    controls = _build_control_info(assay)
    replicates_used = yes_no_to_bool(biological.get("Biological replicates")) or yes_no_to_bool(
        technical.get("Technical replicates")
    )
    positive_controls = bool(controls["has_positive_control"])
    negative_controls = bool(controls["has_negative_control"])
    step3_score = _score_step3(positive_controls, negative_controls, replicates_used)
    step4_score = 0.0 if is_missing(readout.get("Conclusion")) else 20.0
    total = min(100.0, 20.0 + (20.0 if yes_no_to_bool(approved.get("Approved assay")) else 0.0) + step3_score + step4_score)

    return {
        "ps3_step_1": {
            "score": 20.0 if disease else 0.0,
            "summary": "Disease mechanism annotated in benchmark." if disease else "Disease missing.",
        },
        "ps3_step_2": {
            "score": 20.0 if yes_no_to_bool(approved.get("Approved assay")) else 0.0,
            "summary": f"Approved assay: {stringify(approved.get('Approved assay')) or 'unknown'}.",
            "assay_suitable": stringify(approved.get("Approved assay")) or "unknown",
        },
        "ps3_step_3": {
            "score": step3_score,
            "summary": "Controls and replicates converted from benchmark annotations.",
            "checkpoint_3a": {
                "basic_controls_present": positive_controls and negative_controls,
                "positive_controls_present": positive_controls,
                "negative_controls_present": negative_controls,
                "replicates_used": replicates_used,
            },
        },
        "ps3_step_4": {
            "score": step4_score,
            "final_evidence_strength": None,
            "oddspath_data": {
                "computable": False,
                "functional_evidence_aim": _evidence_direction(readout),
            },
            "control_count_data": {
                "pathogenic_count": _safe_int_from_controls(assay, "Validation controls P/LP", "Counts"),
                "benign_count": _safe_int_from_controls(assay, "Validation controls B/LB", "Counts"),
            },
        },
        "overall_assessment": {
            "total_score": total,
            "reasoning": "Deterministic conversion from gold-standard benchmark annotations.",
        },
    }


def _score_step3(positive_controls: bool, negative_controls: bool, replicates_used: bool) -> float:
    if positive_controls and negative_controls and replicates_used:
        return 20.0
    if positive_controls and replicates_used:
        return 15.0
    if positive_controls or negative_controls:
        return 10.0
    return 0.0


def _safe_int_from_controls(assay: dict[str, Any], key: str, count_key: str) -> int:
    section = assay.get(key) if isinstance(assay.get(key), dict) else {}
    value = section.get(count_key)
    if is_missing(value):
        return 0
    try:
        return int(str(value))
    except ValueError:
        return 0


def _evidence_direction(readout: dict[str, Any]) -> str:
    text = " ".join(
        part
        for part in [
            stringify(readout.get("Conclusion")),
            stringify(readout.get("Molecular Effect")),
            stringify(readout.get("Result Description")),
        ]
        if part
    ).lower()
    if "normal" in text and "abnormal" not in text:
        return "benign"
    if "loss" in text or "abnormal" in text or "impaired" in text or "reduced" in text:
        return "pathogenic"
    return "pathogenic"


def _classify(ps3: dict[str, Any], readout: dict[str, Any]) -> tuple[str, str, list[str]]:
    if is_missing(readout.get("Conclusion")):
        ps3["ps3_step_4"]["final_evidence_strength"] = "Inconclusive"
        return "Inconclusive", "Uncertain Significance", []

    total = float(ps3["overall_assessment"]["total_score"])
    direction = ps3["ps3_step_4"]["oddspath_data"]["functional_evidence_aim"]
    if direction == "benign":
        if total >= 70:
            strength, classification, levels = "BS3", "Benign", ["BS3"]
        elif total >= 50:
            strength, classification, levels = "BS3_moderate", "Likely Benign", ["BS2"]
        else:
            strength, classification, levels = "BS3_supporting", "Likely Benign", ["BP4"]
    else:
        if total >= 70:
            strength, classification, levels = "PS3", "Pathogenic", ["PS3"]
        elif total >= 50:
            strength, classification, levels = "PS3_moderate", "Likely Pathogenic", ["PM1"]
        else:
            strength, classification, levels = "PS3_supporting", "Likely Pathogenic", ["PP3"]

    ps3["ps3_step_4"]["final_evidence_strength"] = strength
    return strength, classification, levels
```

**Step 2: Run tests**

Run from `apps/backend`:

```bash
uv run pytest tests/unit/test_gold_standard_converter.py -v
```

Expected: the two new tests pass.

**Step 3: Adjust expected strength if needed**

The scoring rules above produce total score `75.0` for the minimal fixture, so expected final strength should be `PS3`, not `PS3_supporting`. If implementing exactly as written, update the first test assertions to:

```python
assert output.final_evidence_strength == "PS3"
assert output.acmg_evidence_levels == ["PS3"]
assert output.evidence_classification == "Pathogenic"
```

This adjustment keeps tests aligned with the scoring rules. Prefer this over changing converter behavior.

**Step 4: Run focused existing validation**

Run from `apps/backend`:

```bash
uv run pytest tests/test_golden_fixtures.py::TestGoldenFixtures::test_evidence_output_validates tests/unit/test_domain_evidence.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/backend/src/domain/evidence/gold_standard_converter.py apps/backend/tests/unit/test_gold_standard_converter.py apps/backend/tests/fixtures/gold_standard_source_minimal.json
git commit -m "feat: convert gold standard annotations to evidence output"
```

---

### Task 4: Add edge-case tests for benchmark quirks

**Files:**
- Modify: `apps/backend/tests/unit/test_gold_standard_converter.py`
- Test data source: `benchmark/Gold-Standard-Json/19801972.json`

**Step 1: Add tests**

Append to `apps/backend/tests/unit/test_gold_standard_converter.py`:

```python
def test_convert_gold_standard_payload_matches_parenthetical_variant_suffix() -> None:
    payload = {
        "Variants Include": [
            {
                "Gene": "DJ-1",
                "variants": [
                    {
                        "HGVS": "NM_007262.5:c.497T>C",
                        "cDNA Change": {"transcript": "NM_007262.5", "ref": "T", "alt": "C", "position": "497"},
                        "Protein Change": {"ref": "L", "alt": "P", "position": "166"},
                        "Description in input context": "L166P",
                    }
                ],
            }
        ],
        "Described Disease": {"Described Disease": "Parkinson's disease", "MONDO": "MONDO:0005180"},
        "Experiment Method": [
            {
                "Assay Method": "Flow Cytometry",
                "Material used": {"Material Source": "Cell line", "Material Name": "SH-SY5Y cells", "Description": "ROS assay"},
                "Readout type": "Quantitative",
                "Readout description": [
                    {
                        "Variant": "NM_007262.5:c.497T>C (L166P)",
                        "Conclusion": "Abnormal",
                        "Molecular Effect": "complete loss-of-function",
                        "Result Description": "Higher ROS",
                    }
                ],
                "Biological replicates": {"Biological replicates": "Yes", "Description": "replicates"},
                "Technical replicates": {"Technical replicates": "N.D.", "Description": "N.D."},
                "Basic positive control": {"Basic positive control": "Yes", "Description": "Wild-type DJ-1"},
                "Basic negative control": {
                    "Basic negative control": "Yes",
                    "Description": {"Control vector-transfected cells": "Negative control for DJ-1 expression."},
                },
                "Validation controls P/LP": {"Validation controls P/LP": "N.D.", "Counts": "N.D."},
                "Validation controls B/LB": {"Validation controls B/LB": "N.D.", "Counts": "N.D."},
                "Statistical analysis method": {"Statistical analysis method": "N.D."},
                "Threshold for normal readout": {"Threshold for normal readout": "N.D.", "Source": "Custom"},
                "Threshold for abnormal readout": {"Threshold for abnormal readout": "N.D.", "Source": "Custom"},
                "Approved assay": {"Approved assay": "Yes"},
            }
        ],
    }

    records = convert_gold_standard_payload(payload, source_id="19801972")

    fields = ExtractedEvidenceFields.model_validate(records[0]["extracted_fields"])
    assert fields.variant is not None
    assert fields.variant.hgvs_c == "NM_007262.5:c.497T>C"
    assert fields.variant.hgvs_p == "p.Leu166Pro"
    assert fields.negative_positive_control is not None
    assert fields.negative_positive_control.has_negative_control is True
    assert fields.negative_positive_control.negative_control_description == "Control vector-transfected cells: Negative control for DJ-1 expression."


def test_convert_gold_standard_payload_emits_partial_variant_when_missing_from_variant_list() -> None:
    payload = json.loads((FIXTURES_DIR / "gold_standard_source_minimal.json").read_text())
    payload["Experiment Method"][0]["Readout description"][0]["Variant"] = "NM_007262.5:c.155G>C (C53A)"

    records = convert_gold_standard_payload(payload, source_id="19801972")

    fields = ExtractedEvidenceFields.model_validate(records[0]["extracted_fields"])
    assert fields.variant is not None
    assert fields.variant.hgvs_c == "NM_007262.5:c.155G>C"
    assert fields.transcript_id is not None
    assert fields.transcript_id.transcript_id == "NM_007262.5"
    assert fields.variant.hgvs_p is None
```

**Step 2: Run tests**

Run from `apps/backend`:

```bash
uv run pytest tests/unit/test_gold_standard_converter.py -v
```

Expected: PASS. If not, minimally update helper behavior without broad refactoring.

**Step 3: Commit**

```bash
git add apps/backend/src/domain/evidence/gold_standard_converter.py apps/backend/tests/unit/test_gold_standard_converter.py
git commit -m "test: cover gold standard converter edge cases"
```

---

### Task 5: Add batch conversion CLI script

**Files:**
- Create: `apps/backend/scripts/convert_gold_standard_json.py`
- Modify: `apps/backend/tests/unit/test_gold_standard_converter.py`

**Step 1: Write failing CLI test**

Append to `apps/backend/tests/unit/test_gold_standard_converter.py`:

```python
def test_convert_gold_standard_file_writes_evidence_json(tmp_path: Path) -> None:
    from apps.backend.scripts.convert_gold_standard_json import convert_file

    source = FIXTURES_DIR / "gold_standard_source_minimal.json"
    target = tmp_path / "14749723.evidence.json"

    count = convert_file(source, target, source_id="14749723")

    assert count == 1
    data = json.loads(target.read_text())
    assert isinstance(data, list)
    assert len(data) == 1
    EvidenceOutput.model_validate(data[0])
```

Note: If importing via `apps.backend.scripts...` fails because `apps` is not a package in this repo, use `importlib.util.spec_from_file_location` in the test instead of package import. Do not add package `__init__.py` files solely for this script.

**Step 2: Run test to verify it fails**

Run from repository root:

```bash
uv --directory apps/backend run pytest tests/unit/test_gold_standard_converter.py::test_convert_gold_standard_file_writes_evidence_json -v
```

Expected: FAIL because `apps/backend/scripts/convert_gold_standard_json.py` does not exist.

**Step 3: Implement CLI script**

Create `apps/backend/scripts/convert_gold_standard_json.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from src.domain.evidence.gold_standard_converter import convert_gold_standard_payload
from src.domain.models import EvidenceOutput


def convert_file(source_path: Path, target_path: Path, source_id: str | None = None) -> int:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    records = convert_gold_standard_payload(payload, source_id=source_id or source_path.stem)
    validated = [EvidenceOutput.model_validate(record).model_dump(mode="json") for record in records]
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(validated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(validated)


def convert_directory(source_dir: Path, target_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source_path in sorted(source_dir.glob("*.json")):
        target_path = target_dir / f"{source_path.stem}.evidence.json"
        counts[source_path.name] = convert_file(source_path, target_path, source_id=source_path.stem)
    return counts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert benchmark gold-standard JSON to EvidenceOutput JSON.")
    parser.add_argument("source", type=Path, help="Source JSON file or directory")
    parser.add_argument("target", type=Path, help="Target JSON file or directory")
    args = parser.parse_args(argv)

    if args.source.is_dir():
        counts = convert_directory(args.source, args.target)
        for name, count in counts.items():
            print(f"{name}: {count}")
        return 0

    count = convert_file(args.source, args.target, source_id=args.source.stem)
    print(f"{args.source.name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 4: Run CLI test**

Run from repository root:

```bash
uv --directory apps/backend run pytest tests/unit/test_gold_standard_converter.py::test_convert_gold_standard_file_writes_evidence_json -v
```

Expected: PASS.

**Step 5: Run full converter tests**

Run from repository root:

```bash
uv --directory apps/backend run pytest tests/unit/test_gold_standard_converter.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add apps/backend/scripts/convert_gold_standard_json.py apps/backend/tests/unit/test_gold_standard_converter.py
git commit -m "feat: add gold standard conversion script"
```

---

### Task 6: Validate converter on real benchmark directory

**Files:**
- Generated: `benchmark/evidence-json/*.evidence.json`

**Step 1: Run conversion**

Run from repository root:

```bash
uv --directory apps/backend run python scripts/convert_gold_standard_json.py ../../benchmark/Gold-Standard-Json ../../benchmark/evidence-json
```

Expected: prints one line per input file with record counts, e.g.:

```text
14749723.json: 12
19801972.json: 19
...
```

**Step 2: Validate generated files parse as `EvidenceOutput`**

Run from repository root:

```bash
uv --directory apps/backend run python - <<'PY'
import json
from pathlib import Path
from src.domain.models import EvidenceOutput

root = Path('../../benchmark/evidence-json')
files = sorted(root.glob('*.evidence.json'))
assert files, 'no converted evidence files found'
count = 0
for path in files:
    records = json.loads(path.read_text())
    assert isinstance(records, list), path
    for record in records:
        EvidenceOutput.model_validate(record)
        count += 1
print(f'validated {count} EvidenceOutput records from {len(files)} files')
PY
```

Expected: prints validation count and exits 0.

**Step 3: Check a representative output**

Run from repository root:

```bash
python -m json.tool benchmark/evidence-json/14749723.evidence.json | sed -n '1,160p'
```

Expected: first output record has:

- `evidence_sources: ["PMID:14749723"]`
- `extracted_fields.gene.symbol: "PRKN"`
- `extracted_fields.variant.hgvs_c: "NM_004562.3:c.1252T>C"`
- `extracted_fields.experiment_data.assay_type: "Caspase-3 activity measurements"`
- `status: "success"`

**Step 4: Decide whether to commit generated benchmark outputs**

Ask the user before committing generated `benchmark/evidence-json/*.evidence.json` files because there may be many files. If the user wants them versioned, commit them:

```bash
git add benchmark/evidence-json
git commit -m "data: add converted benchmark evidence outputs"
```

If the user does not want generated files committed, add only source/test/script changes in prior commits and leave generated files untracked or delete them after validation only if explicitly requested.

---

### Task 7: Run regression tests and lint checks

**Files:**
- No source changes expected unless tests expose issues.

**Step 1: Run focused regression tests**

Run from repository root:

```bash
uv --directory apps/backend run pytest tests/unit/test_gold_standard_converter.py tests/test_golden_fixtures.py tests/unit/test_domain_evidence.py -v
```

Expected: PASS.

**Step 2: Run formatter/linter if configured**

Run from repository root:

```bash
uv --directory apps/backend run ruff check src/domain/evidence/gold_standard_converter.py scripts/convert_gold_standard_json.py tests/unit/test_gold_standard_converter.py
```

Expected: PASS. If it reports auto-fixable issues, run:

```bash
uv --directory apps/backend run ruff check --fix src/domain/evidence/gold_standard_converter.py scripts/convert_gold_standard_json.py tests/unit/test_gold_standard_converter.py
```

Then rerun the non-fix command.

**Step 3: Commit lint fixes if any**

```bash
git add apps/backend/src/domain/evidence/gold_standard_converter.py apps/backend/scripts/convert_gold_standard_json.py apps/backend/tests/unit/test_gold_standard_converter.py
git commit -m "chore: satisfy converter lint checks"
```

Skip this commit if no files changed.

---

## Notes for Implementer

- Do not modify `EvidenceOutput` or `ExtractedEvidenceFields` unless validation proves the existing schema cannot represent the benchmark data.
- Do not call LLMs or external APIs; this is a deterministic format conversion.
- Do not invent reference genome, ICD-10, CHPO, ClinVar, or rsID values. Use `unknown`/`None` with low confidence instead.
- Keep conversion conservative. It is acceptable for `final_evidence_strength` to be weaker than a future adjudicated score; the goal is schema conversion, not scientific re-adjudication.
- Generated benchmark outputs may be large; ask before committing them.
