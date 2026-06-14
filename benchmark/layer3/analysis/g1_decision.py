"""Generate a reproducible BIBM G1 go/no-go decision report."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Mapping, TypedDict, cast

from benchmark.analysis.diagnose_grounding import (
    GroundingDiagnostics,
    build_grounding_diagnostics,
    latest_report_path,
)
from benchmark.analysis.diagnose_native_gain import (
    DEFAULT_RETT_ROOT,
    NativeGainDiagnostics,
    build_native_gain_diagnostics,
)
from benchmark.layer3.analysis.diagnose_baselines import (
    BaselineComparison,
    ComparisonRow,
    build_comparison,
)
from benchmark.layer3.analysis.inventory_system_runs import (
    SystemRunInventory,
    run_inventory,
)
from benchmark.layer3.evaluate import REPORTS_DIR


@dataclass(frozen=True)
class G1DirectionDecision:
    """One G1 decision row for a candidate novelty direction."""

    direction: str
    signal: str
    key_numbers: str
    data_legality: str
    missing_work: str


@dataclass(frozen=True)
class G1Decision:
    """Complete G1 decision report."""

    recommendation: str
    main_paper_ready: bool
    system_report_path: Path
    directions: list[G1DirectionDecision]
    evidence: Mapping[str, object]
    owner_options: tuple[str, ...]


class G1DirectionPayload(TypedDict):
    """Serializable G1 decision row."""

    direction: str
    signal: str
    key_numbers: str
    data_legality: str
    missing_work: str


class G1DecisionPayload(TypedDict):
    """Serializable G1 decision report."""

    recommendation: str
    main_paper_ready: bool
    system_report_path: str
    evidence: Mapping[str, object]
    directions: list[G1DirectionPayload]
    owner_options: list[str]


def build_g1_decision(
    comparison: BaselineComparison,
    inventory: SystemRunInventory,
    grounding: GroundingDiagnostics,
    native_gain: NativeGainDiagnostics,
) -> G1Decision:
    """Build the G1 decision from already-computed diagnostics."""
    system = _system_row(comparison)
    best_f1 = _best_baseline_f1(comparison)
    best_labels = _best_baseline_labels(comparison, best_f1)
    has_full_system_coverage = inventory.mapped_count == inventory.total_expected
    system_beats_best_baseline = system.f1 > best_f1

    a_signal = (
        "positive_signal"
        if has_full_system_coverage and system_beats_best_baseline
        else "no_go"
    )
    b_signal = "not_evaluable" if native_gain.missing_dual_track_data else "diagnostic_only"
    c_signal = _grounding_signal(grounding, inventory)
    main_paper_ready = a_signal == "positive_signal" or c_signal == "main_candidate"

    directions = [
        G1DirectionDecision(
            direction="A_structured_extraction",
            signal=a_signal,
            key_numbers=(
                f"SYSTEM F1={system.f1}; "
                f"best matched baseline {'/'.join(best_labels)} F1={best_f1}; "
                f"mapped_system_coverage={inventory.mapped_count}/{inventory.total_expected}"
            ),
            data_legality="ClinGen GT is valid for field P/R/F1; current system coverage is incomplete.",
            missing_work="Current full-system N=30 and a statistically defensible win over B1/B4.",
        ),
        G1DirectionDecision(
            direction="B_native_gain",
            signal=b_signal,
            key_numbers=(
                f"files_discovered={native_gain.files_discovered}; "
                f"files_analyzed={native_gain.files_analyzed}; "
                f"original_only={native_gain.total_original_only}"
            ),
            data_legality="rett is native multilingual, but current artifact set has no evaluable dual-track outputs.",
            missing_work="Materialize rett dual-track extraction results and add GT or validated recall proxy.",
        ),
        G1DirectionDecision(
            direction="C_grounding_traceability",
            signal=c_signal,
            key_numbers=(
                f"CVR={_format_optional_float(grounding.citation_validity_rate)}; "
                f"HCR={_format_optional_float(grounding.hallucinated_citation_rate)}; "
                f"span_evidence={grounding.span_evidence_count}; "
                f"N={grounding.total_entries}"
            ),
            data_legality="Source-span validity is measurable; semantic correctness is still governed by P/R/F1.",
            missing_work="Full span-bearing report, ESR/span-boundary checks, reconcile/ranking algorithm, and ablation.",
        ),
    ]
    return G1Decision(
        recommendation="main_candidate" if main_paper_ready else "owner_decision_required",
        main_paper_ready=main_paper_ready,
        system_report_path=system.report_path,
        directions=directions,
        evidence={
            "system_report": str(system.report_path),
            "system_entries": system.total_entries,
            "inventory_mapped": inventory.mapped_count,
            "inventory_total_expected": inventory.total_expected,
            "best_matched_baseline_f1": best_f1,
            "best_matched_baselines": best_labels,
            "grounding_report": str(grounding.report_path),
            "native_gain_root": str(native_gain.root),
        },
        owner_options=(
            "run_current_full_system_n30",
            "pivot_demo_resource_track",
            "implement_direction_c_reconcile_ranking",
        ),
    )


def g1_decision_to_payload(decision: G1Decision) -> G1DecisionPayload:
    """Convert a G1 decision into JSON-serializable payload."""
    return {
        "recommendation": decision.recommendation,
        "main_paper_ready": decision.main_paper_ready,
        "system_report_path": str(decision.system_report_path),
        "evidence": decision.evidence,
        "directions": [
            {
                "direction": row.direction,
                "signal": row.signal,
                "key_numbers": row.key_numbers,
                "data_legality": row.data_legality,
                "missing_work": row.missing_work,
            }
            for row in decision.directions
        ],
        "owner_options": list(decision.owner_options),
    }


def format_g1_decision(decision: G1Decision) -> str:
    """Format a G1 decision for terminal review."""
    lines = [
        f"recommendation={decision.recommendation} main_paper_ready={decision.main_paper_ready}",
        f"system_report={decision.system_report_path}",
        "direction signal key_numbers missing_work",
    ]
    for row in decision.directions:
        lines.append(f"{row.direction} {row.signal} {row.key_numbers} missing={row.missing_work}")
    lines.append(f"owner_options={','.join(decision.owner_options)}")
    return "\n".join(lines)


def write_g1_decision(decision: G1Decision, reports_dir: Path = REPORTS_DIR) -> Path:
    """Persist a G1 decision JSON report."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"g1_decision_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(g1_decision_to_payload(decision), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


async def build_g1_decision_from_current_state(
    vault_path: Path | None,
    system_report_path: Path | None,
    native_root: Path,
) -> G1Decision:
    """Build the G1 report from current persisted artifacts and DB inventory."""
    resolved_system_report = system_report_path or latest_report_path()
    comparison = build_comparison(
        system_report_path=resolved_system_report,
        match_system_entries=True,
    )
    inventory = await run_inventory(vault_path)
    grounding = build_grounding_diagnostics(resolved_system_report)
    native_gain = build_native_gain_diagnostics(native_root)
    return build_g1_decision(comparison, inventory, grounding, native_gain)


def _system_row(comparison: BaselineComparison) -> ComparisonRow:
    for row in comparison.rows:
        if row.label == "SYSTEM":
            return row
    raise ValueError("Baseline comparison is missing SYSTEM row")


def _baseline_rows(comparison: BaselineComparison) -> list[ComparisonRow]:
    return [row for row in comparison.rows if row.label != "SYSTEM"]


def _best_baseline_f1(comparison: BaselineComparison) -> float:
    rows = _baseline_rows(comparison)
    return max((row.f1 for row in rows), default=0.0)


def _best_baseline_labels(comparison: BaselineComparison, best_f1: float) -> list[str]:
    return [
        row.label
        for row in _baseline_rows(comparison)
        if row.f1 == best_f1
    ]


def _grounding_signal(
    grounding: GroundingDiagnostics,
    inventory: SystemRunInventory,
) -> str:
    if grounding.missing_span_evidence or grounding.citation_validity_rate is None:
        return "not_evaluable"
    if inventory.mapped_count < inventory.total_expected:
        return "weak_feasibility_signal"
    if grounding.hallucinated_citation_rate == 0.0:
        return "main_candidate"
    return "diagnostic_only"


def _format_optional_float(value: float | None) -> str:
    return "uncomputable" if value is None else str(value)


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=None)
    parser.add_argument("--system-report", type=Path, default=None)
    parser.add_argument("--native-root", type=Path, default=DEFAULT_RETT_ROOT)
    parser.add_argument("--write", action="store_true", help="Persist g1_decision_<timestamp>.json")
    args = parser.parse_args()

    decision = asyncio.run(
        build_g1_decision_from_current_state(
            vault_path=cast(Path | None, args.vault),
            system_report_path=cast(Path | None, args.system_report),
            native_root=cast(Path, args.native_root),
        )
    )
    if args.write:
        report_path = write_g1_decision(decision)
        print(f"REPORT: {report_path}")
    print(format_g1_decision(decision))


if __name__ == "__main__":
    main()
