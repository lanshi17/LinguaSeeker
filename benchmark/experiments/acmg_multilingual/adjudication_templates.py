"""Create label-masked review packets and a coordinator-only ACMG allocation map."""

from __future__ import annotations

import hashlib
import json
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel

from .contracts import (
    ACMG_MULTILINGUAL_ARMS,
    AdjudicationTemplateReport,
    ArmExtractionRun,
    ArmExtractionRunReport,
    ArmCriterionDecision,
    BlindedAdjudicationTemplateReport,
    BlindedArmAdjudicationPacket,
    BlindedArmDecisionPacket,
    BlindingMap,
    BlindingMapEntry,
    ExperimentArm,
    ExperimentEntry,
    ExperimentManifest,
    GoldAdjudicationSet,
    GoldCriterionEvent,
    GoldReviewerDecisionSet,
    ReviewPanel,
    ReviewPacketEvidenceArtifact,
)
from .materialize import validate_materialized_input_bundle
from .scoring import (
    fingerprint_manifest,
    fingerprint_reviewer_evidence,
    load_blinded_packet,
)


@dataclass(frozen=True)
class PreparedReviewerEvidence:
    """One validated result file held before its neutral packet is written."""

    artifact: ReviewPacketEvidenceArtifact
    content: bytes


@dataclass(frozen=True)
class PreparedReviewerPacket:
    """A coordinator-side arm association that is never written to a reviewer file."""

    arm: ExperimentArm
    study_id: str
    manifest_sha256: str
    review_packet_id: str
    evidence_artifacts: tuple[ReviewPacketEvidenceArtifact, ...]
    decisions: tuple[ArmCriterionDecision, ...]
    evidence: tuple[PreparedReviewerEvidence, ...]


@dataclass(frozen=True)
class CompletedReviewerPacket:
    """One returned reviewer packet together with its verified delivery location."""

    packet: BlindedArmDecisionPacket
    packet_path: Path


@dataclass(frozen=True)
class VerifiedArmRunIndex:
    """Run receipt entries whose on-disk result and input hashes still match."""

    by_case_and_arm: Mapping[tuple[str, ExperimentArm], ArmExtractionRun]


@dataclass(frozen=True)
class CompletedReviewerPacketGroup:
    """The two independent returns for one opaque packet identifier."""

    review_packet_id: str
    packets: tuple[CompletedReviewerPacket, ...]


