from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

SUCCESS_RATE_THRESHOLD = 95.0
PAPER_DURATION_SLA_SECONDS = 30 * 60


class AcceptancePaperRecord(BaseModel):
    paper_id: str = Field(..., description="Stable acceptance-set paper identifier")
    paper_task_id: Optional[str] = Field(None, description="paper_task_id when executed")
    status: str = Field("queued", description="Paper task status")
    error_code: Optional[str] = Field(None, description="Frozen task error code")
    duration_seconds: Optional[float] = Field(
        None, description="Per-paper end-to-end duration from worker start"
    )
    worker_started_at: Optional[str] = Field(
        None, description="Worker start timestamp"
    )
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    title: Optional[str] = Field(None, description="Human-readable title")
    notes: Optional[str] = Field(None, description="Optional operator notes")


class AcceptanceManifest(BaseModel):
    release_no: str = Field(..., description="Release identifier, e.g. v1.0")
    expected_paper_count: int = Field(100, description="Frozen acceptance-set size")
    locked: bool = Field(False, description="Whether the acceptance set is locked")
    generated_at: Optional[str] = Field(None, description="Manifest generation timestamp")
    notes: List[str] = Field(default_factory=list, description="Manifest-level notes")
    papers: List[AcceptancePaperRecord] = Field(
        default_factory=list,
        description="Acceptance papers and observed execution results",
    )


class ReleaseGateSummary(BaseModel):
    gate_status: str
    blocking_reasons: List[str]
    manifest_entry_count: int
    completed_paper_count: int
    pending_paper_count: int
    success_count: int
    failed_count: int
    duplicate_count: int
    success_rate_numerator: int
    success_rate_denominator: int
    success_rate_pct: Optional[float]
    max_duration_seconds: Optional[float]
    duration_sla_pass: bool


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _paper_duration_seconds(paper: AcceptancePaperRecord) -> Optional[float]:
    if paper.duration_seconds is not None:
        return float(paper.duration_seconds)
    started_at = _parse_iso_datetime(paper.worker_started_at)
    completed_at = _parse_iso_datetime(paper.completed_at)
    if started_at is None or completed_at is None:
        return None
    return max((completed_at - started_at).total_seconds(), 0.0)


def calculate_release_gate_summary(
    manifest: AcceptanceManifest,
) -> ReleaseGateSummary:
    completed_papers = [
        paper for paper in manifest.papers if paper.status in {"success", "failed"}
    ]
    success_count = sum(1 for paper in completed_papers if paper.status == "success")
    failed_count = sum(1 for paper in completed_papers if paper.status == "failed")
    duplicate_count = sum(
        1
        for paper in completed_papers
        if paper.status == "success" and paper.error_code == "FILE_DUPLICATE"
    )
    success_rate_denominator = len(completed_papers)
    success_rate_pct = (
        (success_count / success_rate_denominator) * 100.0
        if success_rate_denominator
        else None
    )

    durations = [
        duration
        for duration in (_paper_duration_seconds(paper) for paper in completed_papers)
        if duration is not None
    ]
    max_duration_seconds = max(durations) if durations else None
    duration_sla_pass = all(
        duration <= PAPER_DURATION_SLA_SECONDS for duration in durations
    )
    if len(durations) < len(completed_papers):
        duration_sla_pass = False

    blocking_reasons: List[str] = []
    if not manifest.locked:
        blocking_reasons.append("MANIFEST_UNLOCKED")
    if len(completed_papers) < manifest.expected_paper_count:
        blocking_reasons.append("RUN_INCOMPLETE")
    elif success_rate_pct is not None and success_rate_pct < SUCCESS_RATE_THRESHOLD:
        blocking_reasons.append("SUCCESS_RATE_BELOW_THRESHOLD")
    if (
        len(completed_papers) >= manifest.expected_paper_count
        and not duration_sla_pass
    ):
        blocking_reasons.append("DURATION_SLA_BREACHED")

    if any(
        reason in {"MANIFEST_UNLOCKED", "RUN_INCOMPLETE"}
        for reason in blocking_reasons
    ):
        gate_status = "INCOMPLETE"
    elif blocking_reasons:
        gate_status = "FAILED"
    else:
        gate_status = "PASSED"

    return ReleaseGateSummary(
        gate_status=gate_status,
        blocking_reasons=blocking_reasons,
        manifest_entry_count=len(manifest.papers),
        completed_paper_count=len(completed_papers),
        pending_paper_count=max(manifest.expected_paper_count - len(completed_papers), 0),
        success_count=success_count,
        failed_count=failed_count,
        duplicate_count=duplicate_count,
        success_rate_numerator=success_count,
        success_rate_denominator=success_rate_denominator,
        success_rate_pct=success_rate_pct,
        max_duration_seconds=max_duration_seconds,
        duration_sla_pass=duration_sla_pass,
    )


def load_acceptance_manifest(path: str | Path) -> AcceptanceManifest:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return AcceptanceManifest.model_validate(payload)


def save_acceptance_manifest(
    path: str | Path,
    manifest: AcceptanceManifest,
) -> None:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _default_template_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "templates"
        / "release_report.md.template"
    )


def render_release_report(
    manifest: AcceptanceManifest,
    summary: ReleaseGateSummary,
    *,
    template_text: Optional[str] = None,
) -> str:
    if template_text is None:
        template_text = _default_template_path().read_text(encoding="utf-8")

    success_rate_pct = (
        f"{summary.success_rate_pct:.1f}"
        if summary.success_rate_pct is not None
        else "n/a"
    )
    max_duration_seconds = (
        f"{summary.max_duration_seconds:.1f}"
        if summary.max_duration_seconds is not None
        else "n/a"
    )
    generated_at = manifest.generated_at or datetime.now(timezone.utc).isoformat()
    reasons = summary.blocking_reasons or ["NONE"]
    notes = manifest.notes or ["None."]

    return template_text.format(
        release_no=manifest.release_no,
        generated_at=generated_at,
        locked="yes" if manifest.locked else "no",
        expected_paper_count=manifest.expected_paper_count,
        manifest_entry_count=summary.manifest_entry_count,
        completed_paper_count=summary.completed_paper_count,
        pending_paper_count=summary.pending_paper_count,
        gate_status=summary.gate_status,
        success_count=summary.success_count,
        failed_count=summary.failed_count,
        duplicate_count=summary.duplicate_count,
        success_rate_numerator=summary.success_rate_numerator,
        success_rate_denominator=summary.success_rate_denominator,
        success_rate_pct=success_rate_pct,
        max_duration_seconds=max_duration_seconds,
        duration_sla_pass="yes" if summary.duration_sla_pass else "no",
        blocking_reasons="\n".join(f"- {reason}" for reason in reasons),
        notes="\n".join(f"- {note}" for note in notes),
    )
