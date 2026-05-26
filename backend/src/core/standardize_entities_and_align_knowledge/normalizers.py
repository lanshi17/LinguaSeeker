"""Normalization helpers shared by terminology import and matching."""
from __future__ import annotations

import hashlib
import re
import unicodedata

_SPACE_RE = re.compile(r"\s+")

# Common Chinese disease names in medical genetics that map to English equivalents.
# Used for cross-lingual alias expansion during terminology lookup.
_CROSS_LINGUAL_DISEASE_MAP: dict[str, str] = {
    "法布雷病": "fabry disease",
    "戈谢病": "gaucher disease",
    "庞贝病": "pompe disease",
    "尼曼匹克病": "niemann-pick disease",
    "威尔逊病": "wilson disease",
    "亨廷顿病": "huntington disease",
    "马凡综合征": "marfan syndrome",
    "囊性纤维化": "cystic fibrosis",
    "杜氏肌营养不良": "duchenne muscular dystrophy",
    "贝克肌营养不良": "becker muscular dystrophy",
    "脊髓性肌萎缩": "spinal muscular atrophy",
    "地中海贫血": "thalassemia",
    "镰状细胞病": "sickle cell disease",
    "血友病": "hemophilia",
}


def normalize_lookup_text(value: str) -> str:
    """Normalize lookup text with stable Unicode folding and spacing."""
    text = unicodedata.normalize("NFKC", value or "")
    text = _SPACE_RE.sub(" ", text.strip())
    return text.casefold()


def normalize_gene_symbol(value: str) -> str:
    """Normalize gene symbols for exact HGNC-style matching."""
    return normalize_lookup_text(value).upper()


def normalize_variant_text(value: str) -> str:
    """Normalize variant aliases by removing display whitespace."""
    return _SPACE_RE.sub("", unicodedata.normalize("NFKC", value or "").strip())


def normalize_disease_lookup_text(value: str) -> str:
    """Normalize disease names with cross-lingual Chinese-to-English mapping."""
    normalized = normalize_lookup_text(value)
    return _CROSS_LINGUAL_DISEASE_MAP.get(normalized, normalized)


def make_entity_scope_hash(bindings: list[tuple[str, str]]) -> str:
    """Build an order-independent entity-scope hash from role/identity pairs."""
    stable = "|".join(f"{role}:{identity}" for role, identity in sorted(bindings))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()
