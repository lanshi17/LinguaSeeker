"""Cross-disease ACMG increment denominator: freeze, load, and verify.

This ledger widens the study beyond MECP2/Rett Chinese papers. Every slot is a
predeclared ``case_id × target variant × criterion family`` unit that can later
enter Stage-1 adjudication. Formal ACMG codes remain 0 until blinded review.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

IncrementTrackId = Literal[
    "multilingual_pm6_pvs1",
    "english_pm3_ready",
    "parkinson_latent_pp1_ps3_ps4",
]
CriterionFamily = Literal["PS2_PM6", "PM3", "PP1_BS4", "PS3_BS3", "PS4", "PVS1"]
EligibilityTier = Literal[
    "source_fact_eligible",
    "code_candidate",
    "latent_pending_materialization",
    "negative_control",
]
MaterializationStatus = Literal[
    "on_disk",
    "needs_external_corpus",
    "needs_workbook_export",
]
SourceRootKind = Literal["reviewed", "clinvar_fused", "parkinson_workbook", "external_rett"]

_HASH_CHARS = frozenset("0123456789abcdef")


class IncrementSpan(BaseModel):
    """One line-anchored quote that must appear in the owned source when on disk."""

    model_config = ConfigDict(frozen=True)

    line: int = Field(ge=1)
    quote: str = Field(min_length=1)
    language: str = Field(min_length=2, max_length=16)


class IncrementSlot(BaseModel):
    """One predeclared case × variant × criterion-family unit in the denominator."""

    model_config = ConfigDict(frozen=True)

    slot_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    gene: str = Field(min_length=1)
    disease: str = Field(min_length=1)
    target_hgvs_c: str = Field(min_length=1)
    partner_allele: str = ""
    criterion_family: CriterionFamily
    eligibility_tier: EligibilityTier
    materialization_status: MaterializationStatus
    source_root_kind: SourceRootKind
    source_relative_path: str = ""
    source_sha256: str = ""
    native_language: str = Field(min_length=2, max_length=16)
    fulltext_increment_over_english_pivot: int | None = None
    spans: tuple[IncrementSpan, ...] = ()
    notes: str = ""
    provenance: str = ""

    @model_validator(mode="after")
    def validate_slot(self) -> IncrementSlot:
        """Keep on-disk slots content-addressed and latent slots free of fake hashes."""
        if self.materialization_status == "on_disk":
            if not self.source_relative_path:
                raise ValueError(f"{self.slot_id}: on_disk slots require source_relative_path")
            relative_path = Path(self.source_relative_path)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise ValueError(f"{self.slot_id}: source_relative_path must stay below its root")
            if len(self.source_sha256) != 64 or any(
                character not in _HASH_CHARS for character in self.source_sha256
            ):
                raise ValueError(f"{self.slot_id}: on_disk slots require a lowercase SHA-256 digest")
            if not self.spans:
                raise ValueError(f"{self.slot_id}: on_disk slots require at least one span")
        else:
            if self.source_sha256:
                raise ValueError(f"{self.slot_id}: non-on_disk slots must not set source_sha256")
        if self.criterion_family == "PM3" and not self.partner_allele and self.eligibility_tier != "negative_control":
            raise ValueError(f"{self.slot_id}: PM3 slots require partner_allele")
        return self


class IncrementTrack(BaseModel):
    """One narrative track grouping related increment slots."""

    model_config = ConfigDict(frozen=True)

    track_id: IncrementTrackId
    narrative: str = Field(min_length=1)
    slots: tuple[IncrementSlot, ...]

    @model_validator(mode="after")
    def validate_track(self) -> IncrementTrack:
        """Reject empty tracks and duplicate slot ids within a track."""
        if not self.slots:
            raise ValueError(f"{self.track_id}: track must contain at least one slot")
        slot_ids = [slot.slot_id for slot in self.slots]
        if len(set(slot_ids)) != len(slot_ids):
            raise ValueError(f"{self.track_id}: slot_id values must be unique")
        return self


class IncrementDenominator(BaseModel):
    """Frozen cross-disease ACMG increment denominator."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    protocol_version: str
    created_on: str
    scope_note: str
    provenance: tuple[str, ...]
    tracks: tuple[IncrementTrack, ...]

    @model_validator(mode="after")
    def validate_denominator(self) -> IncrementDenominator:
        """Require all three tracks and globally unique slot ids."""
        track_ids = [track.track_id for track in self.tracks]
        expected = {
            "multilingual_pm6_pvs1",
            "english_pm3_ready",
            "parkinson_latent_pp1_ps3_ps4",
        }
        if set(track_ids) != expected:
            raise ValueError(f"tracks must be exactly {sorted(expected)}")
        all_slot_ids = [slot.slot_id for track in self.tracks for slot in track.slots]
        if len(set(all_slot_ids)) != len(all_slot_ids):
            raise ValueError("slot_id values must be unique across the denominator")
        return self


