"""Live extraction probe: did span recovery fill catalog gates the LLM missed?

This is not Stage-1 scoring and does not write ``assigned_acmg_codes``.
"""

from __future__ import annotations

import html
import re
import time
from collections.abc import Sequence
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.core.standardize_entities_and_align_knowledge.hgvs_normalizer import canonical_protein_hgvs

from .direct_inference import (
    DirectInferenceEvent,
    DirectInferenceTable,
    Mecp2VcepSlice,
    infer_event,
    load_direct_inference_table,
)
from .field_bridge import FieldBridgeEvent, FieldBridgeTable, FieldFact, load_field_bridge_table

DEFAULT_PROBE_EVENT_IDS = (
    "rett_007_case2_R180X",
    "rett_011_P237R",
)
_CRITERION_TOKEN_RE = re.compile(
    r"\b(?:PVS1|PS[1-4]|PM[1-6]|PP[1-5]|BA1|BS[1-4]|BP[1-7])\b",
    re.IGNORECASE,
)
_ABSENT_PARENTAGE_VALUES = frozenset(
    {"not_confirmed", "false", "absent", "unconfirmed", "no", "not confirmed"}
)
_LOF_VARIANT_CLASSES = frozenset({"nonsense", "frameshift"})
_DISEASE_ALIASES = {
    "rett综合征": "rettsyndrome",
    "rett綜合徵": "rettsyndrome",
    "синдромретта": "rettsyndrome",
}


class FieldOrigin(str, Enum):
    """Where a final catalog value came from relative to the pre-recovery snapshot."""

    LLM = "llm"
    RECOVERED = "recovered"
    NORMALIZED = "normalized"
    MISSING = "missing"


class LiveExtractionService(Protocol):
    """Minimum product facade needed by the probe."""

    async def run(self, document: object) -> object:
        """Run production extraction on one track document."""


class GateObservation(BaseModel):
    """One field-bridge gate compared against LLM snapshot and final output."""

    model_config = ConfigDict(frozen=True)

    field_id: str
    gold_presence: str
    gold_expected_value: str
    llm_value: str | None = None
    final_value: str | None = None
    origin: FieldOrigin
    matches_gold: bool


class LiveEngineComparison(BaseModel):
    """Shadow rule-engine output if live FOUND gates replaced frozen facts.

    This does not write product ``assigned_acmg_codes``.
    """

    model_config = ConfigDict(frozen=True)

    frozen_codes: tuple[str, ...] = ()
    frozen_classification: str = ""
    live_codes: tuple[str, ...] = ()
    live_classification: str = ""
    live_reason: str = ""
    degraded_field_ids: tuple[str, ...] = ()
    classification_changed: bool = False


