"""Frozen Stage-1 corpus manifest for the ACMG multilingual four-arm study.

The four-arm design compares, on one pre-frozen multilingual corpus, an
English-only arm against three all-source arms that read non-English papers as
machine translation, native full text, or both. This module freezes the corpus
half of that design: it scans the external native-language Rett corpus once,
deduplicates by content hash, classifies each source family's native language,
and extracts candidate MECP2 coding variants to build cross-language pairing
anchors (variants reported by both an English and a non-English family).

Everything is content-addressed and read-only. ``scan_corpus`` produces the
frozen manifest; ``verify_corpus_manifest`` re-scans and compares hashes,
language, dedup, and variants without contacting a model or promoting any
source to a run.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CorpusLanguage = Literal["en", "zh", "ja", "ko", "ru"]

_CASE_ID_RE = re.compile(r"^rett_[0-9]{3}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Native-language detection by script. Han is shared by Chinese and Japanese,
# so kana is checked first; Cyrillic and Hangul are unambiguous. An English
# native paper never carries 200+ Han/Cyrillic/Hangul characters, while a
# bilingual non-English paper (native full text plus an English abstract)
# does.
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_HANGUL_RE = re.compile(r"[\uac00-\ud7af]")
_HIRAGANA_RE = re.compile(r"[\u3040-\u309F]")
_KATAKANA_RE = re.compile(r"[\u30A0-\u30FF]")
_HAN_RE = re.compile(r"[\u4e00-\u9fff]")

# Candidate MECP2 coding HGVS extraction. The alternation order lets a
# substitution match before the del/ins/dup branches, and each branch requires
# a base/sequence so a bare ``c.1126C`` cannot be emitted.
_HGVS_SUB = r"c\.\d+(?:_\d+)?[A-Za-z]+>[A-Za-z*]+"
_HGVS_DEL = r"c\.\d+(?:_\d+)?(?:[A-Za-z]+)?del[A-Za-z]+"
_HGVS_INS = r"c\.\d+(?:_\d+)?(?:[A-Za-z]+)?ins[A-Za-z]+"
_HGVS_DUP = r"c\.\d+(?:_\d+)?(?:[A-Za-z]+)?dup[A-Za-z]+"
_HGVS_RE = re.compile("|".join((_HGVS_SUB, _HGVS_DEL, _HGVS_INS, _HGVS_DUP)))



def _sha256(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def _classify_native_language(text: str) -> CorpusLanguage:
    """Classify a document's native language from its dominant non-Latin script."""
    if len(_CYRILLIC_RE.findall(text)) > 200:
        return "ru"
    if len(_HANGUL_RE.findall(text)) > 200:
        return "ko"
    if len(_HIRAGANA_RE.findall(text)) + len(_KATAKANA_RE.findall(text)) > 200:
        return "ja"
    if len(_HAN_RE.findall(text)) > 200:
        return "zh"
    return "en"


def _extract_candidate_variants(text: str) -> tuple[str, ...]:
    """Extract candidate ``c.`` coding HGVS tokens, decoded from HTML entities."""
    decoded = html.unescape(text)
    return tuple(sorted({m.group(0) for m in _HGVS_RE.finditer(decoded)}))


def _resolve_source_path(source_root: Path, relative_path: Path) -> Path:
    """Resolve a manifest path while preventing escape from the source root."""
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"source path escapes the source root: {relative_path}")
    return source_root / relative_path


class SourceFamilyRecord(BaseModel):
    """One deduplicated source family and its mechanical corpus attributes."""

    model_config = ConfigDict(frozen=True)

    family_id: str
    language: CorpusLanguage
    source_relative_path: str
    source_sha256: str = Field(min_length=64, max_length=64)
    alias_case_ids: tuple[str, ...] = ()
    candidate_variants: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_record(self) -> "SourceFamilyRecord":
        if not _CASE_ID_RE.fullmatch(self.family_id):
            raise ValueError(f"family_id must match rett_NNN, got {self.family_id!r}")
        if not _SHA256_RE.fullmatch(self.source_sha256):
            raise ValueError("source_sha256 must be a 64-char lowercase hex digest")
        if self.source_relative_path != f"{self.family_id}/source.md":
            raise ValueError("source_relative_path must be '<family_id>/source.md'")
        if tuple(sorted(set(self.alias_case_ids))) != self.alias_case_ids:
            raise ValueError("alias_case_ids must be sorted and unique")
        for alias in self.alias_case_ids:
            if not _CASE_ID_RE.fullmatch(alias):
                raise ValueError(f"alias_case_ids must match rett_NNN, got {alias!r}")
            if alias <= self.family_id:
                raise ValueError("alias_case_ids must sort strictly after family_id")
        if tuple(sorted(set(self.candidate_variants))) != self.candidate_variants:
            raise ValueError("candidate_variants must be sorted and unique")
        return self