def create_adjudication_templates(
    manifest: ExperimentManifest,
    *,
    input_root: Path,
    arm_output_root: Path,
    arm_run_report: ArmExtractionRunReport,
    reviewer_output_root: Path,
    gold_reviewer_output_root: Path,
    coordinator_output_root: Path,
    review_panel: ReviewPanel,
) -> AdjudicationTemplateReport:
    """Create independent gold and reviewer templates from completed arm outputs.

    Each independent reviewer receives a separate copy with the same neutral
    packet ID and evidence. The arm association and review panel remain only
    in the separately rooted coordinator blinding map.
    """
    entries = _ready_entries_only(manifest)
    run_index = _verify_arm_run_report(
        manifest=manifest,
        entries=entries,
        input_root=input_root,
        arm_output_root=arm_output_root,
        arm_run_report=arm_run_report,
    )
    _validate_output_roots(
        arm_output_root=arm_output_root,
        reviewer_output_root=reviewer_output_root,
        gold_reviewer_output_root=gold_reviewer_output_root,
        coordinator_output_root=coordinator_output_root,
    )
    manifest_sha256 = fingerprint_manifest(manifest)
    events = tuple(_gold_events(entries))
    prepared_packets = _prepare_reviewer_packets(
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        entries=entries,
        events=events,
        arm_output_root=arm_output_root,
        run_index=run_index,
    )
    gold = GoldAdjudicationSet(
        study_id=manifest.study_id,
        manifest_sha256=manifest_sha256,
        reviewer_ids=review_panel.reviewer_ids,
        review_panel=review_panel,
        is_complete=False,
        events=events,
    )
    blinding_map = BlindingMap(
        study_id=manifest.study_id,
        manifest_sha256=manifest_sha256,
        review_panel=review_panel,
        entries=tuple(
            BlindingMapEntry(
                review_packet_id=prepared.review_packet_id,
                arm=prepared.arm,
                evidence_manifest_sha256=fingerprint_reviewer_evidence(
                    prepared.evidence_artifacts
                ),
            )
            for prepared in prepared_packets
        ),
    )

    reviewer_staging_root = _create_staging_root(reviewer_output_root)
    gold_reviewer_staging_root = _create_staging_root(gold_reviewer_output_root)
    coordinator_staging_root = _create_staging_root(coordinator_output_root)
    reviewer_packet_paths = tuple(
        _write_reviewer_packet(
            prepared=prepared,
            reviewer_id=reviewer_id,
            reviewer_root=reviewer_staging_root / f"reviewer-{reviewer_index:02d}",
        )
        for reviewer_index, reviewer_id in enumerate(review_panel.reviewer_ids, start=1)
        for prepared in prepared_packets
    )
    gold_reviewer_template_paths = tuple(
        _write_gold_reviewer_template(
            study_id=manifest.study_id,
            manifest_sha256=manifest_sha256,
            reviewer_id=reviewer_id,
            events=events,
            reviewer_root=gold_reviewer_staging_root / f"reviewer-{reviewer_index:02d}",
        )
        for reviewer_index, reviewer_id in enumerate(review_panel.reviewer_ids, start=1)
    )
    gold_path = coordinator_staging_root / "gold_adjudication.json"
    blinding_map_path = coordinator_staging_root / "blinding_map.json"
    _write_model(gold, gold_path)
    _write_model(blinding_map, blinding_map_path)
    _publish_staging_roots(
        (
            (reviewer_staging_root, reviewer_output_root),
            (gold_reviewer_staging_root, gold_reviewer_output_root),
            (coordinator_staging_root, coordinator_output_root),
        )
    )
    return AdjudicationTemplateReport(
        study_id=manifest.study_id,
        manifest_sha256=manifest_sha256,
        gold_template_path=coordinator_output_root / "gold_adjudication.json",
        gold_reviewer_template_paths=tuple(
            gold_reviewer_output_root / path.relative_to(gold_reviewer_staging_root)
            for path in gold_reviewer_template_paths
        ),
        reviewer_packet_paths=tuple(
            reviewer_output_root / path.relative_to(reviewer_staging_root)
            for path in reviewer_packet_paths
        ),
        coordinator_blinding_map_path=coordinator_output_root / "blinding_map.json",
    )


def prepare_blinded_adjudication_packets(
    manifest: ExperimentManifest,
    blinding_map: BlindingMap,
    *,
    reviewer_packet_paths: tuple[Path, ...],
    adjudicator_output_root: Path,
) -> BlindedAdjudicationTemplateReport:
    """Create neutral adjudicator packets after both independent arm reviews return."""
    manifest_sha256 = fingerprint_manifest(manifest)
    _validate_adjudication_request(
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        blinding_map=blinding_map,
        reviewer_packet_paths=reviewer_packet_paths,
        adjudicator_output_root=adjudicator_output_root,
    )
    completed_packets = tuple(
        CompletedReviewerPacket(packet=load_blinded_packet(path), packet_path=path)
        for path in reviewer_packet_paths
    )
    packet_groups = _group_completed_reviewer_packets(
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        blinding_map=blinding_map,
        completed_packets=completed_packets,
    )
    packets_by_id = {packet_group.review_packet_id: packet_group for packet_group in packet_groups}

    adjudicator_staging_root = _create_staging_root(adjudicator_output_root)
    adjudication_packet_paths: list[Path] = []
    for blinding_entry in blinding_map.entries:
        reviewer_packets = packets_by_id[blinding_entry.review_packet_id].packets
        packet_by_reviewer_id = {
            completed.packet.reviewer_id: completed
            for completed in reviewer_packets
        }
        ordered_reviewer_packets = tuple(
            packet_by_reviewer_id[reviewer_id]
            for reviewer_id in blinding_map.review_panel.reviewer_ids
        )
        first_packet = ordered_reviewer_packets[0].packet
        adjudication_packet = BlindedArmAdjudicationPacket(
            study_id=manifest.study_id,
            manifest_sha256=manifest_sha256,
            review_packet_id=first_packet.review_packet_id,
            evidence_artifacts=first_packet.evidence_artifacts,
            review_panel=blinding_map.review_panel,
            reviewer_packets=tuple(completed.packet for completed in ordered_reviewer_packets),
            is_complete=False,
            decisions=tuple(
                ArmCriterionDecision(
                    event_id=decision.event_id,
                    criterion_family=decision.criterion_family,
                    outcome="not_assessed",
                )
                for decision in first_packet.decisions
            ),
        )
        _validate_opaque_packet_payload(adjudication_packet)
        adjudication_packet_paths.append(
            _write_adjudication_packet(
                packet=adjudication_packet,
                evidence_source_root=ordered_reviewer_packets[0].packet_path.parent,
                adjudicator_output_root=adjudicator_staging_root,
            )
        )
    _publish_staging_roots(((adjudicator_staging_root, adjudicator_output_root),))
    return BlindedAdjudicationTemplateReport(
        study_id=manifest.study_id,
        manifest_sha256=manifest_sha256,
        adjudication_packet_paths=tuple(
            adjudicator_output_root / path.relative_to(adjudicator_staging_root)
            for path in adjudication_packet_paths
        ),
    )


