from __future__ import annotations

import re
from typing import Any

from src.domain.models import EvidenceOutput, ExtractedEvidenceFields

_MISSING_VALUES = {"", "n.d.", "nd", "n/a", "na", "not determined", "unknown"}
_AA3 = {
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


def convert_gold_standard_payload(
    payload: dict[str, Any], source_id: str | None = None
) -> list[dict[str, Any]]:
    """Convert gold standard annotation JSON into EvidenceOutput-compatible dicts."""
    variants = _build_variant_lookup(payload)
    records: list[dict[str, Any]] = []

    for method in payload.get("Experiment Method") or []:
        if not isinstance(method, dict):
            continue
        for readout in method.get("Readout description") or []:
            if not isinstance(readout, dict):
                continue
            records.append(_convert_readout(payload, method, readout, variants, source_id))

    return records


def _convert_readout(
    payload: dict[str, Any],
    method: dict[str, Any],
    readout: dict[str, Any],
    variants: dict[str, dict[str, Any]],
    source_id: str | None,
) -> dict[str, Any]:
    readout_variant_key = _variant_key(readout.get("Variant"))
    variant = variants.get(readout_variant_key, {})
    transcript = (variant.get("cDNA Change") or {}).get("transcript") or _transcript_from_hgvs(readout_variant_key)
    ps3_evidence = _build_ps3_evidence(payload, method, readout)
    strength = _strength_from_score(ps3_evidence["overall_assessment"]["total_score"])

    extracted = ExtractedEvidenceFields.model_validate(
        {
            "gene": {"symbol": variant.get("Gene"), "confidence": 100.0}
            if not _is_missing(variant.get("Gene"))
            else None,
            "transcript_id": {
                "transcript_id": transcript,
                "confidence": 100.0,
            }
            if not _is_missing(transcript)
            else None,
            "experiment_data": {
                "assay_type": method.get("Assay Method"),
                "method_description": (method.get("Material used") or {}).get("Description"),
                "cell_line": (method.get("Material used") or {}).get("Material Name"),
                "confidence": 100.0,
            },
            "disease_chpo": {
                "disease_name": (payload.get("Described Disease") or {}).get("Described Disease"),
                "confidence": 100.0,
            }
            if not _is_missing((payload.get("Described Disease") or {}).get("Described Disease"))
            else None,
            "species": {"species_name": "Homo sapiens", "is_human": True, "confidence": 100.0},
            "phenotype": {
                "phenotype_description": readout.get("Conclusion"),
                "confidence": 100.0,
            }
            if not _is_missing(readout.get("Conclusion"))
            else None,
            "variant": {
                "hgvs_c": variant.get("HGVS") or readout_variant_key,
                "hgvs_p": _hgvs_p(variant),
                "ref_allele": (variant.get("cDNA Change") or {}).get("ref"),
                "alt_allele": (variant.get("cDNA Change") or {}).get("alt"),
                "confidence": 100.0,
            },
            "negative_positive_control": {
                "has_positive_control": _is_yes(
                    (method.get("Basic positive control") or {}).get("Basic positive control")
                ),
                "has_negative_control": _is_yes(
                    (method.get("Basic negative control") or {}).get("Basic negative control")
                ),
                "positive_control_description": _control_description(
                    (method.get("Basic positive control") or {}).get("Description")
                ),
                "negative_control_description": _control_description(
                    (method.get("Basic negative control") or {}).get("Description")
                ),
                "confidence": 100.0,
            },
        }
    )

    output = EvidenceOutput.model_validate(
        {
            "ps3_evidence": ps3_evidence,
            "evidence_sources": [f"PMID:{source_id}"] if source_id else [],
            "final_evidence_strength": strength,
            "status": "success",
            "extracted_fields": extracted.model_dump(mode="json"),
            "field_confidence_scores": extracted.compute_field_confidence_scores(),
            "overall_confidence": extracted.compute_overall_confidence(),
            "evidence_classification": "Pathogenic" if strength.startswith("PS3") else None,
            "acmg_evidence_levels": [strength] if strength else [],
        }
    )
    return output.model_dump(mode="json")


def _build_variant_lookup(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for group in payload.get("Variants Include") or []:
        if not isinstance(group, dict):
            continue
        gene = group.get("Gene")
        for variant in group.get("variants") or []:
            if not isinstance(variant, dict):
                continue
            enriched = {**variant, "Gene": gene}
            for key in (variant.get("HGVS"), variant.get("Description in input context")):
                normalized = _variant_key(key)
                if normalized:
                    lookup[normalized] = enriched
    return lookup


def _build_ps3_evidence(
    payload: dict[str, Any], method: dict[str, Any], readout: dict[str, Any]
) -> dict[str, Any]:
    disease_present = not _is_missing((payload.get("Described Disease") or {}).get("Described Disease"))
    approved = _is_yes((method.get("Approved assay") or {}).get("Approved assay"))
    positive = _is_yes((method.get("Basic positive control") or {}).get("Basic positive control"))
    negative = _is_yes((method.get("Basic negative control") or {}).get("Basic negative control"))
    replicate = _is_yes((method.get("Biological replicates") or {}).get("Biological replicates")) or _is_yes(
        (method.get("Technical replicates") or {}).get("Technical replicates")
    )
    conclusion_present = not _is_missing(readout.get("Conclusion"))

    step1 = 20 if disease_present else 0
    step2 = 20 if approved else 0
    step3 = 20 if positive and negative and replicate else 15 if positive and replicate else 10 if positive or negative else 0
    step4 = 20 if conclusion_present else 0
    total = min(100, step1 + step2 + step3 + step4)

    return {
        "functional_evidence_aim": _functional_evidence_aim(readout),
        "ps3_step_1": {"score": step1},
        "ps3_step_2": {"score": step2},
        "ps3_step_3": {
            "score": step3,
            "checkpoint_3a": {
                "replicates_used": replicate,
                "positive_control_present": positive,
                "negative_control_present": negative,
            },
        },
        "ps3_step_4": {
            "score": step4,
            "final_evidence_strength": _strength_from_score(total),
            "oddspath_data": {"computable": False},
        },
        "overall_assessment": {"total_score": total},
    }


def _functional_evidence_aim(readout: dict[str, Any]) -> str | None:
    text = " ".join(
        str(value).lower()
        for value in (readout.get("Conclusion"), readout.get("Molecular Effect"), readout.get("Result Description"))
        if value is not None
    )
    return "pathogenic" if any(term in text for term in ("abnormal", "loss", "impaired", "reduced")) else None


def _strength_from_score(score: int) -> str:
    return "PS3" if score >= 75 else "PS3_moderate" if score >= 60 else "PS3_supporting"


def _variant_key(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+\([^)]*\)\s*$", "", str(value).strip())


def _transcript_from_hgvs(value: str) -> str | None:
    match = re.match(r"^([^:]+):", value)
    return match[1] if match else None


def _hgvs_p(variant: dict[str, Any]) -> str | None:
    protein = variant.get("Protein Change") or {}
    ref = protein.get("ref")
    alt = protein.get("alt")
    position = protein.get("position")
    if not _is_missing(ref) and not _is_missing(alt) and not _is_missing(position):
        return f"p.{_AA3.get(str(ref), str(ref))}{position}{_AA3.get(str(alt), str(alt))}"

    description = variant.get("Description in input context")
    match = re.fullmatch(r"([A-Z*])(\d+)([A-Z*])", str(description or "").strip())
    if match:
        return f"p.{_AA3.get(match[1], match[1])}{match[2]}{_AA3.get(match[3], match[3])}"
    return None


def _is_missing(value: Any) -> bool:
    return value is None or str(value).strip().lower() in _MISSING_VALUES


def _none_if_missing(value: Any) -> Any:
    return None if _is_missing(value) else value


def _control_description(value: Any) -> str | None:
    if _is_missing(value):
        return None
    if isinstance(value, dict):
        return "; ".join(f"{key}: {description}" for key, description in value.items())
    return str(value)


def _is_yes(value: Any) -> bool:
    return str(value or "").strip().lower() == "yes"
