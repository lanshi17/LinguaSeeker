"""Code-level paired scoring for the ACMG multilingual experiment.

This module consumes blinded, human-reviewed formal decisions. It intentionally
does not inspect pipeline ``assigned_acmg_codes`` because those labels are not
ACMG/AMP adjudications.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .contracts import (
    ACMG_MULTILINGUAL_ARMS,
    ArmCodeRecoveryMetric,
    ArmCriterionDecision,
    ArmDecisionSet,
    BlindedArmAdjudicationPacket,
    BlindedArmDecisionPacket,
    BlindingMap,
    CodeRecoveryReport,
    ExperimentArm,
    ExperimentManifest,
    GoldAdjudicationSet,
    GoldCriterionEvent,
    PairedCodeComparison,
    ReviewPacketEvidenceArtifact,
)


@dataclass(frozen=True)
class ArmDecisionIndex:
    """Private lookup structure for one complete set of arm decisions."""

    by_arm: Mapping[ExperimentArm, Mapping[str, ArmCriterionDecision]]


def fingerprint_manifest(manifest: ExperimentManifest) -> str:
    """Return a stable hash used to bind gold and arm decisions to a manifest."""
    payload = json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_manifest(path: Path) -> ExperimentManifest:
    """Load one frozen experiment manifest from JSON."""
    return ExperimentManifest.model_validate_json(path.read_text(encoding="utf-8"))


def load_gold_adjudication(path: Path) -> GoldAdjudicationSet:
    """Load a frozen, independent code-level gold adjudication file."""
    return GoldAdjudicationSet.model_validate_json(path.read_text(encoding="utf-8"))


def load_arm_decisions(path: Path) -> ArmDecisionSet:
    """Load one unblinded arm decision set for internal analysis or tests."""
    return ArmDecisionSet.model_validate_json(path.read_text(encoding="utf-8"))


def load_blinded_packet(path: Path) -> BlindedArmDecisionPacket:
    """Load a reviewer packet and verify all of its neutral evidence artifacts."""
    if _path_contains_experimental_arm_label(path):
        raise ValueError("reviewer packet path contains an experimental arm label")
    packet = BlindedArmDecisionPacket.model_validate_json(path.read_text(encoding="utf-8"))
    _validate_opaque_packet_payload(packet)
    _validate_packet_evidence_files(
        review_packet_id=packet.review_packet_id,
        evidence_artifacts=packet.evidence_artifacts,
        packet_root=path.parent,
    )
    return packet


def load_blinded_adjudication_packet(path: Path) -> BlindedArmAdjudicationPacket:
    """Load a completed neutral adjudication packet and verify its evidence files."""
    if _path_contains_experimental_arm_label(path):
        raise ValueError("adjudication packet path contains an experimental arm label")
    packet = BlindedArmAdjudicationPacket.model_validate_json(path.read_text(encoding="utf-8"))
    _validate_opaque_packet_payload(packet)
    _validate_packet_evidence_files(
        review_packet_id=packet.review_packet_id,
        evidence_artifacts=packet.evidence_artifacts,
        packet_root=path.parent,
    )
    return packet


def load_blinding_map(path: Path) -> BlindingMap:
    """Load the coordinator-only packet-to-arm association."""
    return BlindingMap.model_validate_json(path.read_text(encoding="utf-8"))


def fingerprint_reviewer_evidence(
    evidence_artifacts: tuple[ReviewPacketEvidenceArtifact, ...],
) -> str:
    """Return the stable identity of the evidence files attached to one packet."""
    payload = json.dumps(
        [artifact.model_dump(mode="json") for artifact in evidence_artifacts],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def unblind_decision_packets(
    manifest: ExperimentManifest,
    blinding_map: BlindingMap,
    adjudication_packets: tuple[BlindedArmAdjudicationPacket, ...],
) -> tuple[ArmDecisionSet, ...]:
    """Convert three completed neutral adjudications into arm-labelled decision sets."""
    manifest_sha256 = fingerprint_manifest(manifest)
    if blinding_map.study_id != manifest.study_id:
        raise ValueError("blinding map study_id does not match manifest")
    if blinding_map.manifest_sha256 != manifest_sha256:
        raise ValueError("blinding map manifest_sha256 does not match manifest")

    map_entry_by_packet_id = {
        entry.review_packet_id: entry
        for entry in blinding_map.entries
    }
    packet_by_id: dict[str, BlindedArmAdjudicationPacket] = {}
    for packet in adjudication_packets:
        _validate_opaque_packet_payload(packet)
        if packet.study_id != manifest.study_id:
            raise ValueError(f"{packet.review_packet_id}: adjudication packet study_id does not match manifest")
        if packet.manifest_sha256 != manifest_sha256:
            raise ValueError(f"{packet.review_packet_id}: adjudication packet manifest_sha256 does not match manifest")
        if not packet.is_complete:
            raise ValueError(f"{packet.review_packet_id}: adjudication packet is incomplete")
        if packet.review_panel != blinding_map.review_panel:
            raise ValueError(f"{packet.review_packet_id}: adjudication review panel does not match sealed map")
        if packet.review_packet_id in packet_by_id:
            raise ValueError(f"Duplicate adjudication packet: {packet.review_packet_id}")
        packet_by_id[packet.review_packet_id] = packet

    expected_packet_ids = set(map_entry_by_packet_id)
    received_packet_ids = set(packet_by_id)
    if expected_packet_ids != received_packet_ids:
        missing_packet_ids = ", ".join(sorted(expected_packet_ids - received_packet_ids))
        unexpected_packet_ids = ", ".join(sorted(received_packet_ids - expected_packet_ids))
        descriptions = tuple(
            description
            for description in (
                f"missing: {missing_packet_ids}" if missing_packet_ids else "",
                f"unexpected: {unexpected_packet_ids}" if unexpected_packet_ids else "",
            )
            if description
        )
        raise ValueError("adjudication packets do not match blinding map (" + "; ".join(descriptions) + ")")

    expected_case_ids = {
        entry.case_id
        for entry in manifest.entries
        if entry.status == "ready"
    }
    for review_packet_id, packet in packet_by_id.items():
        map_entry = map_entry_by_packet_id[review_packet_id]
        packet_case_ids = {artifact.case_id for artifact in packet.evidence_artifacts}
        if packet_case_ids != expected_case_ids:
            raise ValueError(f"{review_packet_id}: packet evidence does not cover every ready case")
        actual_evidence_sha256 = fingerprint_reviewer_evidence(packet.evidence_artifacts)
        if actual_evidence_sha256 != map_entry.evidence_manifest_sha256:
            raise ValueError(f"{review_packet_id}: packet evidence does not match the sealed blinding map")

    packet_by_arm = {
        map_entry.arm: packet_by_id[map_entry.review_packet_id]
        for map_entry in blinding_map.entries
    }
    return tuple(
        ArmDecisionSet(
            study_id=manifest.study_id,
            manifest_sha256=manifest_sha256,
            arm=arm,
            review_panel=blinding_map.review_panel,
            is_complete=True,
            decisions=packet_by_arm[arm].decisions,
        )
        for arm in ACMG_MULTILINGUAL_ARMS
    )


def _validate_packet_evidence_files(
    *,
    review_packet_id: str,
    evidence_artifacts: tuple[ReviewPacketEvidenceArtifact, ...],
    packet_root: Path,
) -> None:
    """Verify that a packet still points to the exact neutral result files it declares."""
    resolved_packet_root = packet_root.resolve()
    for artifact in evidence_artifacts:
        evidence_path = (resolved_packet_root / artifact.relative_path).resolve()
        if not evidence_path.is_relative_to(resolved_packet_root):
            raise ValueError(f"{review_packet_id}: evidence artifact escapes reviewer packet root")
        if not evidence_path.is_file():
            raise FileNotFoundError(evidence_path)
        content = evidence_path.read_bytes()
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if actual_sha256 != artifact.sha256:
            raise ValueError(f"{review_packet_id}: evidence artifact SHA-256 does not match packet")
        _validate_neutral_reviewer_evidence(content, evidence_path)


def _validate_neutral_reviewer_evidence(content: bytes, path: Path) -> None:
    """Reject a corrupted or arm-labelled result before it reaches the scorer."""
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Reviewer evidence must be a UTF-8 JSON object: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Reviewer evidence must be a JSON object: {path}")
    if _contains_experimental_arm_label(payload):
        raise ValueError(f"Reviewer evidence contains an experimental arm label: {path}")


def _contains_experimental_arm_label(value: object) -> bool:
    """Detect a label that would reveal an arm from an otherwise neutral packet."""
    if isinstance(value, str):
        return any(arm in value for arm in ACMG_MULTILINGUAL_ARMS)
    if isinstance(value, list):
        return any(_contains_experimental_arm_label(item) for item in value)
    if isinstance(value, dict):
        return any(
            _contains_experimental_arm_label(key) or _contains_experimental_arm_label(item)
            for key, item in value.items()
        )
    return False


def _path_contains_experimental_arm_label(path: Path) -> bool:
    """Reject a reviewer-visible path that discloses an experimental arm."""
    return any(
        arm in path_part
        for path_part in path.resolve().parts
        for arm in ACMG_MULTILINGUAL_ARMS
    )


def _validate_opaque_packet_payload(
    packet: BlindedArmDecisionPacket | BlindedArmAdjudicationPacket,
) -> None:
    """Reject packet metadata or reviewer notes that reveal an arm allocation."""
    if _contains_experimental_arm_label(packet.model_dump(mode="json")):
        raise ValueError("reviewer packet metadata contains an experimental arm label")


def evaluate_code_recovery(
    manifest: ExperimentManifest,
    gold: GoldAdjudicationSet,
    arm_decision_sets: tuple[ArmDecisionSet, ...],
) -> CodeRecoveryReport:
    """Score all three arms against the frozen source-grounded gold set.

    A true positive requires the exact qualified formal criterion, not merely a
    field label or a matching criterion family. Each source family occurs once
    in the manifest, so the report's denominator is already deduplicated at
    the source-family level.
    """
    manifest_sha256 = fingerprint_manifest(manifest)
    _validate_gold(manifest, gold, manifest_sha256)
    decision_index = _index_decisions(manifest, arm_decision_sets, manifest_sha256)
    event_by_id = {event.event_id: event for event in gold.events}
    _validate_gold_event_membership(manifest, tuple(event_by_id.values()))
    for arm in ACMG_MULTILINGUAL_ARMS:
        _validate_decision_coverage(
            arm=arm,
            events=tuple(event_by_id.values()),
            decisions=decision_index.by_arm[arm],
        )
    _validate_arm_source_span_artifacts(decisions_by_arm=decision_index.by_arm)
    ready_source_family_count = sum(entry.status == "ready" for entry in manifest.entries)

    metrics = tuple(
        _calculate_arm_metric(
            arm=arm,
            source_family_count=ready_source_family_count,
            events=tuple(event_by_id.values()),
            decisions=decision_index.by_arm[arm],
        )
        for arm in ACMG_MULTILINGUAL_ARMS
    )
    comparisons = (
        _build_paired_comparison(
            baseline_arm="english_pivot",
            comparison_arm="native_only",
            events=tuple(event_by_id.values()),
            decisions_by_arm=decision_index.by_arm,
        ),
        _build_paired_comparison(
            baseline_arm="english_pivot",
            comparison_arm="dual_track",
            events=tuple(event_by_id.values()),
            decisions_by_arm=decision_index.by_arm,
        ),
        _build_paired_comparison(
            baseline_arm="native_only",
            comparison_arm="dual_track",
            events=tuple(event_by_id.values()),
            decisions_by_arm=decision_index.by_arm,
        ),
    )
    return CodeRecoveryReport(
        study_id=manifest.study_id,
        manifest_sha256=manifest_sha256,
        metrics=metrics,
        comparisons=comparisons,
    )


def write_code_recovery_report(report: CodeRecoveryReport, path: Path) -> None:
    """Write a deterministic JSON report without exposing a bare-dict API."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    path.write_text(payload + "\n", encoding="utf-8")