class VariantPairingAnchor(BaseModel):
    """A coding variant reported by at least one English and one non-English family."""

    model_config = ConfigDict(frozen=True)

    variant: str
    english_family_ids: tuple[str, ...]
    non_english_family_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_anchor(self) -> "VariantPairingAnchor":
        if not self.english_family_ids or not self.non_english_family_ids:
            raise ValueError("a pairing anchor needs both English and non-English families")
        if tuple(sorted(set(self.english_family_ids))) != self.english_family_ids:
            raise ValueError("english_family_ids must be sorted and unique")
        if tuple(sorted(set(self.non_english_family_ids))) != self.non_english_family_ids:
            raise ValueError("non_english_family_ids must be sorted and unique")
        return self


class Stage1CorpusManifest(BaseModel):
    """Frozen, content-addressed enumeration of the four-arm corpus."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    protocol_version: str
    created_on: str
    corpus_revision: str
    corpus_note: str
    families: tuple[SourceFamilyRecord, ...]
    pairing_anchors: tuple[VariantPairingAnchor, ...]

    @model_validator(mode="after")
    def _validate_manifest(self) -> "Stage1CorpusManifest":
        family_ids = [f.family_id for f in self.families]
        if tuple(sorted(family_ids)) != tuple(family_ids):
            raise ValueError("families must be sorted by family_id")
        if len(set(family_ids)) != len(family_ids):
            raise ValueError("family_id values must be unique")
        language_by_id = {f.family_id: f.language for f in self.families}
        for anchor in self.pairing_anchors:
            for family_id in anchor.english_family_ids + anchor.non_english_family_ids:
                if family_id not in language_by_id:
                    raise ValueError(f"anchor {anchor.variant} cites unknown family {family_id!r}")
            for family_id in anchor.english_family_ids:
                if language_by_id[family_id] != "en":
                    raise ValueError(f"anchor {anchor.variant} lists non-English family {family_id!r} as English")
            for family_id in anchor.non_english_family_ids:
                if language_by_id[family_id] == "en":
                    raise ValueError(f"anchor {anchor.variant} lists English family {family_id!r} as non-English")
        if tuple(a.variant for a in self.pairing_anchors) != tuple(sorted(a.variant for a in self.pairing_anchors)):
            raise ValueError("pairing_anchors must be sorted by variant")
        if len({a.variant for a in self.pairing_anchors}) != len(self.pairing_anchors):
            raise ValueError("pairing anchor variants must be unique")
        return self

    def fingerprint(self) -> str:
        """Return a content digest of families and anchors, ignoring metadata."""
        payload = json.dumps(
            {
                "families": [family.model_dump(mode="json") for family in self.families],
                "pairing_anchors": [anchor.model_dump(mode="json") for anchor in self.pairing_anchors],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return _sha256(payload.encode("utf-8"))

def _build_pairing_anchors(families: tuple[SourceFamilyRecord, ...]) -> tuple[VariantPairingAnchor, ...]:
    """Index every candidate variant into English and non-English families."""
    english: dict[str, set[str]] = defaultdict(set)
    non_english: dict[str, set[str]] = defaultdict(set)
    for family in families:
        target = english if family.language == "en" else non_english
        for variant in family.candidate_variants:
            target[variant].add(family.family_id)
    anchors: list[VariantPairingAnchor] = []
    for variant in sorted(set(english) | set(non_english)):
        if english.get(variant) and non_english.get(variant):
            anchors.append(
                VariantPairingAnchor(
                    variant=variant,
                    english_family_ids=tuple(sorted(english[variant])),
                    non_english_family_ids=tuple(sorted(non_english[variant])),
                )
            )
    return tuple(anchors)


def scan_corpus(
    source_root: Path,
    *,
    corpus_revision: str,
    created_on: str,
) -> Stage1CorpusManifest:
    """Scan the external corpus once into a frozen, deduplicated manifest."""
    source_paths = sorted(source_root.glob("rett_*/source.md"))
    if not source_paths:
        raise ValueError(f"no rett_*/source.md found under {source_root}")

    names_by_hash: dict[str, list[str]] = defaultdict(list)
    for source_path in source_paths:
        names_by_hash[_sha256(source_path.read_bytes())].append(source_path.parent.name)

    families: list[SourceFamilyRecord] = []
    for digest, names in names_by_hash.items():
        canonical = sorted(names)[0]
        aliases = tuple(name for name in sorted(names) if name != canonical)
        text = _resolve_source_path(source_root, Path(f"{canonical}/source.md")).read_text(
            encoding="utf-8", errors="replace"
        )
        families.append(
            SourceFamilyRecord(
                family_id=canonical,
                language=_classify_native_language(text),
                source_relative_path=f"{canonical}/source.md",
                source_sha256=digest,
                alias_case_ids=aliases,
                candidate_variants=_extract_candidate_variants(text),
            )
        )
    families.sort(key=lambda family: family.family_id)

    return Stage1CorpusManifest(
        study_id="acmg-multilingual-stage1-corpus",
        protocol_version="v1",
        created_on=created_on,
        corpus_revision=corpus_revision,
        corpus_note=(
            "External native-language Rett-spectrum corpus (caller-provided source root). "
            "Content hashes are the integrity authority; this note is descriptive only."
        ),
        families=tuple(families),
        pairing_anchors=_build_pairing_anchors(tuple(families)),
    )


def load_corpus_manifest(path: Path) -> Stage1CorpusManifest:
    """Load the frozen Stage-1 corpus manifest from JSON."""
    return Stage1CorpusManifest.model_validate_json(path.read_text(encoding="utf-8"))


def write_corpus_manifest(manifest: Stage1CorpusManifest, path: Path) -> None:
    """Persist the frozen corpus manifest as canonical JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
    path.write_text(payload + "\n", encoding="utf-8")


