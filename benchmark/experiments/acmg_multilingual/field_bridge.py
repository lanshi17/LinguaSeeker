"""Source-grounded catalog-field bridge for Stage-0 direct inference.

The rule engine consumes hand-filled facts. This module records which product
catalog field_ids those facts correspond to, and verifies the supporting quotes
(or required absences) against reviewed ``source.md`` files. It is not a live
extractor re-run and does not write ``assigned_acmg_codes``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .canonical_alleles import (
    CanonicalAlleleRegistry,
    EventAlleleBinding,
    assert_event_bindings,
    load_canonical_allele_registry,
)
from .direct_inference import (
    DirectInferenceEvent,
    DirectInferenceTable,
    load_direct_inference_table,
)

DEFAULT_FACTS_PATH = Path(__file__).with_name("field_bridge_facts.json")

Presence = Literal["present", "absent"]
_HASH_CHARS = frozenset("0123456789abcdef")

# Closed subset of backend/src/core/evidence_extraction/domain/catalog.py.
# A test asserts these ids still exist in EVIDENCE_FIELD_SPECS.
GATE_FIELD_IDS = frozenset(
    {
        "A.variant_hgvs_c",
        "A.variant_hgvs_p",
        "A.variant_type",
        "A.functional_domain_or_hotspot",
        "B.disease_diagnosis",
        "C.de_novo_status",
        "C.maternal_genotype",
        "C.paternal_genotype",
        "C.parentage_confirmed",
    }
)

DEFAULT_PARENTAGE_PATTERNS = (
    "亲子鉴定",
    "亲权鉴定",
    "STR分型",
    "paternity test",
    "maternity test",
    "parentage confirmation",
    "parentage confirmed",
    "identity testing",
    "biological parentage",
    "trio identity",
)


class FieldSpan(BaseModel):
    """One line-anchored quote that a present catalog field must match."""

    model_config = ConfigDict(frozen=True)

    line: int = Field(ge=1)
    quote: str = Field(min_length=1)
    language: str = Field(min_length=2, max_length=16)


class FieldFact(BaseModel):
    """One catalog field for one inference event, grounded in source or marked absent."""

    model_config = ConfigDict(frozen=True)

    field_id: str = Field(min_length=3)
    presence: Presence
    expected_value: str = ""
    spans: tuple[FieldSpan, ...] = ()
    notes: str = ""

    @model_validator(mode="after")
    def validate_fact(self) -> FieldFact:
        """Present fields need a quote; absent fields must not invent one."""
        if self.field_id not in GATE_FIELD_IDS:
            raise ValueError(f"{self.field_id}: not a frozen gate field")
        if self.presence == "present":
            if not self.spans:
                raise ValueError(f"{self.field_id}: present fields require at least one span")
            if not self.expected_value:
                raise ValueError(f"{self.field_id}: present fields require expected_value")
        elif self.spans:
            raise ValueError(f"{self.field_id}: absent fields must not carry spans")
        return self


class FieldBridgeEvent(BaseModel):
    """Catalog-field facts for one on-disk inference event."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    fields: tuple[FieldFact, ...]

    @model_validator(mode="after")
    def validate_event(self) -> FieldBridgeEvent:
        """Reject duplicate field_ids inside one event."""
        field_ids = [fact.field_id for fact in self.fields]
        if len(set(field_ids)) != len(field_ids):
            raise ValueError(f"{self.event_id}: field_id values must be unique")
        if not self.fields:
            raise ValueError(f"{self.event_id}: field bridge event must list at least one field")
        return self


class FieldBridgeTable(BaseModel):
    """Frozen source-shadow audit over catalog fields used by the rule engine."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    protocol_version: str
    created_on: str
    scope_note: str
    parentage_forbidden_patterns: tuple[str, ...]
    events: tuple[FieldBridgeEvent, ...]

    @model_validator(mode="after")
    def validate_table(self) -> FieldBridgeTable:
        """Reject empty tables, duplicate events, and empty parentage scans."""
        if not self.events:
            raise ValueError("field bridge table must contain at least one event")
        event_ids = [event.event_id for event in self.events]
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("event_id values must be unique")
        if not self.parentage_forbidden_patterns:
            raise ValueError("parentage_forbidden_patterns must not be empty")
        return self


class FieldVerificationResult(BaseModel):
    """Outcome of verifying one on-disk field-bridge event."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    verified: bool
    missing_file: bool = False
    hash_match: bool = False
    missing_fields: tuple[str, ...] = ()
    missing_quotes: tuple[str, ...] = ()
    parentage_hits: tuple[str, ...] = ()
    detail: str = ""


