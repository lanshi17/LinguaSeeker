"""Deterministic MECP2/Rett direct-inference protocol for Stage-0 case analysis.

The extractor recovers facts. This module grants criterion codes and a combining
class from those facts plus a frozen Rett/AS VCEP slice. It does not fill
``assigned_acmg_codes`` in the product pipeline, does not inherit author
self-codes, and is not a blinded Stage-1 formal adjudication.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VariantClass = Literal[
    "missense",
    "nonsense",
    "frameshift",
    "coding_deletion",
    "cnv_duplication",
]
InheritanceStatus = Literal[
    "de_novo_unconfirmed",
    "maternal",
    "paternal",
    "unknown",
    "not_applicable",
]
PhenotypeClass = Literal["rett_diagnosed", "mds", "mecp2_ndd", "other"]
SexLabel = Literal["female", "male", "unknown"]
Zygosity = Literal["heterozygous", "hemizygous", "unknown", "not_applicable"]
VisibilityLayer = Literal[
    "english_abstract",
    "english_figure_legend",
    "native_body_only",
]
MaterializationStatus = Literal["on_disk", "needs_external_corpus"]
SourceRootKind = Literal["reviewed", "external_rett"]
ClinvarMatch = Literal["exact", "transcript_alias", "coordinate_near", "unmatched", "not_applicable"]
Classification = Literal[
    "pathogenic",
    "likely_pathogenic",
    "insufficient",
    "blocked_conflict",
    "excluded",
]
GrantedCode = Literal["PM6", "PVS1", "PVS1_Moderate", "PP4", "PM1"]
RefusedCode = Literal["PS2", "PM2", "PP3", "author_self_code"]

_HASH_CHARS = frozenset("0123456789abcdef")
_LOF_CLASSES = frozenset({"nonsense", "frameshift"})
_POINT_CLASSES = frozenset({"missense", "nonsense", "frameshift"})
_CONFLICT_BLOCKS = frozenset({"clinvar_benign_expert_panel", "maternal_inheritance"})
_EXCLUDED_FLAGS = frozenset({"cnv_not_snv", "unmapped_interval"})

DEFAULT_CASES_PATH = Path(__file__).with_name("direct_inference_cases.json")


class Mecp2VcepSlice(BaseModel):
    """Frozen MECP2 coordinates used by the rule engine; not a live VCEP fetch."""

    model_config = ConfigDict(frozen=True)

    gene: str = "MECP2"
    canonical_transcript: str = "NM_004992.3"
    mane_select_transcript: str = "NM_001110792.2"
    pvs1_last_residue: int = 472
    mbd_start: int = 90
    mbd_end: int = 162
    trd_start: int = 302
    trd_end: int = 306
    citation: str = (
        "ClinGen Rett and Angelman-like Disorders VCEP, MECP2; "
        "PVS1 through p.E472 on NM_004992; PM1 missense in MBD 90-162 or TRD 302-306"
    )


class DirectInferenceSpan(BaseModel):
    """One line-anchored quote that on-disk events must match in source.md."""

    model_config = ConfigDict(frozen=True)

    line: int = Field(ge=1)
    quote: str = Field(min_length=1)
    language: str = Field(min_length=2, max_length=16)


class DirectInferenceEvent(BaseModel):
    """One frozen source event: extracted facts plus the expected engine output."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    source_cluster_id: str = Field(min_length=1)
    gene: str = "MECP2"
    paper_hgvs_c: str = Field(min_length=1)
    paper_hgvs_p: str = ""
    paper_transcript: str = ""
    canonical_allele_id: str = Field(min_length=1)
    vcep_transcript: str = "NM_004992.3"
    vcep_hgvs_c: str = ""
    vcep_protein_position: int | None = None
    vcep_protein_change: str = ""
    variant_class: VariantClass
    clinvar_vcv: str = ""
    clinvar_match: ClinvarMatch = "unmatched"
    clinvar_note: str = ""
    affected_proband: bool
    sex: SexLabel
    zygosity: Zygosity
    both_parents_tested: bool
    parents_negative_at_target: bool
    parentage_confirmed: bool
    inheritance: InheritanceStatus
    phenotype_class: PhenotypeClass
    author_self_codes: tuple[str, ...] = ()
    conflict_flags: tuple[str, ...] = ()
    visibility: VisibilityLayer
    bilingual_increment: int | None = None
    hero_role: str = ""
    materialization_status: MaterializationStatus
    source_root_kind: SourceRootKind
    source_relative_path: str = ""
    source_sha256: str = ""
    spans: tuple[DirectInferenceSpan, ...] = ()
    notes: str = ""
    expected_codes: tuple[GrantedCode, ...] = ()
    expected_classification: Classification

    @model_validator(mode="after")
    def validate_event(self) -> DirectInferenceEvent:
        """Keep on-disk events content-addressed; forbid fake hashes on latent rows."""
        if self.materialization_status == "on_disk":
            if not self.source_relative_path:
                raise ValueError(f"{self.event_id}: on_disk events require source_relative_path")
            relative_path = Path(self.source_relative_path)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise ValueError(f"{self.event_id}: source_relative_path must stay below its root")
            if len(self.source_sha256) != 64 or any(
                character not in _HASH_CHARS for character in self.source_sha256
            ):
                raise ValueError(f"{self.event_id}: on_disk events require a lowercase SHA-256 digest")
            if not self.spans:
                raise ValueError(f"{self.event_id}: on_disk events require at least one span")
        elif self.source_sha256:
            raise ValueError(f"{self.event_id}: non-on_disk events must not set source_sha256")
        if self.gene != "MECP2":
            raise ValueError(f"{self.event_id}: this protocol is frozen to MECP2")
        return self