def _validate_gold(manifest: ExperimentManifest, gold: GoldAdjudicationSet, manifest_sha256: str) -> None:
    """Reject a gold file that does not belong to this frozen study input."""
    if gold.study_id != manifest.study_id:
        raise ValueError("gold study_id does not match manifest")
    if gold.manifest_sha256 != manifest_sha256:
        raise ValueError("gold manifest_sha256 does not match manifest")
    if not gold.is_complete:
        raise ValueError("gold adjudication is incomplete")


def _index_decisions(
    manifest: ExperimentManifest,
    arm_decision_sets: tuple[ArmDecisionSet, ...],
    manifest_sha256: str,
) -> ArmDecisionIndex:
    """Validate complete arm coverage and index decisions by event identifier."""
    indexed: dict[ExperimentArm, dict[str, ArmCriterionDecision]] = {}
    for decision_set in arm_decision_sets:
        if decision_set.study_id != manifest.study_id:
            raise ValueError(f"{decision_set.arm}: study_id does not match manifest")
        if decision_set.manifest_sha256 != manifest_sha256:
            raise ValueError(f"{decision_set.arm}: manifest_sha256 does not match manifest")
        if not decision_set.is_complete:
            raise ValueError(f"{decision_set.arm}: decision set is incomplete")
        if decision_set.arm in indexed:
            raise ValueError(f"Duplicate arm decision set: {decision_set.arm}")
        indexed[decision_set.arm] = {decision.event_id: decision for decision in decision_set.decisions}
    if set(indexed) != set(ACMG_MULTILINGUAL_ARMS):
        raise ValueError("arm decision sets must contain all three experimental arms")
    return ArmDecisionIndex(by_arm=indexed)