def _ready_entries_only(manifest: ExperimentManifest) -> tuple[ExperimentEntry, ...]:
    """Reject packet creation before the scientific denominator has been frozen."""
    blockers = tuple(entry.case_id for entry in manifest.entries if entry.status not in {"ready", "excluded"})
    if blockers:
        raise ValueError("Cannot template an incomplete manifest: " + ", ".join(blockers))
    entries = tuple(entry for entry in manifest.entries if entry.status == "ready")
    if not entries:
        raise ValueError("The manifest has no ready entries")
    return entries


def _verify_arm_run_report(
    *,
    manifest: ExperimentManifest,
    entries: tuple[ExperimentEntry, ...],
    input_root: Path,
    arm_output_root: Path,
    arm_run_report: ArmExtractionRunReport,
) -> VerifiedArmRunIndex:
    """Bind every packet source to the result and input hashes recorded at run time."""
    manifest_sha256 = fingerprint_manifest(manifest)
    if arm_run_report.study_id != manifest.study_id:
        raise ValueError("arm run report study_id does not match manifest")
    if arm_run_report.manifest_sha256 != manifest_sha256:
        raise ValueError("arm run report manifest_sha256 does not match manifest")

    expected_keys = {
        (entry.case_id, arm)
        for entry in entries
        for arm in ACMG_MULTILINGUAL_ARMS
    }
    runs_by_key = {(run.case_id, run.arm): run for run in arm_run_report.runs}
    if len(runs_by_key) != len(arm_run_report.runs):
        raise ValueError("arm run report contains duplicate case/arm entries")
    received_keys = set(runs_by_key)
    if received_keys != expected_keys:
        missing_keys = ", ".join(f"{case_id}/{arm}" for case_id, arm in sorted(expected_keys - received_keys))
        unexpected_keys = ", ".join(f"{case_id}/{arm}" for case_id, arm in sorted(received_keys - expected_keys))
        descriptions = tuple(
            description
            for description in (
                f"missing: {missing_keys}" if missing_keys else "",
                f"unexpected: {unexpected_keys}" if unexpected_keys else "",
            )
            if description
        )
        raise ValueError("arm run report does not cover the frozen manifest (" + "; ".join(descriptions) + ")")

    resolved_input_root = input_root.resolve()
    expected_input_dirs: dict[str, Path] = {}
    for entry in entries:
        validate_materialized_input_bundle(entry, resolved_input_root)
        expected_input_dir = (resolved_input_root / entry.case_id).resolve()
        if not expected_input_dir.is_relative_to(resolved_input_root):
            raise ValueError(f"{entry.case_id}: expected input bundle escapes configured root")
        expected_input_dirs[entry.case_id] = expected_input_dir

    resolved_output_root = arm_output_root.resolve()
    for (case_id, arm), run in runs_by_key.items():
        expected_result_path = (resolved_output_root / case_id / arm / "extraction_result.json").resolve()
        if not expected_result_path.is_relative_to(resolved_output_root):
            raise ValueError(f"{case_id}/{arm}: expected arm result escapes output root")
        if run.result_path.resolve() != expected_result_path:
            raise ValueError(f"{case_id}/{arm}: run receipt result path does not match arm output")
        if not expected_result_path.is_file():
            raise FileNotFoundError(expected_result_path)
        if hashlib.sha256(expected_result_path.read_bytes()).hexdigest() != run.result_sha256:
            raise ValueError(f"{case_id}/{arm}: arm result SHA-256 does not match run receipt")

        expected_input_dir = expected_input_dirs[case_id]
        if run.input_dir.resolve() != expected_input_dir:
            raise ValueError(f"{case_id}/{arm}: run receipt input path does not match frozen input root")
        input_manifest_path = expected_input_dir / "input_manifest.json"
        if not input_manifest_path.is_file():
            raise FileNotFoundError(input_manifest_path)
        if hashlib.sha256(input_manifest_path.read_bytes()).hexdigest() != run.input_manifest_sha256:
            raise ValueError(f"{case_id}/{arm}: input manifest SHA-256 does not match run receipt")
    return VerifiedArmRunIndex(by_case_and_arm=runs_by_key)


