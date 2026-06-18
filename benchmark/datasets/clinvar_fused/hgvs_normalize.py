"""HGVS normalization utilities for benchmark variant matching.

Handles common format variations found in literature vs ClinVar:
- Transcript prefix removal (NM_xxxxx.x(...):)
- Three-letter to one-letter amino acid conversion
- Stop codon normalization (Ter/X/*/stop -> *)
- Whitespace and case normalization
"""
from __future__ import annotations

import re
import unicodedata

# Three-letter to one-letter amino acid mapping
_AA_3_TO_1: dict[str, str] = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C",
    "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
    "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P",
    "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
    "Sec": "U", "Pyl": "O",
}

_AA_1_TO_3: dict[str, str] = {v: k for k, v in _AA_3_TO_1.items()}

# Regex for three-letter amino acid codes in protein HGVS
_RE_3LETTER_AA = re.compile(
    r"(?<![A-Za-z])" + "|".join(_AA_3_TO_1.keys()) + r"(?=[0-9*X])",
    re.IGNORECASE,
)

# Transcript prefix pattern: NM_000001.1(GENE): or NP_000001.1(GENE):
# Also handles bare NP_000001.1:p. format (no gene name in parens)
_RE_TRANSCRIPT_PREFIX = re.compile(
    r"^(?:NM|NP|NC|NR|XM|XP|XR)_[0-9]+\.[0-9]+(?:\([^)]*\))?\s*:\s*"
)

# Genomic transcript prefix: NC_000001.10:
_RE_GENOMIC_PREFIX = re.compile(
    r"^NC_[0-9]+\.[0-9]+\s*:\s*"
)

# Stop codon variants
_RE_STOP_VARIANTS = re.compile(r"\b(?:Ter|X|stop)\b", re.IGNORECASE)

# FS termination: p.Gln1756ProfsTer74 or p.Q1756Pfs*74 or fsX74
_RE_FS_PATTERN = re.compile(
    r"fs(?:Ter|X|stop|\*)\d*", re.IGNORECASE,
)

# Delins normalization
_RE_DELINS = re.compile(r"delins", re.IGNORECASE)

# Whitespace around operators
_RE_OPERATOR_SPACE = re.compile(r"\s*(dup|del|ins|inv|>|=)\s*")


def normalize_hgvs_c(hgvs: str) -> str:
    """Normalize HGVS coding variant notation.

    Rules:
    - Remove transcript prefix NM_xxxxx.x(...):
    - Remove whitespace
    - Unicode NFKC normalization
    - Normalize delins/del/ins/dup case
    - Keep c. prefix
    """
    if not hgvs:
        return ""
    text = unicodedata.normalize("NFKC", hgvs.strip())
    text = _RE_TRANSCRIPT_PREFIX.sub("", text)
    text = _RE_GENOMIC_PREFIX.sub("", text)
    text = text.strip()
    # Normalize delins case
    text = _RE_DELINS.sub("delins", text)
    # Remove spaces around operators but keep the operator
    text = _RE_OPERATOR_SPACE.sub(lambda m: m.group(1), text)
    # Remove remaining whitespace
    text = re.sub(r"\s+", "", text)
    return text


def normalize_hgvs_p(hgvs: str) -> str:
    """Normalize HGVS protein variant notation.

    Rules:
    - Remove transcript prefix NP_xxxxx.x(...):
    - Three-letter amino acid codes -> one-letter
    - Normalize stop codons: Ter/X/stop -> *
    - fsTerXX -> fs*XX
    - Remove whitespace
    """
    if not hgvs:
        return ""
    text = unicodedata.normalize("NFKC", hgvs.strip())
    text = _RE_TRANSCRIPT_PREFIX.sub("", text)
    text = text.strip()

    # Three-letter to one-letter conversion
    # Must be done carefully: only convert when followed by a digit, X, or *
    def _replace_3letter(m: re.Match) -> str:
        code = m.group(0)
        return _AA_3_TO_1[code[0].upper() + code[1:].lower()]

    text = _RE_3LETTER_AA.sub(_replace_3letter, text)

    # Normalize fsTer/fsX/fsstop/fs*NN -> fs*
    text = _RE_FS_PATTERN.sub("fs*", text)

    # Normalize stop codons after amino acid position: Ter/X/stop -> *
    # e.g. p.R227Ter -> p.R227*, p.R227X -> p.R227*
    text = re.sub(r"(?<=[0-9])Ter\b", "*", text)
    text = re.sub(r"(?<=[0-9])X\b", "*", text)
    text = re.sub(r"(?<=[0-9])stop\b", "*", text)
    # Remove position after *fs* (already handled by _RE_FS_PATTERN)
    text = re.sub(r"\*(\d+)$", "*", text)

    # Remove spaces
    text = re.sub(r"\s+", "", text)
    return text