class DirectInferenceTable(BaseModel):
    """Frozen case table plus the VCEP slice the engine is allowed to use."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    protocol_version: str
    created_on: str
    scope_note: str
    vcep: Mecp2VcepSlice
    events: tuple[DirectInferenceEvent, ...]

    @model_validator(mode="after")
    def validate_table(self) -> DirectInferenceTable:
        """Reject empty tables and duplicate event ids."""
        if not self.events:
            raise ValueError("direct inference table must contain at least one event")
        event_ids = [event.event_id for event in self.events]
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("event_id values must be unique")
        return self


class DirectInferenceResult(BaseModel):
    """Engine output for one event; codes are granted, never copied from the paper."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    canonical_allele_id: str
    granted_codes: tuple[GrantedCode, ...]
    refused_codes: tuple[RefusedCode, ...]
    classification: Classification
    classification_reason: str


class EventVerificationResult(BaseModel):
    """Outcome of verifying one on-disk event against a source root."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    case_id: str
    verified: bool
    missing_file: bool = False
    hash_match: bool = False
    engine_match: bool = False
    missing_quotes: tuple[str, ...] = ()
    detail: str = ""


class DirectInferenceVerificationReport(BaseModel):
    """Receipt for hash, quote, and frozen-expectation checks."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    protocol_version: str
    total_events: int
    on_disk_events: int
    verified_on_disk_events: int
    engine_mismatches: int
    results: tuple[EventVerificationResult, ...]


@dataclass(frozen=True)
class DirectInferenceSummary:
    """Compact counts used by CLI, tests, and the reviewer-facing write-up."""

    total_events: int
    on_disk: int
    needs_external_corpus: int
    pm6_granted: int
    pvs1_granted: int
    pathogenic: int
    likely_pathogenic: int
    insufficient: int
    blocked_conflict: int
    excluded: int
    pathogenic_clinvar_gap: int
    bilingual_increment: int
    bilingual_increment_without_rett_007: int
    unique_pathogenic_alleles: int


def load_direct_inference_table(path: Path | None = None) -> DirectInferenceTable:
    """Load and validate the frozen direct-inference case table."""
    payload = json.loads((path or DEFAULT_CASES_PATH).read_text(encoding="utf-8"))
    return DirectInferenceTable.model_validate(payload)


def _in_closed_interval(position: int | None, start: int, end: int) -> bool:
    """Return True when a 1-based protein residue sits inside an inclusive domain."""
    return position is not None and start <= position <= end


def _combine_rett_vcep(*, n_vs: int, n_strong: int, n_mod: int, n_sup: int) -> Classification:
    """Apply the Richards 2015 pathogenic/LP combinations used by Rett VCEP.

    Pathogenic is tested first. One Very Strong plus one Moderate is Likely
    Pathogenic, not Pathogenic; adding one Supporting reaches Pathogenic.
    """
    if n_vs and n_strong >= 1:
        return "pathogenic"
    if n_vs and n_mod >= 2:
        return "pathogenic"
    if n_vs and n_mod >= 1 and n_sup >= 1:
        return "pathogenic"
    if n_vs and n_sup >= 2:
        return "pathogenic"
    if n_strong >= 2:
        return "pathogenic"
    if n_strong >= 1 and n_mod >= 3:
        return "pathogenic"
    if n_vs and n_mod >= 1:
        return "likely_pathogenic"
    if n_strong >= 1 and n_mod >= 1:
        return "likely_pathogenic"
    if n_strong >= 1 and n_sup >= 2:
        return "likely_pathogenic"
    if n_mod >= 3:
        return "likely_pathogenic"
    if n_mod >= 2 and n_sup >= 2:
        return "likely_pathogenic"
    if n_mod >= 1 and n_sup >= 4:
        return "likely_pathogenic"
    return "insufficient"