def _validate_adjudication_request(
    *,
    manifest: ExperimentManifest,
    manifest_sha256: str,
    blinding_map: BlindingMap,
    reviewer_packet_paths: tuple[Path, ...],
    adjudicator_output_root: Path,
) -> None:
    """Reject an incomplete, unsealed, or arm-revealing adjudication handoff."""
    if blinding_map.study_id != manifest.study_id:
        raise ValueError("blinding map study_id does not match manifest")
    if blinding_map.manifest_sha256 != manifest_sha256:
        raise ValueError("blinding map manifest_sha256 does not match manifest")
    if len(reviewer_packet_paths) != len(blinding_map.entries) * len(blinding_map.review_panel.reviewer_ids):
        raise ValueError("adjudication requires one completed packet per reviewer and opaque packet ID")
    if _path_contains_experimental_arm_label(adjudicator_output_root):
        raise ValueError("adjudicator_output_root must not contain an experimental arm label")
    if adjudicator_output_root.exists():
        raise FileExistsError(f"Refusing to overwrite adjudicator packets: {adjudicator_output_root}")
    resolved_adjudicator_root = adjudicator_output_root.resolve()
    for reviewer_packet_path in reviewer_packet_paths:
        resolved_reviewer_packet_root = reviewer_packet_path.parent.resolve()
        if (
            resolved_adjudicator_root == resolved_reviewer_packet_root
            or resolved_adjudicator_root.is_relative_to(resolved_reviewer_packet_root)
            or resolved_reviewer_packet_root.is_relative_to(resolved_adjudicator_root)
        ):
            raise ValueError("adjudicator_output_root must be separate from reviewer packet directories")


