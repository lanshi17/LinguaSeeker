"""Build target-safe context packs from benchmark or runtime metadata."""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from .contracts import DiseaseContext, GeneContext, TargetContextPack


_PAREN_RE = re.compile(r"\s*\([^)]*\)")
_ABBREVIATION_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9})\b")
_ALIAS_ABBREVIATION_SKIPLIST = {"MIM", "OMIM", "ID"}
_DASH_TRANSLATION = str.maketrans({
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
})
_SPACE_RE = re.compile(r"\s+")
_SOURCE_ALIAS_SPLIT_RE = re.compile(r"[.!?\n]")
_MONDO_DIR = (
    Path(__file__).resolve().parents[5]
    / "database"
    / "terminology_database"
    / "mondo"
)
_MONDO_CACHE_PATH = _MONDO_DIR / "mondo_hierarchy_cache.json"
_STOPWORDS = {
    "cell",
    "cells",
    "complex",
    "disease",
    "gene",
    "genes",
    "immune",
    "kinase",
    "mutation",
    "pathway",
    "protein",
    "proteins",
    "receptor",
    "signal",
    "signaling",
    "syndrome",
    "tract",
    "variant",
    "variants",
    "virus",
}


def build_context_pack_from_expected_json(path: Path) -> TargetContextPack:
    """Build a no-leakage target context pack from a ClinGen expected.json file."""
    raw = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    gene_symbol = _string(raw.get("gene_symbol")).upper()
    disease_label = _string(raw.get("disease_label"))
    mondo_id = _optional_string(raw.get("mondo_id"))
    source_text = _load_source_text(path)
    disease_aliases = _disease_aliases(disease_label)
    if source_text:
        disease_aliases = _source_aware_disease_aliases(disease_label, disease_aliases, source_text)
    if source_text and mondo_id:
        disease_aliases = _source_observed_mondo_aliases(gene_symbol, disease_label, disease_aliases, source_text)

    return TargetContextPack(
        entry_id=_string(raw.get("entry_id")),
        gene=GeneContext(
            symbol=gene_symbol,
            hgnc_id=_optional_string(raw.get("hgnc_id")),
            aliases=(gene_symbol,) if gene_symbol else (),
        ),
        disease=DiseaseContext(
            label=disease_label,
            mondo_id=mondo_id,
            aliases=disease_aliases,
            ancestor_labels=(),
        ),
        moi=_string(raw.get("moi")),
        source_pmid=_optional_string(raw.get("source_pmid")),
        source_pmc=_optional_string(raw.get("source_pmc")),
    )


def build_context_pack_from_runtime_target(
    *,
    entry_id: str,
    gene_symbol: str,
    disease_label: str,
    hgnc_id: str | None = None,
    mondo_id: str | None = None,
    moi: str = "",
    source_pmid: str | None = None,
    source_pmc: str | None = None,
) -> TargetContextPack:
    """Build a target context pack from production runtime metadata."""
    normalized_gene = _string(gene_symbol).upper()
    normalized_disease = _string(disease_label)
    return TargetContextPack(
        entry_id=_string(entry_id),
        gene=GeneContext(
            symbol=normalized_gene,
            hgnc_id=_optional_string(hgnc_id),
            aliases=(normalized_gene,) if normalized_gene else (),
        ),
        disease=DiseaseContext(
            label=normalized_disease,
            mondo_id=_optional_string(mondo_id),
            aliases=_disease_aliases(normalized_disease),
            ancestor_labels=(),
        ),
        moi=_string(moi),
        source_pmid=_optional_string(source_pmid),
        source_pmc=_optional_string(source_pmc),
    )


def _disease_aliases(label: str) -> tuple[str, ...]:
    aliases: list[str] = []
    for candidate in (
        label,
        label.casefold(),
        _strip_parenthetical(label),
        _strip_parenthetical(label).casefold(),
    ):
        normalized = _normalize_spaces(candidate)
        if normalized and normalized not in aliases:
            aliases.append(normalized)
    return tuple(aliases)


def _source_observed_mondo_aliases(
    gene_symbol: str,
    disease_label: str,
    base_aliases: tuple[str, ...],
    source_text: str,
) -> tuple[str, ...]:
    index = _load_mondo_alias_index()
    if index is None:
        return base_aliases

    aliases = list(base_aliases)
    normalized_source = _normalize_alias_text(source_text)
    for label in index.labels:
        if not _is_safe_ontology_label(label):
            continue
        for candidate in _label_match_candidates(label):
            if candidate not in normalized_source:
                continue
            match = _source_phrase_match(source_text, candidate)
            if match is None:
                continue
            if not _has_target_context(source_text, match.start(), match.end(), gene_symbol, disease_label):
                continue
            observed = _normalize_spaces(match.group(0))
            _append_alias(aliases, observed)
            for abbreviation in _source_observed_abbreviations(source_text, candidate):
                _append_alias(aliases, abbreviation)
    return tuple(aliases)


def _source_aware_disease_aliases(
    label: str,
    base_aliases: tuple[str, ...],
    source_text: str,
) -> tuple[str, ...]:
    aliases = list(base_aliases)
    stems = _disease_stems(label)
    source_sections = [section for section in _SOURCE_ALIAS_SPLIT_RE.split(source_text) if section.strip()]

    for section in source_sections:
        normalized_section = _normalize_spaces(section).casefold()
        if not normalized_section:
            continue

        if not any(stem in normalized_section for stem in stems):
            continue

        for phrase, abbreviation in _iter_abbreviation_phrases(section):
            normalized_phrase = _normalize_spaces(phrase)
            if not _is_safe_source_phrase(normalized_phrase):
                continue
            normalized_abbreviation = _normalize_spaces(abbreviation)
            if normalized_abbreviation and normalized_abbreviation not in aliases:
                aliases.append(normalized_abbreviation)

    for stem in stems:
        if stem and stem not in aliases and stem in source_text.casefold():
            aliases.append(stem)

    return tuple(aliases)