def infer_event(event: DirectInferenceEvent, vcep: Mecp2VcepSlice) -> DirectInferenceResult:
    """Grant codes from extracted fields; never copy author self-codes; never grant PS2."""
    granted: list[GrantedCode] = []
    refused: list[RefusedCode] = ["PS2"]
    if event.author_self_codes:
        refused.append("author_self_code")
        if "PM2" in event.author_self_codes:
            refused.append("PM2")
        if "PP3" in event.author_self_codes:
            refused.append("PP3")

    flags = set(event.conflict_flags)
    if flags & _EXCLUDED_FLAGS or event.variant_class == "cnv_duplication":
        return DirectInferenceResult(
            event_id=event.event_id,
            canonical_allele_id=event.canonical_allele_id,
            granted_codes=(),
            refused_codes=tuple(dict.fromkeys(refused)),
            classification="excluded",
            classification_reason="CNV or unmapped interval is outside the point-variant engine",
        )

    if (
        event.variant_class in _POINT_CLASSES
        and event.affected_proband
        and event.both_parents_tested
        and event.parents_negative_at_target
        and not event.parentage_confirmed
        and event.inheritance == "de_novo_unconfirmed"
    ):
        granted.append("PM6")

    if event.variant_class in _LOF_CLASSES and event.vcep_protein_position is not None:
        if event.vcep_protein_position <= vcep.pvs1_last_residue:
            granted.append("PVS1")
        else:
            granted.append("PVS1_Moderate")

    if event.phenotype_class in {"rett_diagnosed", "mecp2_ndd"}:
        granted.append("PP4")

    if event.variant_class == "missense" and (
        _in_closed_interval(event.vcep_protein_position, vcep.mbd_start, vcep.mbd_end)
        or _in_closed_interval(event.vcep_protein_position, vcep.trd_start, vcep.trd_end)
    ):
        granted.append("PM1")

    if flags & _CONFLICT_BLOCKS:
        return DirectInferenceResult(
            event_id=event.event_id,
            canonical_allele_id=event.canonical_allele_id,
            granted_codes=tuple(granted),
            refused_codes=tuple(dict.fromkeys(refused)),
            classification="blocked_conflict",
            classification_reason="conflict layer blocked pathogenic inference: "
            + ", ".join(sorted(flags & _CONFLICT_BLOCKS)),
        )

    n_vs = int("PVS1" in granted)
    n_mod = sum(code in granted for code in ("PM6", "PM1", "PVS1_Moderate"))
    n_sup = int("PP4" in granted)
    classification = _combine_rett_vcep(n_vs=n_vs, n_strong=0, n_mod=n_mod, n_sup=n_sup)
    reason = (
        f"codes={'+'.join(granted) or 'none'}; "
        f"VS={n_vs} Mod={n_mod} Sup={n_sup}"
    )
    return DirectInferenceResult(
        event_id=event.event_id,
        canonical_allele_id=event.canonical_allele_id,
        granted_codes=tuple(granted),
        refused_codes=tuple(dict.fromkeys(refused)),
        classification=classification,
        classification_reason=reason,
    )


def infer_table(table: DirectInferenceTable) -> tuple[DirectInferenceResult, ...]:
    """Run the engine over every frozen event."""
    return tuple(infer_event(event, table.vcep) for event in table.events)


def _bilingual_increment(events: tuple[DirectInferenceEvent, ...], *, drop_clusters: frozenset[str]) -> int:
    """Sum per-cluster bilingual increments; do not add events inside one series."""
    by_cluster: dict[str, int] = {}
    for event in events:
        if event.source_cluster_id in drop_clusters:
            continue
        if event.bilingual_increment is None:
            continue
        by_cluster[event.source_cluster_id] = event.bilingual_increment
    return sum(by_cluster.values())