class CorpusVerificationReport(BaseModel):
    """Deterministic receipt for a corpus-manifest integrity audit."""

    model_config = ConfigDict(frozen=True)

    manifest_fingerprint: str
    corpus_revision: str
    total_families: int
    verified_families: int
    drifted_source_families: tuple[str, ...]
    language_mismatches: tuple[str, ...]
    variant_mismatches: tuple[str, ...]
    alias_mismatches: tuple[str, ...]


def verify_corpus_manifest(manifest: Stage1CorpusManifest, source_root: Path) -> CorpusVerificationReport:
    """Re-scan the corpus and compare every family against the frozen manifest."""
    rescanned = scan_corpus(
        source_root,
        corpus_revision=manifest.corpus_revision,
        created_on=manifest.created_on,
    )
    frozen = {family.family_id: family for family in manifest.families}
    current = {family.family_id: family for family in rescanned.families}

    drifted: list[str] = []
    language_mismatches: list[str] = []
    variant_mismatches: list[str] = []
    alias_mismatches: list[str] = []

    for family_id in sorted(set(frozen) | set(current)):
        frozen_family = frozen.get(family_id)
        current_family = current.get(family_id)
        if frozen_family is None or current_family is None:
            drifted.append(family_id)
            continue
        if frozen_family.source_sha256 != current_family.source_sha256:
            drifted.append(family_id)
            continue
        if frozen_family.language != current_family.language:
            language_mismatches.append(family_id)
        if frozen_family.candidate_variants != current_family.candidate_variants:
            variant_mismatches.append(family_id)
        if frozen_family.alias_case_ids != current_family.alias_case_ids:
            alias_mismatches.append(family_id)

    mismatched = set(drifted) | set(language_mismatches) | set(variant_mismatches) | set(alias_mismatches)
    return CorpusVerificationReport(
        manifest_fingerprint=manifest.fingerprint(),
        corpus_revision=manifest.corpus_revision,
        total_families=len(frozen),
        verified_families=len(frozen) - len(mismatched),
        drifted_source_families=tuple(drifted),
        language_mismatches=tuple(language_mismatches),
        variant_mismatches=tuple(variant_mismatches),
        alias_mismatches=tuple(alias_mismatches),
    )


def write_corpus_verification_report(report: CorpusVerificationReport, path: Path) -> None:
    """Persist a deterministic receipt for the corpus audit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
    path.write_text(payload + "\n", encoding="utf-8")