class EventProbeResult(BaseModel):
    """Live extraction outcome for one on-disk inference event."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    paper_hgvs_c: str
    status: str
    elapsed_seconds: float = Field(ge=0.0)
    assigned_acmg_codes: tuple[str, ...] = ()
    author_criterion_tokens: tuple[str, ...] = ()
    recovered_field_ids: tuple[str, ...] = ()
    llm_found_field_ids: tuple[str, ...] = ()
    gates: tuple[GateObservation, ...] = ()
    engine: LiveEngineComparison | None = None


class LiveExtractionProbeReport(BaseModel):
    """Receipt for one live probe batch."""

    model_config = ConfigDict(frozen=True)

    created_on: str
    fast_model: str
    reasoning_model: str
    events: tuple[EventProbeResult, ...]
    recovered_gate_count: int = Field(ge=0)
    llm_gate_count: int = Field(ge=0)
    normalized_gate_count: int = Field(ge=0)
    missing_gate_count: int = Field(ge=0)


def found_field_values(items: Sequence[object]) -> dict[str, str]:
    """Return the first FOUND field_id → string value mapping."""
    values: dict[str, str] = {}
    for item in items:
        status = getattr(item, "status", None)
        status_value = getattr(status, "value", status)
        if str(status_value) != "found":
            continue
        field_id = str(getattr(item, "field_id", ""))
        if not field_id or field_id in values:
            continue
        raw = getattr(item, "value", None)
        if raw is None:
            continue
        if isinstance(raw, list):
            text = "; ".join(str(part) for part in raw if str(part).strip())
        else:
            text = str(raw).strip()
        if text:
            values[field_id] = text
    return values


def classify_field_origin(llm_value: str | None, final_value: str | None) -> FieldOrigin:
    """Classify a gate as LLM-filled, recovery-added, normalized, or still missing."""
    if final_value is None:
        return FieldOrigin.MISSING
    if llm_value is None:
        return FieldOrigin.RECOVERED
    if _compact(llm_value) != _compact(final_value):
        return FieldOrigin.NORMALIZED
    return FieldOrigin.LLM


def gate_matches_gold(fact: FieldFact, value: str | None) -> bool:
    """Compare an extracted value against one frozen field-bridge fact."""
    if fact.presence == "absent":
        if value is None:
            return True
        return value.strip().casefold() in _ABSENT_PARENTAGE_VALUES
    if value is None:
        return False
    expected = fact.expected_value.strip()
    observed = str(value).strip()
    if expected == "de_novo_unconfirmed":
        return observed.casefold() in {"de_novo", "de_novo_unconfirmed"}
    if expected == "target_absent":
        folded = observed.casefold()
        return (
            "target_absent" in folded
            or "未检测" in observed
            or "未携带" in observed
            or "均无" in observed
        )
    if fact.field_id in {"A.variant_hgvs_c", "A.variant_hgvs_p"}:
        expected_protein = canonical_protein_hgvs(expected)
        observed_protein = canonical_protein_hgvs(observed)
        if expected_protein and observed_protein and expected_protein == observed_protein:
            return True
    expected_key = _DISEASE_ALIASES.get(_compact(expected), _compact(expected))
    observed_key = _DISEASE_ALIASES.get(_compact(observed), _compact(observed))
    return expected_key in observed_key or observed_key in expected_key


def collect_assigned_acmg_codes(items: Sequence[object]) -> tuple[str, ...]:
    """Collect granted ACMG tokens that extraction is supposed to leave empty."""
    codes: list[str] = []
    for item in items:
        for code in getattr(item, "assigned_acmg_codes", ()) or ():
            token = str(code).strip().upper()
            if token and token not in codes:
                codes.append(token)
    return tuple(codes)


def collect_author_criterion_tokens(items: Sequence[object]) -> tuple[str, ...]:
    """Collect ACMG tokens that still appear in values or notes."""
    tokens: list[str] = []
    for item in items:
        blob = f"{getattr(item, 'value', '')} {getattr(item, 'notes', '')}"
        for match in _CRITERION_TOKEN_RE.findall(blob):
            token = match.upper()
            if token not in tokens:
                tokens.append(token)
    return tuple(tokens)


def observe_gates(
    facts: Sequence[FieldFact],
    llm_values: dict[str, str],
    final_values: dict[str, str],
) -> tuple[GateObservation, ...]:
    """Build per-gate observations for one event."""
    observations: list[GateObservation] = []
    for fact in facts:
        llm_value = llm_values.get(fact.field_id)
        final_value = final_values.get(fact.field_id)
        origin = classify_field_origin(llm_value, final_value)
        observations.append(
            GateObservation(
                field_id=fact.field_id,
                gold_presence=fact.presence,
                gold_expected_value=fact.expected_value,
                llm_value=llm_value,
                final_value=final_value,
                origin=origin,
                matches_gold=gate_matches_gold(fact, final_value),
            )
        )
    return tuple(observations)


def overlay_event_with_live_gates(
    event: DirectInferenceEvent,
    gates: Sequence[GateObservation],
) -> DirectInferenceEvent:
    """Degrade frozen engine inputs when a field-bridge gate missed gold."""
    by_id = {gate.field_id: gate for gate in gates}
    updates: dict[str, object] = {}

    def matched(field_id: str) -> bool | None:
        gate = by_id.get(field_id)
        if gate is None:
            return None
        return gate.matches_gold

    if matched("C.maternal_genotype") is False or matched("C.paternal_genotype") is False:
        updates["parents_negative_at_target"] = False
        updates["both_parents_tested"] = False
    if matched("C.de_novo_status") is False:
        updates["inheritance"] = "unknown"
    if matched("C.parentage_confirmed") is False:
        updates["parentage_confirmed"] = True
    if matched("B.disease_diagnosis") is False:
        updates["phenotype_class"] = "other"
    if matched("A.variant_type") is False and event.variant_class in _LOF_VARIANT_CLASSES:
        updates["variant_class"] = "missense"
    if matched("A.functional_domain_or_hotspot") is False and event.variant_class == "missense":
        updates["vcep_protein_position"] = None
    if not updates:
        return event
    return event.model_copy(update=updates)


def compare_live_gates_to_engine(
    event: DirectInferenceEvent,
    gates: Sequence[GateObservation],
    vcep: Mecp2VcepSlice | None = None,
) -> LiveEngineComparison:
    """Run the shadow engine on frozen facts and on live-degraded facts."""
    slice_ = vcep or Mecp2VcepSlice()
    frozen = infer_event(event, slice_)
    live = infer_event(overlay_event_with_live_gates(event, gates), slice_)
    degraded = tuple(gate.field_id for gate in gates if not gate.matches_gold)
    return LiveEngineComparison(
        frozen_codes=tuple(frozen.granted_codes),
        frozen_classification=frozen.classification,
        live_codes=tuple(live.granted_codes),
        live_classification=live.classification,
        live_reason=live.classification_reason,
        degraded_field_ids=degraded,
        classification_changed=live.classification != frozen.classification,
    )


def on_disk_probe_event_ids(table: DirectInferenceTable) -> tuple[str, ...]:
    """Return frozen on-disk event ids in table order."""
    return tuple(
        event.event_id for event in table.events if event.materialization_status == "on_disk"
    )


def build_event_probe_result(
    event: DirectInferenceEvent,
    bridge_event: FieldBridgeEvent,
    *,
    status: str,
    elapsed_seconds: float,
    pre_recovery_items: Sequence[object],
    final_items: Sequence[object],
    vcep: Mecp2VcepSlice | None = None,
) -> EventProbeResult:
    """Compare one live run against the frozen field-bridge gates."""
    llm_values = found_field_values(pre_recovery_items)
    final_values = found_field_values(final_items)
    gates = observe_gates(bridge_event.fields, llm_values, final_values)
    recovered = tuple(gate.field_id for gate in gates if gate.origin is FieldOrigin.RECOVERED)
    llm_found = tuple(gate.field_id for gate in gates if gate.origin is FieldOrigin.LLM)
    return EventProbeResult(
        event_id=event.event_id,
        paper_hgvs_c=event.paper_hgvs_c,
        status=status,
        elapsed_seconds=round(elapsed_seconds, 2),
        assigned_acmg_codes=collect_assigned_acmg_codes(final_items),
        author_criterion_tokens=collect_author_criterion_tokens(final_items),
        recovered_field_ids=recovered,
        llm_found_field_ids=llm_found,
        gates=gates,
        engine=compare_live_gates_to_engine(event, gates, vcep),
    )


def build_probe_report(
    event_results: Sequence[EventProbeResult],
    *,
    fast_model: str,
    reasoning_model: str,
    created_on: str | None = None,
) -> LiveExtractionProbeReport:
    """Aggregate per-event observations into one probe receipt."""
    gates = [gate for result in event_results for gate in result.gates]
    return LiveExtractionProbeReport(
        created_on=created_on or date.today().isoformat(),
        fast_model=fast_model,
        reasoning_model=reasoning_model,
        events=tuple(event_results),
        recovered_gate_count=sum(gate.origin is FieldOrigin.RECOVERED for gate in gates),
        llm_gate_count=sum(gate.origin is FieldOrigin.LLM for gate in gates),
        normalized_gate_count=sum(gate.origin is FieldOrigin.NORMALIZED for gate in gates),
        missing_gate_count=sum(gate.origin is FieldOrigin.MISSING for gate in gates),
    )


def write_live_extraction_probe_report(report: LiveExtractionProbeReport, path: Path) -> None:
    """Write the probe receipt as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