def _group_completed_reviewer_packets(
    *,
    manifest: ExperimentManifest,
    manifest_sha256: str,
    blinding_map: BlindingMap,
    completed_packets: tuple[CompletedReviewerPacket, ...],
) -> tuple[CompletedReviewerPacketGroup, ...]:
    """Group verified returns by opaque ID without exposing their arm allocation.

    The returned groups carry only opaque packet identifiers, never arm labels.
    """
    map_entries_by_packet_id = {
        entry.review_packet_id: entry
        for entry in blinding_map.entries
    }
    packets_by_id: dict[str, dict[str, CompletedReviewerPacket]] = {}
    for completed in completed_packets:
        packet = completed.packet
        _validate_opaque_packet_payload(packet)
        if packet.study_id != manifest.study_id:
            raise ValueError(f"{packet.review_packet_id}: reviewer packet study_id does not match manifest")
        if packet.manifest_sha256 != manifest_sha256:
            raise ValueError(f"{packet.review_packet_id}: reviewer packet manifest_sha256 does not match manifest")
        if not packet.is_complete:
            raise ValueError(f"{packet.review_packet_id}: reviewer packet is incomplete")
        map_entry = map_entries_by_packet_id.get(packet.review_packet_id)
        if map_entry is None:
            raise ValueError(f"Unexpected reviewer packet: {packet.review_packet_id}")
        if packet.reviewer_id not in blinding_map.review_panel.reviewer_ids:
            raise ValueError(f"{packet.review_packet_id}: reviewer is not assigned to the review panel")
        if fingerprint_reviewer_evidence(packet.evidence_artifacts) != map_entry.evidence_manifest_sha256:
            raise ValueError(f"{packet.review_packet_id}: packet evidence does not match the sealed blinding map")
        packet_group = packets_by_id.setdefault(packet.review_packet_id, {})
        if packet.reviewer_id in packet_group:
            raise ValueError(f"Duplicate reviewer return: {packet.review_packet_id}/{packet.reviewer_id}")
        packet_group[packet.reviewer_id] = completed

    expected_packet_ids = set(map_entries_by_packet_id)
    if set(packets_by_id) != expected_packet_ids:
        raise ValueError("reviewer packets do not match the sealed blinding map")
    expected_reviewer_ids = set(blinding_map.review_panel.reviewer_ids)
    grouped_packets: list[CompletedReviewerPacketGroup] = []
    for review_packet_id, packet_group in packets_by_id.items():
        if set(packet_group) != expected_reviewer_ids:
            raise ValueError(f"{review_packet_id}: missing an independent reviewer return")
        grouped_packets.append(
            CompletedReviewerPacketGroup(
                review_packet_id=review_packet_id,
                packets=tuple(packet_group.values()),
            )
        )
    return tuple(grouped_packets)


def _validate_output_roots(
    *,
    arm_output_root: Path,
    reviewer_output_root: Path,
    gold_reviewer_output_root: Path,
    coordinator_output_root: Path,
) -> None:
    """Keep arm-labelled outputs and sealed coordination data out of reviewer trees."""
    if not arm_output_root.is_dir():
        raise FileNotFoundError(arm_output_root)
    if _path_contains_experimental_arm_label(reviewer_output_root):
        raise ValueError("reviewer_output_root must not contain an experimental arm label")
    if _path_contains_experimental_arm_label(gold_reviewer_output_root):
        raise ValueError("gold_reviewer_output_root must not contain an experimental arm label")
    if reviewer_output_root.exists():
        raise FileExistsError(f"Refusing to overwrite reviewer packets: {reviewer_output_root}")
    if gold_reviewer_output_root.exists():
        raise FileExistsError(f"Refusing to overwrite gold reviewer packets: {gold_reviewer_output_root}")
    if coordinator_output_root.exists():
        raise FileExistsError(f"Refusing to overwrite coordinator outputs: {coordinator_output_root}")
    roots = (
        ("arm_output_root", arm_output_root.resolve()),
        ("reviewer_output_root", reviewer_output_root.resolve()),
        ("gold_reviewer_output_root", gold_reviewer_output_root.resolve()),
        ("coordinator_output_root", coordinator_output_root.resolve()),
    )
    for index, (left_name, left_root) in enumerate(roots):
        for right_name, right_root in roots[index + 1 :]:
            if (
                left_root == right_root
                or left_root.is_relative_to(right_root)
                or right_root.is_relative_to(left_root)
            ):
                raise ValueError(
                    f"{left_name} and {right_name} must be separate, non-nested directories"
                )


def _create_staging_root(output_root: Path) -> Path:
    """Create a sibling staging root without exposing a partial delivery tree."""
    resolved_output_root = output_root.resolve()
    resolved_output_root.parent.mkdir(parents=True, exist_ok=True)
    return Path(
        tempfile.mkdtemp(
            prefix=f".{resolved_output_root.name}.staging-",
            dir=resolved_output_root.parent,
        )
    )


def _publish_staging_roots(staging_roots: tuple[tuple[Path, Path], ...]) -> None:
    """Publish fully written delivery roots only after every template has been built."""
    for staging_root, output_root in staging_roots:
        if output_root.exists() or output_root.is_symlink():
            raise FileExistsError(f"Refusing to overwrite output root: {output_root}")
        staging_root.rename(output_root)