class FieldBridgeVerificationReport(BaseModel):
    """Receipt for catalog-field quote and parentage-absence checks."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    protocol_version: str
    total_events: int
    on_disk_events: int
    verified_on_disk_events: int
    allele_mismatches: int
    results: tuple[FieldVerificationResult, ...]


def load_field_bridge_table(path: Path | None = None) -> FieldBridgeTable:
    """Load and validate the frozen field-bridge fact table."""
    payload = json.loads((path or DEFAULT_FACTS_PATH).read_text(encoding="utf-8"))
    return FieldBridgeTable.model_validate(payload)


def required_field_ids(
    event: DirectInferenceEvent,
) -> tuple[str, ...]:
    """Return catalog fields the extractor would have to recover for this event."""
    fields: list[str] = ["A.variant_hgvs_c"]
    codes = event.expected_codes
    if "PM6" in codes:
        fields.extend(
            (
                "C.de_novo_status",
                "C.maternal_genotype",
                "C.paternal_genotype",
                "C.parentage_confirmed",
            )
        )
    if "PVS1" in codes or "PVS1_Moderate" in codes:
        fields.extend(("A.variant_type", "A.variant_hgvs_p"))
    if "PP4" in codes:
        fields.append("B.disease_diagnosis")
    if "PM1" in codes:
        fields.append("A.functional_domain_or_hotspot")
    if event.expected_classification == "excluded":
        fields.append("B.disease_diagnosis")
    unknown = [field_id for field_id in fields if field_id not in GATE_FIELD_IDS]
    if unknown:
        raise ValueError(f"{event.event_id}: required field not in gate set: {unknown}")
    return tuple(dict.fromkeys(fields))


def _quote_missing(_text: str, lines: list[str], span: FieldSpan) -> bool:
    """Return True when the frozen quote is missing from the cited line."""
    if span.line > len(lines):
        return True
    return span.quote not in lines[span.line - 1]


def _parentage_hits(text: str, patterns: tuple[str, ...]) -> tuple[str, ...]:
    """Return forbidden parentage-confirmation phrases found in the source."""
    folded = text.casefold()
    hits = [pattern for pattern in patterns if pattern.casefold() in folded]
    return tuple(hits)


def verify_field_bridge(
    table: FieldBridgeTable,
    inference: DirectInferenceTable,
    registry: CanonicalAlleleRegistry,
    *,
    reviewed_root: Path | None = None,
) -> FieldBridgeVerificationReport:
    """Verify on-disk catalog-field quotes, parentage absence, and allele bindings."""
    bindings = tuple(
        EventAlleleBinding(
            event_id=event.event_id,
            canonical_allele_id=event.canonical_allele_id,
            clinvar_vcv=event.clinvar_vcv,
            clinvar_match=event.clinvar_match,
        )
        for event in inference.events
    )
    allele_mismatches = 0
    try:
        assert_event_bindings(registry, bindings)
    except ValueError:
        allele_mismatches = 1

    by_bridge = {event.event_id: event for event in table.events}
    results: list[FieldVerificationResult] = []
    on_disk_count = 0
    verified_count = 0

    for event in inference.events:
        if event.materialization_status != "on_disk":
            continue
        on_disk_count += 1
        required = required_field_ids(event)
        bridge = by_bridge.get(event.event_id)
        if bridge is None:
            results.append(
                FieldVerificationResult(
                    event_id=event.event_id,
                    verified=False,
                    missing_fields=required,
                    detail="missing field-bridge event",
                )
            )
            continue

        present = {fact.field_id: fact for fact in bridge.fields}
        missing_fields = tuple(field_id for field_id in required if field_id not in present)
        if reviewed_root is None:
            results.append(
                FieldVerificationResult(
                    event_id=event.event_id,
                    verified=False,
                    missing_fields=missing_fields,
                    detail="missing reviewed source root",
                )
            )
            continue

        source_path = reviewed_root / event.source_relative_path
        if not source_path.is_file():
            results.append(
                FieldVerificationResult(
                    event_id=event.event_id,
                    verified=False,
                    missing_file=True,
                    missing_fields=missing_fields,
                    detail=f"missing file: {source_path}",
                )
            )
            continue

        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        hash_match = digest == event.source_sha256
        if len(event.source_sha256) != 64 or any(
            character not in _HASH_CHARS for character in event.source_sha256
        ):
            hash_match = False
        text = source_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        missing_quotes: list[str] = []
        parentage_hits: list[str] = []
        for field_id in required:
            fact = present.get(field_id)
            if fact is None:
                continue
            if fact.presence == "present":
                for span in fact.spans:
                    if _quote_missing(text, lines, span):
                        missing_quotes.append(f"{field_id}:{span.quote}")
            elif field_id == "C.parentage_confirmed":
                parentage_hits.extend(_parentage_hits(text, table.parentage_forbidden_patterns))
            elif fact.presence == "absent":
                continue

        verified = (
            hash_match
            and not missing_fields
            and not missing_quotes
            and not parentage_hits
            and allele_mismatches == 0
        )
        if verified:
            verified_count += 1
        detail_parts: list[str] = []
        if not hash_match:
            detail_parts.append(f"digest={digest}")
        if missing_fields:
            detail_parts.append(f"missing_fields={missing_fields}")
        results.append(
            FieldVerificationResult(
                event_id=event.event_id,
                verified=verified,
                hash_match=hash_match,
                missing_fields=missing_fields,
                missing_quotes=tuple(missing_quotes),
                parentage_hits=tuple(dict.fromkeys(parentage_hits)),
                detail="; ".join(detail_parts),
            )
        )

    return FieldBridgeVerificationReport(
        study_id=table.study_id,
        protocol_version=table.protocol_version,
        total_events=len(table.events),
        on_disk_events=on_disk_count,
        verified_on_disk_events=verified_count,
        allele_mismatches=allele_mismatches,
        results=tuple(results),
    )


def write_field_bridge_report(report: FieldBridgeVerificationReport, path: Path) -> None:
    """Write a verification receipt as indented JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


def load_and_verify_field_bridge(
    *,
    cases_path: Path | None = None,
    alleles_path: Path | None = None,
    facts_path: Path | None = None,
    reviewed_root: Path | None = None,
) -> tuple[FieldBridgeTable, DirectInferenceTable, CanonicalAlleleRegistry, FieldBridgeVerificationReport]:
    """Load the three frozen tables and verify the on-disk field bridge."""
    inference = load_direct_inference_table(cases_path)
    registry = load_canonical_allele_registry(alleles_path)
    table = load_field_bridge_table(facts_path)
    report = verify_field_bridge(
        table,
        inference,
        registry,
        reviewed_root=reviewed_root,
    )
    return table, inference, registry, report
