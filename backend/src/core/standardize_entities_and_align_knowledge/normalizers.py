"""Normalization helpers shared by terminology import and matching."""
from __future__ import annotations

import hashlib
import re
import unicodedata


_SPACE_RE = re.compile(r"\s+")


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


def make_entity_scope_hash(bindings: list[tuple[str, str]]) -> str:
    """Build an order-independent entity-scope hash from role/identity pairs."""
    stable = "|".join(f"{role}:{identity}" for role, identity in sorted(bindings))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()