def normalize_variant_type(vt: str) -> str:
    """Normalize variant type to standard enum values.

    Maps ClinVar Type values and literature descriptions to the
    pipeline's A.variant_type enum.
    """
    if not vt:
        return ""
    vt_lower = vt.strip().lower()
    mapping = {
        "single nucleotide variant": "missense",
        "snv": "missense",
        "snp": "missense",
        "missense": "missense",
        "nonsense": "nonsense",
        "stop gained": "nonsense",
        "frameshift": "frameshift",
        "frameshift variant": "frameshift",
        "splice site": "splice_site",
        "splice donor": "splice_site",
        "splice acceptor": "splice_site",
        "splice region": "splice_site",
        "splice_region_variant": "splice_site",
        "splice_donor_variant": "splice_site",
        "splice_acceptor_variant": "splice_site",
        "deletion": "deletion",
        "insertion": "insertion",
        "dup": "dup",
        "duplication": "dup",
        "indel": "deletion",  # ClinVar Indel -> closest match
        "delins": "deletion",
        "copy number loss": "cnv",
        "copy number gain": "cnv",
        "cnv": "cnv",
        "inversion": "other",
        "synonymous": "synonymous",
        "synonymous variant": "synonymous",
        "intron variant": "other",
        "intronic": "other",
    }
    # Direct match
    if vt_lower in mapping:
        return mapping[vt_lower]
    # Partial match
    for key, val in mapping.items():
        if key in vt_lower:
            return val
    return "other"


def normalize_hgvs_for_matching(hgvs: str, field_id: str) -> str:
    """Dispatch to the correct normalizer based on field_id."""
    if field_id == "A.variant_hgvs_c":
        return normalize_hgvs_c(hgvs)
    if field_id == "A.variant_hgvs_p":
        return normalize_hgvs_p(hgvs)
    return normalize_hgvs_c(hgvs)  # default


def _parse_hgvs_from_clinvar_name(name: str) -> dict[str, str]:
    """Parse ClinVar Name field into hgvs_c and hgvs_p components.

    ClinVar Name format: NM_xxx.x(GENE):c.123A>G (p.Arg42Gly)
    """
    result: dict[str, str] = {"raw": name, "hgvs_c": "", "hgvs_p": ""}

    # Extract coding HGVS (c.xxx)
    c_match = re.search(r"(c\.[^()\s]+)", name)
    if c_match:
        result["hgvs_c"] = c_match.group(1)

    # Extract protein HGVS (p.xxx) inside parentheses
    p_match = re.search(r"\((p\.[^)]+)\)", name)
    if p_match:
        result["hgvs_p"] = p_match.group(1)

    return result


def _parse_clinvar_hgvs_name(name: str) -> dict[str, str]:
    """Parse ClinVar Name into hgvs_c and hgvs_p, with normalized forms.

    Returns dict with keys: raw, hgvs_c, hgvs_p, normalized_c, normalized_p
    """
    parsed = _parse_hgvs_from_clinvar_name(name)
    parsed["normalized_c"] = normalize_hgvs_c(parsed["hgvs_c"]) if parsed["hgvs_c"] else ""
    parsed["normalized_p"] = normalize_hgvs_p(parsed["hgvs_p"]) if parsed["hgvs_p"] else ""
    return parsed
