"""Build target-safe context packs from benchmark metadata."""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from .contracts import DiseaseContext, GeneContext, TargetContextPack


_PAREN_RE = re.compile(r"\s*\([^)]*\)")
_ABBREVIATION_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9})\b")
_SPACE_RE = re.compile(r"\s+")
_SOURCE_ALIAS_SPLIT_RE = re.compile(r"[.!?\n]")
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
    source_text = _load_source_text(path)
    disease_aliases = _disease_aliases(disease_label)
    if source_text:
        disease_aliases = _source_aware_disease_aliases(disease_label, disease_aliases, source_text)

    return TargetContextPack(
        entry_id=_string(raw.get("entry_id")),
        gene=GeneContext(
            symbol=gene_symbol,
            hgnc_id=_optional_string(raw.get("hgnc_id")),
            aliases=(gene_symbol,) if gene_symbol else (),
        ),
        disease=DiseaseContext(
            label=disease_label,
            mondo_id=_optional_string(raw.get("mondo_id")),
            aliases=disease_aliases,
            ancestor_labels=(),
        ),
        moi=_string(raw.get("moi")),
        source_pmid=_optional_string(raw.get("source_pmid")),
        source_pmc=_optional_string(raw.get("source_pmc")),
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