def _validate_gold_event_membership(
    manifest: ExperimentManifest,
    events: tuple[GoldCriterionEvent, ...],
) -> None:
    """Ensure gold events target their frozen ready assertion and planned family."""
    ready_entries = tuple(entry for entry in manifest.entries if entry.status == "ready")
    entries_by_assertion_id = {
        entry.index_assertion.assertion_id: entry
        for entry in ready_entries
        if entry.index_assertion is not None
    }
    expected_event_keys = {
        (entry.index_assertion.assertion_id, entry.source_family_id, criterion_family)
        for entry in ready_entries
        if entry.index_assertion is not None
        for criterion_family in entry.index_assertion.planned_criterion_families
    }
    actual_event_keys: set[tuple[str, str, str]] = set()
    for event in events:
        entry = entries_by_assertion_id.get(event.assertion_id)
        if entry is None:
            raise ValueError(f"Gold event {event.event_id} has an unknown assertion_id")
        if event.source_family_id != entry.source_family_id:
            raise ValueError(f"Gold event {event.event_id} does not belong to its assertion source family")
        if entry.index_assertion is None:
            raise ValueError(f"Gold event {event.event_id} has no ready index assertion")
        if event.criterion_family not in entry.index_assertion.planned_criterion_families:
            raise ValueError(f"Gold event {event.event_id} uses an unplanned criterion family")
        actual_event_keys.add((event.assertion_id, event.source_family_id, event.criterion_family))
    missing_event_keys = expected_event_keys - actual_event_keys
    if missing_event_keys:
        missing_descriptions = ", ".join(
            "/".join(event_key) for event_key in sorted(missing_event_keys)
        )
        raise ValueError("Gold adjudication is missing planned criterion events: " + missing_descriptions)