def _prepare_reviewer_packets(
    *,
    manifest: ExperimentManifest,
    manifest_sha256: str,
    entries: tuple[ExperimentEntry, ...],
    events: tuple[GoldCriterionEvent, ...],
    arm_output_root: Path,
    run_index: VerifiedArmRunIndex,
) -> tuple[PreparedReviewerPacket, ...]:
    """Read all arm outputs before any reviewer-visible directory is created."""
    packet_ids: set[str] = set()
    prepared_packets: list[PreparedReviewerPacket] = []
    packet_arms = list(ACMG_MULTILINGUAL_ARMS)
    secrets.SystemRandom().shuffle(packet_arms)
    for arm in packet_arms:
        review_packet_id = _generate_packet_id(packet_ids)
        evidence = tuple(
            _read_reviewer_evidence(
                arm_output_root=arm_output_root,
                entry=entry,
                arm=arm,
                run=run_index.by_case_and_arm[(entry.case_id, arm)],
            )
            for entry in entries
        )
        prepared_packets.append(
            PreparedReviewerPacket(
                arm=arm,
                study_id=manifest.study_id,
                manifest_sha256=manifest_sha256,
                review_packet_id=review_packet_id,
                evidence_artifacts=tuple(item.artifact for item in evidence),
                decisions=tuple(
                    ArmCriterionDecision(
                        event_id=event.event_id,
                        criterion_family=event.criterion_family,
                        outcome="not_assessed",
                    )
                    for event in events
                ),
                evidence=evidence,
            )
        )
    return tuple(prepared_packets)


def _generate_packet_id(existing_packet_ids: set[str]) -> str:
    """Return a cryptographically random, nonsemantic identifier for one packet."""
    while True:
        review_packet_id = f"packet-{secrets.token_hex(16)}"
        if review_packet_id not in existing_packet_ids:
            existing_packet_ids.add(review_packet_id)
            return review_packet_id


def _read_reviewer_evidence(
    *,
    arm_output_root: Path,
    entry: ExperimentEntry,
    arm: ExperimentArm,
    run: ArmExtractionRun,
) -> PreparedReviewerEvidence:
    """Load one completed arm result and reject an output that leaks its arm label."""
    resolved_output_root = arm_output_root.resolve()
    source_path = arm_output_root / entry.case_id / arm / "extraction_result.json"
    resolved_source_path = source_path.resolve()
    if not resolved_source_path.is_relative_to(resolved_output_root):
        raise ValueError(f"Arm output escapes configured root: {source_path}")
    if not resolved_source_path.is_file():
        raise FileNotFoundError(resolved_source_path)
    if run.result_path.resolve() != resolved_source_path:
        raise ValueError(f"{entry.case_id}/{arm}: run receipt result path does not match arm output")
    content = resolved_source_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != run.result_sha256:
        raise ValueError(f"{entry.case_id}/{arm}: arm result SHA-256 does not match run receipt")
    _validate_neutral_reviewer_result(content, resolved_source_path)
    artifact = ReviewPacketEvidenceArtifact(
        case_id=entry.case_id,
        relative_path=Path("evidence") / f"{entry.case_id}.json",
        sha256=hashlib.sha256(content).hexdigest(),
    )
    return PreparedReviewerEvidence(artifact=artifact, content=content)


def _validate_neutral_reviewer_result(content: bytes, path: Path) -> None:
    """Reject malformed or arm-labelled payloads before a reviewer can receive them."""
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Reviewer evidence must be a UTF-8 JSON object: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Reviewer evidence must be a JSON object: {path}")
    if _contains_experimental_arm_label(payload):
        raise ValueError(f"Reviewer evidence contains an experimental arm label: {path}")


def _contains_experimental_arm_label(value: object) -> bool:
    """Detect labels that would make a supposedly masked packet self-identifying."""
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
    """Reject a delivery path that would disclose an arm before the file is opened."""
    return any(
        arm in path_part
        for path_part in path.resolve().parts
        for arm in ACMG_MULTILINGUAL_ARMS
    )


