"""Utility helpers for the Rett annotation tool."""
from __future__ import annotations

import re

MECP2_HGNC_ID = "HGNC:6992"
RETT_MONDO_ID = "MONDO:0010726"

COMMON_MEC2_VARIANTS_P: list[str] = [
    "p.R255X", "p.Arg255*", "p.Arg255Ter",
    "p.R270X", "p.Arg270*", "p.Arg270Ter",
    "p.R306C", "p.Arg306Cys",
    "p.R168X", "p.Arg168*", "p.Arg168Ter",
    "p.T158M", "p.Thr158Met",
    "p.R133C", "p.Arg133Cys",
    "p.R294X", "p.Arg294*", "p.Arg294Ter",
    "p.R306H", "p.Arg306His",
]

MECP2_DOMAINS = {
    "MBD": "methyl-CpG binding domain",
    "TRD": "transcription repression domain",
    "NCoR/SMRT": "NCoR/SMRT interaction domain",
    "NLS": "nuclear localization signal",
}

RETT_HPO_TERMS: dict[str, str] = {
    "HP:0002194": "Delayed gross motor development",
    "HP:0001250": "Seizures",
    "HP:0001263": "Global developmental delay",
    "HP:0002072": "Hand stereotypies",
    "HP:0012759": "Abnormality of respiratory system",
    "HP:0000252": "Microcephaly",
    "HP:0001249": "Intellectual disability",
    "HP:0000756": "Autistic behavior",
    "HP:0001252": "Hypotonia",
    "HP:0001257": "Spasticity",
    "HP:0001371": "Flexion contracture",
    "HP:0000253": "Progressive microcephaly",
    "HP:0002376": "Developmental regression",
    "HP:0012758": "Neurodevelopmental delay",
    "HP:0001272": "Cerebellar atrophy",
    "HP:0000505": "Visual impairment",
    "HP:0000729": "Autistic behavior",
    "HP:0002069": "Generalized tonic-clonic seizures",
    "HP:0002098": "Respiratory distress",
    "HP:0002144": "Gait ataxia",
    "HP:0004322": "Short stature",
    "HP:0000568": "Strabismus",
    "HP:0002270": "Horripilatio / piloerection",
    "HP:0001251": "Ataxia",
    "HP:0010818": "Tonic seizures",
    "HP:0001382": "Joint hypermobility",
    "HP:0001290": "Generalized hypotonia",
    "HP:0000365": "Hearing impairment",
    "HP:0001339": "Limb ataxia",
    "HP:0012768": "Scoliosis",
    "HP:0000407": "Sensorineural hearing impairment",
    "HP:0001631": "Atrial septal defect",
    "HP:0000982": "Palmoplantar keratoderma",
}


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text


def normalize_hgvs(hgvs: str) -> str:
    hgvs = hgvs.strip()
    hgvs = re.sub(r"\s+", "", hgvs)
    return hgvs


def classify_variant_type(hgvs_c: str = "", hgvs_p: str = "") -> str:
    """Infer variant type from HGVS notation."""
    combined = f"{hgvs_c} {hgvs_p}".lower()
    if any(t in combined for t in ["del", "delins"]):
        return "deletion"
    if "dup" in combined or "ins" in combined:
        return "insertion" if "ins" in combined and "delins" not in combined else "duplication"
    if any(t in combined for t in ["*", "ter", "x"]):
        if re.search(r"[pr]\.\w+\d+[\*xtX]", combined):
            return "nonsense"
    if re.search(r"p\.\w+\d+\w+", combined) and "del" not in combined and "ins" not in combined:
        return "missense"
    if "fs" in combined or "frameshift" in combined:
        return "frameshift"
    if "splice" in combined or re.search(r"[+-]\d", hgvs_c):
        return "splice"
    return "other"


def infer_domain(hgvs_p: str) -> str:
    """Infer MECP2 protein domain from amino acid position."""
    match = re.search(r"(\d+)", hgvs_p)
    if not match:
        return ""
    pos = int(match.group(1))
    if 78 <= pos <= 162:
        return "MBD"
    if 201 <= pos <= 310:
        return "TRD"
    if 310 < pos <= 400:
        return "NCoR/SMRT"
    if pos > 400:
        return "NLS"
    return ""