@dataclass(frozen=True)
class _MondoAliasIndex:
    labels: tuple[str, ...]


@lru_cache(maxsize=1)
def _load_mondo_alias_index() -> _MondoAliasIndex | None:
    if not _MONDO_CACHE_PATH.exists():
        return None
    raw = cast(dict[str, Any], json.loads(_MONDO_CACHE_PATH.read_text(encoding="utf-8")))
    label_to_id = cast(dict[str, str], raw.get("label_to_id", {}))
    return _MondoAliasIndex(labels=tuple(sorted(label_to_id)))


def _label_match_candidates(label: str) -> tuple[str, ...]:
    candidates = [label]
    if "," in label:
        prefix = label.split(",", 1)[0]
        if _is_safe_ontology_label(prefix):
            candidates.append(prefix)
    return tuple(dict.fromkeys(_normalize_alias_text(candidate) for candidate in candidates if candidate))


def _is_safe_ontology_label(label: str) -> bool:
    normalized = _normalize_alias_text(label)
    if normalized.startswith("obsolete "):
        return False
    if not any(term in normalized for term in ("disease", "disorder", "syndrome")):
        return False
    return len(re.findall(r"[a-z0-9]+", normalized)) >= 2


def _source_phrase_match(source_text: str, normalized_phrase: str) -> re.Match[str] | None:
    return _phrase_pattern(normalized_phrase).search(source_text)


def _source_observed_abbreviations(source_text: str, normalized_phrase: str) -> tuple[str, ...]:
    abbreviations: list[str] = []
    for match in _phrase_pattern(normalized_phrase, with_parenthetical=True).finditer(source_text):
        for abbreviation in _ABBREVIATION_RE.findall(match.group(1)):
            if abbreviation in _ALIAS_ABBREVIATION_SKIPLIST:
                continue
            if abbreviation and abbreviation not in abbreviations:
                abbreviations.append(abbreviation)
    return tuple(abbreviations)


def _phrase_pattern(normalized_phrase: str, *, with_parenthetical: bool = False) -> re.Pattern[str]:
    parts: list[str] = []
    for char in normalized_phrase:
        if char.isspace():
            parts.append(r"\s+")
        elif char == "-":
            parts.append(r"[-\u2010\u2011\u2012\u2013\u2014\u2212]")
        else:
            parts.append(re.escape(char))
    body = "".join(parts)
    suffix = r"\s*\(([^)]{2,80})\)" if with_parenthetical else ""
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9]){suffix}", re.IGNORECASE)


def _has_target_context(
    source_text: str,
    start_offset: int,
    end_offset: int,
    gene_symbol: str,
    disease_label: str,
) -> bool:
    start = max(0, start_offset - 220)
    end = min(len(source_text), end_offset + 220)
    window = _normalize_spaces(source_text[start:end]).casefold()
    gene_present = bool(gene_symbol and gene_symbol.casefold() in window)
    if not gene_present:
        return False
    disease_cues = _target_disease_cues(disease_label)
    return any(cue in window for cue in disease_cues)


def _target_disease_cues(disease_label: str) -> tuple[str, ...]:
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", disease_label.casefold())
        if len(token) > 4 and token not in _STOPWORDS and token not in {"disorder"}
    ]
    cues = [*tokens, "genetic disorder", "rare autosomal", "human genetic disorder"]
    return tuple(dict.fromkeys(cues))


def _append_alias(aliases: list[str], alias: str) -> None:
    normalized = _normalize_spaces(alias)
    if not normalized:
        return
    for candidate in (normalized, normalized.translate(_DASH_TRANSLATION)):
        if candidate and candidate not in aliases:
            aliases.append(candidate)


def _normalize_alias_text(value: str) -> str:
    return _normalize_spaces(value.translate(_DASH_TRANSLATION)).casefold()


def _disease_stems(label: str) -> tuple[str, ...]:
    stems = [alias.casefold() for alias in _disease_aliases(label)]
    if "," in label:
        prefix = _normalize_spaces(label.split(",", 1)[0])
        if prefix:
            stems.append(prefix.casefold())
    return tuple(dict.fromkeys(stems))


def _iter_abbreviation_phrases(text: str) -> Iterable[tuple[str, str]]:
    for match in re.finditer(r"([A-Za-z][^()]{2,120}?)\s*\(([A-Z][A-Z0-9]{1,9})\)", text):
        yield match.group(1), match.group(2)


def _is_safe_source_phrase(phrase: str) -> bool:
    lower_phrase = phrase.casefold()
    if len(phrase.split()) < 2:
        return False
    if any(stopword in lower_phrase for stopword in _STOPWORDS):
        return False
    return any(ch.isalpha() for ch in phrase)


def _load_source_text(path: Path) -> str | None:
    source_path = path.with_name("source.md")
    if not source_path.exists():
        return None
    return source_path.read_text(encoding="utf-8")


def _strip_parenthetical(value: str) -> str:
    return _PAREN_RE.sub("", value).strip()


def _string(value: object) -> str:
    return _normalize_spaces(str(value or ""))


def _optional_string(value: object) -> str | None:
    normalized = _string(value)
    return normalized or None


def _normalize_spaces(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip())