def _validate_opaque_packet_payload(packet: BaseModel) -> None:
    """Ensure neutral reviewer or adjudicator metadata cannot disclose an arm."""
    if _contains_experimental_arm_label(packet.model_dump(mode="json")):
        raise ValueError("Reviewer packet metadata contains an experimental arm label")


def _write_reviewer_packet(
    *,
    prepared: PreparedReviewerPacket,
    reviewer_id: str,
    reviewer_root: Path,
) -> Path:
    """Write one reviewer's neutral copy without using their ID as a path segment."""
    packet = BlindedArmDecisionPacket(
        study_id=prepared.study_id,
        manifest_sha256=prepared.manifest_sha256,
        review_packet_id=prepared.review_packet_id,
        reviewer_id=reviewer_id,
        evidence_artifacts=prepared.evidence_artifacts,
        is_complete=False,
        decisions=prepared.decisions,
    )
    _validate_opaque_packet_payload(packet)
    packet_root = reviewer_root / prepared.review_packet_id
    packet_root.mkdir(parents=True, exist_ok=False)
    for evidence in prepared.evidence:
        artifact_path = packet_root / evidence.artifact.relative_path
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(evidence.content)
    packet_path = packet_root / "review_packet.json"
    _write_model(packet, packet_path)
    return packet_path


def _write_gold_reviewer_template(
    *,
    study_id: str,
    manifest_sha256: str,
    reviewer_id: str,
    events: tuple[GoldCriterionEvent, ...],
    reviewer_root: Path,
) -> Path:
    """Write one isolated gold-review template without any arm result or map."""
    gold_review = GoldReviewerDecisionSet(
        study_id=study_id,
        manifest_sha256=manifest_sha256,
        reviewer_id=reviewer_id,
        is_complete=False,
        events=events,
    )
    reviewer_root.mkdir(parents=True, exist_ok=False)
    gold_review_path = reviewer_root / "gold_review.json"
    _write_model(gold_review, gold_review_path)
    return gold_review_path


def _write_adjudication_packet(
    *,
    packet: BlindedArmAdjudicationPacket,
    evidence_source_root: Path,
    adjudicator_output_root: Path,
) -> Path:
    """Copy verified evidence into one neutral packet for the adjudicating clinician."""
    packet_root = adjudicator_output_root / packet.review_packet_id
    packet_root.mkdir(parents=False, exist_ok=False)
    resolved_evidence_source_root = evidence_source_root.resolve()
    for artifact in packet.evidence_artifacts:
        source_path = (resolved_evidence_source_root / artifact.relative_path).resolve()
        if not source_path.is_relative_to(resolved_evidence_source_root):
            raise ValueError(f"{packet.review_packet_id}: evidence artifact escapes reviewer packet root")
        content = source_path.read_bytes()
        if hashlib.sha256(content).hexdigest() != artifact.sha256:
            raise ValueError(f"{packet.review_packet_id}: evidence artifact SHA-256 does not match packet")
        _validate_neutral_reviewer_result(content, source_path)
        target_path = packet_root / artifact.relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
    packet_path = packet_root / "adjudication_packet.json"
    _write_model(packet, packet_path)
    return packet_path


def _gold_events(entries: tuple[ExperimentEntry, ...]) -> list[GoldCriterionEvent]:
    """Enumerate predeclared assertion/criterion-family keys with no outcome filled in."""
    events: list[GoldCriterionEvent] = []
    for entry in entries:
        if entry.index_assertion is None:
            raise ValueError(f"{entry.case_id}: ready entry has no index assertion")
        for family in entry.index_assertion.planned_criterion_families:
            events.append(
                GoldCriterionEvent(
                    event_id=f"{entry.index_assertion.assertion_id}:{family}",
                    assertion_id=entry.index_assertion.assertion_id,
                    source_family_id=entry.source_family_id,
                    criterion_family=family,
                    outcome="not_assessed",
                )
            )
    return events


def _write_model(model: BaseModel, path: Path) -> None:
    """Write one schema-valid template with deterministic formatting."""
    payload = json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    path.write_text(payload + "\n", encoding="utf-8")