def summarize_direct_inference(
    table: DirectInferenceTable,
    results: tuple[DirectInferenceResult, ...] | None = None,
) -> DirectInferenceSummary:
    """Return reviewer-facing counts with cluster-not-event bilingual increment."""
    inferred = results or infer_table(table)
    by_id = {result.event_id: result for result in inferred}
    pathogenic_gap = 0
    pathogenic_alleles: set[str] = set()
    for event in table.events:
        result = by_id[event.event_id]
        if result.classification == "pathogenic":
            pathogenic_alleles.add(event.canonical_allele_id)
            if event.clinvar_match in {"unmatched", "coordinate_near"}:
                pathogenic_gap += 1
    return DirectInferenceSummary(
        total_events=len(table.events),
        on_disk=sum(event.materialization_status == "on_disk" for event in table.events),
        needs_external_corpus=sum(
            event.materialization_status == "needs_external_corpus" for event in table.events
        ),
        pm6_granted=sum("PM6" in result.granted_codes for result in inferred),
        pvs1_granted=sum("PVS1" in result.granted_codes for result in inferred),
        pathogenic=sum(result.classification == "pathogenic" for result in inferred),
        likely_pathogenic=sum(result.classification == "likely_pathogenic" for result in inferred),
        insufficient=sum(result.classification == "insufficient" for result in inferred),
        blocked_conflict=sum(result.classification == "blocked_conflict" for result in inferred),
        excluded=sum(result.classification == "excluded" for result in inferred),
        pathogenic_clinvar_gap=pathogenic_gap,
        bilingual_increment=_bilingual_increment(table.events, drop_clusters=frozenset()),
        bilingual_increment_without_rett_007=_bilingual_increment(
            table.events, drop_clusters=frozenset({"rett_007"})
        ),
        unique_pathogenic_alleles=len(pathogenic_alleles),
    )


def verify_direct_inference(
    table: DirectInferenceTable,
    *,
    reviewed_root: Path | None = None,
) -> DirectInferenceVerificationReport:
    """Verify on-disk hashes/quotes and that the engine matches frozen expectations."""
    results: list[EventVerificationResult] = []
    on_disk_count = 0
    verified_count = 0
    mismatch_count = 0

    for event in table.events:
        inferred = infer_event(event, table.vcep)
        engine_match = (
            inferred.granted_codes == event.expected_codes
            and inferred.classification == event.expected_classification
        )
        if not engine_match:
            mismatch_count += 1

        if event.materialization_status != "on_disk":
            results.append(
                EventVerificationResult(
                    event_id=event.event_id,
                    case_id=event.case_id,
                    verified=engine_match,
                    engine_match=engine_match,
                    detail=""
                    if engine_match
                    else (
                        f"engine {inferred.granted_codes}/{inferred.classification} "
                        f"!= frozen {event.expected_codes}/{event.expected_classification}"
                    ),
                )
            )
            continue

        on_disk_count += 1
        if reviewed_root is None:
            results.append(
                EventVerificationResult(
                    event_id=event.event_id,
                    case_id=event.case_id,
                    verified=False,
                    engine_match=engine_match,
                    detail="missing reviewed source root",
                )
            )
            continue

        source_path = reviewed_root / event.source_relative_path
        if not source_path.is_file():
            results.append(
                EventVerificationResult(
                    event_id=event.event_id,
                    case_id=event.case_id,
                    verified=False,
                    missing_file=True,
                    engine_match=engine_match,
                    detail=f"missing file: {source_path}",
                )
            )
            continue

        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        hash_match = digest == event.source_sha256
        text = source_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        missing_quotes: list[str] = []
        for span in event.spans:
            if span.line > len(lines) or span.quote not in lines[span.line - 1]:
                if span.quote not in text:
                    missing_quotes.append(span.quote)
        verified = hash_match and not missing_quotes and engine_match
        if verified:
            verified_count += 1
        detail_parts: list[str] = []
        if not hash_match:
            detail_parts.append(f"digest={digest}")
        if not engine_match:
            detail_parts.append(
                f"engine {inferred.granted_codes}/{inferred.classification} "
                f"!= frozen {event.expected_codes}/{event.expected_classification}"
            )
        results.append(
            EventVerificationResult(
                event_id=event.event_id,
                case_id=event.case_id,
                verified=verified,
                hash_match=hash_match,
                engine_match=engine_match,
                missing_quotes=tuple(missing_quotes),
                detail="; ".join(detail_parts),
            )
        )

    return DirectInferenceVerificationReport(
        study_id=table.study_id,
        protocol_version=table.protocol_version,
        total_events=len(table.events),
        on_disk_events=on_disk_count,
        verified_on_disk_events=verified_count,
        engine_mismatches=mismatch_count,
        results=tuple(results),
    )


def write_direct_inference_report(report: DirectInferenceVerificationReport, path: Path) -> None:
    """Write a verification receipt as indented JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