class ProbeScorecard(BaseModel):
    """Rescored FOUND count and gold-match count for one probe receipt."""

    model_config = ConfigDict(frozen=True)

    event_count: int = Field(ge=0)
    total_gates: int = Field(ge=0)
    found_gates: int = Field(ge=0)
    matched_gates: int = Field(ge=0)
    assigned_acmg_code_events: int = Field(ge=0)

    @property
    def found_rate(self) -> float:
        return self.found_gates / self.total_gates if self.total_gates else 0.0

    @property
    def match_rate(self) -> float:
        return self.matched_gates / self.total_gates if self.total_gates else 0.0


def load_live_extraction_probe_report(path: Path) -> LiveExtractionProbeReport:
    """Load a previously written probe receipt."""
    return LiveExtractionProbeReport.model_validate_json(path.read_text(encoding="utf-8"))


def score_probe_report(report: LiveExtractionProbeReport, facts: FieldBridgeTable) -> ProbeScorecard:
    """Rescore stored final_value fields with the current gold matcher."""
    facts_by_id = {event.event_id: event for event in facts.events}
    found = matched = total = leaks = 0
    for event in report.events:
        if event.assigned_acmg_codes:
            leaks += 1
        bridge = facts_by_id[event.event_id]
        by_field = {fact.field_id: fact for fact in bridge.fields}
        for gate in event.gates:
            total += 1
            if gate.final_value is not None:
                found += 1
            if gate_matches_gold(by_field[gate.field_id], gate.final_value):
                matched += 1
    return ProbeScorecard(
        event_count=len(report.events),
        total_gates=total,
        found_gates=found,
        matched_gates=matched,
        assigned_acmg_code_events=leaks,
    )