def _calculate_arm_metric(
    *,
    arm: ExperimentArm,
    source_family_count: int,
    events: tuple[GoldCriterionEvent, ...],
    decisions: Mapping[str, ArmCriterionDecision],
) -> ArmCodeRecoveryMetric:
    """Calculate exact formal-code P/R/F1 for one arm."""
    true_positive_count = 0
    false_positive_count = 0
    false_negative_count = 0
    positive_event_count = 0
    for event in events:
        decision = decisions[event.event_id]
        is_correct_qualified = _is_exact_qualified_recovery(event, decision)
        if event.outcome == "qualified":
            positive_event_count += 1
            if is_correct_qualified:
                true_positive_count += 1
            else:
                false_negative_count += 1
                if decision.outcome == "qualified":
                    false_positive_count += 1
        elif decision.outcome == "qualified":
            false_positive_count += 1
    precision = _ratio(true_positive_count, true_positive_count + false_positive_count)
    recall = _ratio(true_positive_count, positive_event_count)
    f1 = _ratio(
        2 * true_positive_count,
        2 * true_positive_count + false_positive_count + false_negative_count,
    )
    return ArmCodeRecoveryMetric(
        arm=arm,
        source_family_count=source_family_count,
        positive_event_count=positive_event_count,
        true_positive_count=true_positive_count,
        false_positive_count=false_positive_count,
        false_negative_count=false_negative_count,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def _validate_decision_coverage(
    *,
    arm: ExperimentArm,
    events: tuple[GoldCriterionEvent, ...],
    decisions: Mapping[str, ArmCriterionDecision],
) -> None:
    """Reject extra, missing, or mismatched criterion-family decisions."""
    event_by_id = {event.event_id: event for event in events}
    extra_ids = sorted(set(decisions) - set(event_by_id))
    missing_ids = sorted(set(event_by_id) - set(decisions))
    if extra_ids:
        raise ValueError(f"{arm}: decisions reference unknown events: {', '.join(extra_ids)}")
    if missing_ids:
        raise ValueError(f"{arm}: decisions missing events: {', '.join(missing_ids)}")
    for event_id, decision in decisions.items():
        if decision.criterion_family != event_by_id[event_id].criterion_family:
            raise ValueError(f"{arm}: criterion family mismatch for {event_id}")


def _validate_arm_source_span_artifacts(
    *,
    decisions_by_arm: Mapping[ExperimentArm, Mapping[str, ArmCriterionDecision]],
) -> None:
    """Keep formal arm adjudication anchored only to its frozen input artifact."""
    for arm, decisions in decisions_by_arm.items():
        for decision in decisions.values():
            if decision.outcome != "qualified":
                continue
            for source_span in decision.source_spans:
                if not _arm_allows_source_artifact(arm, source_span.artifact_track):
                    raise ValueError(
                        f"{arm}: {decision.event_id} cites {source_span.artifact_track!r} artifact, "
                        "which is not visible in this arm"
                    )


def _arm_allows_source_artifact(
    arm: ExperimentArm,
    artifact_track: str,
) -> bool:
    """Return whether a frozen input artifact is visible to a study arm."""
    if arm == "english_pivot":
        return artifact_track == "translated"
    if arm == "native_only":
        return artifact_track == "original"
    return artifact_track in {"original", "translated"}


def _build_paired_comparison(
    *,
    baseline_arm: ExperimentArm,
    comparison_arm: ExperimentArm,
    events: tuple[GoldCriterionEvent, ...],
    decisions_by_arm: Mapping[ExperimentArm, Mapping[str, ArmCriterionDecision]],
) -> PairedCodeComparison:
    """Build paired recovery counts over gold-positive formal-code events only."""
    baseline_only: list[str] = []
    comparison_only: list[str] = []
    both = 0
    neither = 0
    for event in events:
        if event.outcome != "qualified":
            continue
        baseline_recovered = _is_exact_qualified_recovery(event, decisions_by_arm[baseline_arm][event.event_id])
        comparison_recovered = _is_exact_qualified_recovery(event, decisions_by_arm[comparison_arm][event.event_id])
        if baseline_recovered and comparison_recovered:
            both += 1
        elif baseline_recovered:
            baseline_only.append(event.event_id)
        elif comparison_recovered:
            comparison_only.append(event.event_id)
        else:
            neither += 1
    return PairedCodeComparison(
        baseline_arm=baseline_arm,
        comparison_arm=comparison_arm,
        positive_event_count=both + neither + len(baseline_only) + len(comparison_only),
        baseline_only_count=len(baseline_only),
        comparison_only_count=len(comparison_only),
        both_recovered_count=both,
        neither_recovered_count=neither,
        comparison_only_event_ids=tuple(comparison_only),
        baseline_only_event_ids=tuple(baseline_only),
    )


def _is_exact_qualified_recovery(event: GoldCriterionEvent, decision: ArmCriterionDecision) -> bool:
    """Return whether a decision reproduces the gold criterion exactly."""
    return (
        event.outcome == "qualified"
        and decision.outcome == "qualified"
        and decision.criterion == event.criterion
        and decision.strength == event.strength
    )


def _ratio(numerator: float, denominator: float) -> float:
    """Return a rounded unit-interval metric, including the empty-set case."""
    return round(numerator / denominator, 4) if denominator else 0.0