class SlotVerificationResult(BaseModel):
    """Outcome of verifying one on-disk increment slot against a source root."""

    model_config = ConfigDict(frozen=True)

    slot_id: str
    case_id: str
    verified: bool
    missing_file: bool = False
    hash_match: bool = False
    missing_quotes: tuple[str, ...] = ()
    detail: str = ""


class IncrementDenominatorVerificationReport(BaseModel):
    """Receipt for a read-only verification of materializable increment slots."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    protocol_version: str
    total_slots: int
    on_disk_slots: int
    verified_on_disk_slots: int
    latent_slots: int
    results: tuple[SlotVerificationResult, ...]


def load_increment_denominator(path: Path) -> IncrementDenominator:
    """Load and validate a frozen increment denominator JSON file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return IncrementDenominator.model_validate(payload)


@dataclass(frozen=True)
class IncrementDenominatorSummary:
    """Compact counts for CLI output and unit tests."""

    total_slots: int
    on_disk: int
    needs_external_corpus: int
    needs_workbook_export: int
    family_counts: tuple[tuple[str, int], ...]


def summarize_increment_denominator(denominator: IncrementDenominator) -> IncrementDenominatorSummary:
    """Return compact counts used by CLI and tests."""
    slots = [slot for track in denominator.tracks for slot in track.slots]
    by_family: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for slot in slots:
        by_family[slot.criterion_family] = by_family.get(slot.criterion_family, 0) + 1
        by_status[slot.materialization_status] = by_status.get(slot.materialization_status, 0) + 1
    return IncrementDenominatorSummary(
        total_slots=len(slots),
        on_disk=by_status.get("on_disk", 0),
        needs_external_corpus=by_status.get("needs_external_corpus", 0),
        needs_workbook_export=by_status.get("needs_workbook_export", 0),
        family_counts=tuple(sorted(by_family.items())),
    )


def _resolve_source_root(
    slot: IncrementSlot,
    *,
    reviewed_root: Path | None,
    clinvar_fused_root: Path | None,
) -> Path | None:
    """Map a slot's declared root kind to a caller-provided directory."""
    if slot.source_root_kind == "reviewed":
        return reviewed_root
    if slot.source_root_kind == "clinvar_fused":
        return clinvar_fused_root
    return None


def verify_increment_denominator(
    denominator: IncrementDenominator,
    *,
    reviewed_root: Path | None = None,
    clinvar_fused_root: Path | None = None,
) -> IncrementDenominatorVerificationReport:
    """Verify every on_disk slot's hash and cited quotes; leave latent slots unchecked."""
    results: list[SlotVerificationResult] = []
    on_disk_count = 0
    verified_count = 0
    latent_count = 0

    for track in denominator.tracks:
        for slot in track.slots:
            if slot.materialization_status != "on_disk":
                latent_count += 1
                results.append(
                    SlotVerificationResult(
                        slot_id=slot.slot_id,
                        case_id=slot.case_id,
                        verified=True,
                        detail="latent slot; content check deferred until materialization",
                    )
                )
                continue

            on_disk_count += 1
            root = _resolve_source_root(
                slot,
                reviewed_root=reviewed_root,
                clinvar_fused_root=clinvar_fused_root,
            )
            if root is None:
                results.append(
                    SlotVerificationResult(
                        slot_id=slot.slot_id,
                        case_id=slot.case_id,
                        verified=False,
                        detail=f"missing source root for {slot.source_root_kind}",
                    )
                )
                continue

            source_path = root / slot.source_relative_path
            if not source_path.is_file():
                results.append(
                    SlotVerificationResult(
                        slot_id=slot.slot_id,
                        case_id=slot.case_id,
                        verified=False,
                        missing_file=True,
                        detail=f"missing file: {source_path}",
                    )
                )
                continue

            digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
            hash_match = digest == slot.source_sha256
            text = source_path.read_text(encoding="utf-8")
            lines = text.splitlines()
            missing_quotes: list[str] = []
            for span in slot.spans:
                if span.line > len(lines) or span.quote not in lines[span.line - 1]:
                    if span.quote not in text:
                        missing_quotes.append(span.quote)
            verified = hash_match and not missing_quotes
            if verified:
                verified_count += 1
            results.append(
                SlotVerificationResult(
                    slot_id=slot.slot_id,
                    case_id=slot.case_id,
                    verified=verified,
                    hash_match=hash_match,
                    missing_quotes=tuple(missing_quotes),
                    detail="" if verified else f"digest={digest}",
                )
            )

    return IncrementDenominatorVerificationReport(
        study_id=denominator.study_id,
        protocol_version=denominator.protocol_version,
        total_slots=on_disk_count + latent_count,
        on_disk_slots=on_disk_count,
        verified_on_disk_slots=verified_count,
        latent_slots=latent_count,
        results=tuple(results),
    )


def write_increment_denominator_report(
    report: IncrementDenominatorVerificationReport,
    path: Path,
) -> None:
    """Write a verification receipt as indented JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