def resolve_probe_events(
    table: DirectInferenceTable,
    bridge: FieldBridgeTable,
    event_ids: Sequence[str],
) -> tuple[tuple[DirectInferenceEvent, FieldBridgeEvent], ...]:
    """Resolve requested event ids against the frozen tables."""
    inference_by_id = {event.event_id: event for event in table.events}
    bridge_by_id = {event.event_id: event for event in bridge.events}
    resolved: list[tuple[DirectInferenceEvent, FieldBridgeEvent]] = []
    for event_id in event_ids:
        if event_id not in inference_by_id:
            raise ValueError(f"{event_id}: not in direct_inference_cases.json")
        if event_id not in bridge_by_id:
            raise ValueError(f"{event_id}: not in field_bridge_facts.json")
        resolved.append((inference_by_id[event_id], bridge_by_id[event_id]))
    return tuple(resolved)


def build_probe_document(event: DirectInferenceEvent, source_text: str) -> object:
    """Build a single-track document from a reviewed source.md."""
    from src.core.evidence_extraction.contracts import (
        ContentBlock,
        ExtractionTarget,
        PageSpan,
        Track,
        TrackDocument,
    )

    from src.utils.text_normalize import unescape_mined_text

    source_text = unescape_mined_text(source_text)
    return TrackDocument(
        document_id=event.event_id,
        track=Track.ORIGINAL,
        formatted_text=source_text,
        page_spans=[
            PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(source_text)),
        ],
        blocks=[ContentBlock(type="text", page_idx=0, text=source_text)],
        extraction_target=ExtractionTarget(
            gene_symbol=event.gene,
            disease_name="Rett syndrome",
            variant_hgvs_c=event.paper_hgvs_c,
            variant_hgvs_p=event.paper_hgvs_p,
        ),
    )


def attach_recovery_snapshot(service: object, bucket: list[list[object]]) -> None:
    """Capture evidence items immediately before span recovery."""
    workflow = getattr(service, "_workflow")
    recovery = getattr(workflow, "_target_span_recovery")
    original = recovery.recover

    def recover_with_snapshot(document: object, items: list[object]) -> list[object]:
        bucket.append([item.model_copy(deep=True) for item in items])
        return original(document, items)

    recovery.recover = recover_with_snapshot


async def run_live_extraction_probe(
    service: LiveExtractionService,
    *,
    reviewed_root: Path,
    event_ids: Sequence[str] = DEFAULT_PROBE_EVENT_IDS,
    cases_path: Path | None = None,
    facts_path: Path | None = None,
    fast_model: str = "",
    reasoning_model: str = "",
    report_path: Path | None = None,
) -> LiveExtractionProbeReport:
    """Run production extraction on selected events and score field-bridge gates."""
    table = load_direct_inference_table(cases_path)
    bridge = load_field_bridge_table(facts_path)
    snapshots: list[list[object]] = []
    attach_recovery_snapshot(service, snapshots)
    results: list[EventProbeResult] = []
    for event, bridge_event in resolve_probe_events(table, bridge, event_ids):
        source_path = reviewed_root / event.source_relative_path
        source_text = source_path.read_text(encoding="utf-8")
        document = build_probe_document(event, source_text)
        started = time.perf_counter()
        extraction = await service.run(document)
        elapsed = time.perf_counter() - started
        pre_items = snapshots[-1] if snapshots else []
        final_items = list(getattr(extraction, "evidence_items", []) or [])
        results.append(
            build_event_probe_result(
                event,
                bridge_event,
                status=str(getattr(getattr(extraction, "status", ""), "value", getattr(extraction, "status", ""))),
                elapsed_seconds=elapsed,
                pre_recovery_items=pre_items,
                final_items=final_items,
                vcep=table.vcep,
            )
        )
        if report_path is not None:
            write_live_extraction_probe_report(
                build_probe_report(results, fast_model=fast_model, reasoning_model=reasoning_model),
                report_path,
            )
    return build_probe_report(
        results,
        fast_model=fast_model,
        reasoning_model=reasoning_model,
    )


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", html.unescape(value).casefold())
