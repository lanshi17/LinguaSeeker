"""CLI for validating, materializing, and scoring ACMG multilingual studies."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .adjudication_templates import (
    create_adjudication_templates,
    prepare_blinded_adjudication_packets,
)
from .contracts import ReviewPanel
from .coverage import (
    load_source_coverage_fact_table,
    verify_source_coverage,
    write_coverage_verification_report,
)
from .allele_class_increment import (
    score_allele_class_increment,
    summarize_allele_class_increment,
)
from .evidence_item_coverage import (
    load_evidence_item_coverage_table,
    summarize_evidence_item_coverage,
    verify_evidence_item_coverage,
    write_evidence_item_verification_report,
)
from .four_arm_corpus import (
    load_corpus_manifest,
    scan_corpus,
    verify_corpus_manifest,
    write_corpus_manifest,
    write_corpus_verification_report,
)
from .materialize import (
    materialize_reviewed_inputs,
    verify_native_source_artifacts,
    write_materialization_report,
    write_native_source_verification_report,
)
from .readiness import assess_manifest_readiness
from .retrieval_reachability import (
    load_retrieval_probe_ledger,
    load_retrieval_target_ledger,
    score_retrieval_reachability,
    write_retrieval_recall_report,
)
from .run import load_arm_run_report
from .translation_fidelity import (
    load_translation_fidelity_fact_table,
    verify_translation_fidelity,
    write_translation_fidelity_report,
)
from .direct_inference import (
    load_direct_inference_table,
    summarize_direct_inference,
    verify_direct_inference,
    write_direct_inference_report,
)
from .field_bridge import (
    load_and_verify_field_bridge,
    write_field_bridge_report,
)
from .live_extraction_probe import (
    DEFAULT_PROBE_EVENT_IDS,
    on_disk_probe_event_ids,
    run_live_extraction_probe,
    write_live_extraction_probe_report,
)
from .increment_denominator import (
    load_increment_denominator,
    summarize_increment_denominator,
    verify_increment_denominator,
    write_increment_denominator_report,
)
from .scoring import (
    evaluate_code_recovery,
    load_blinded_adjudication_packet,
    load_blinding_map,
    load_gold_adjudication,
    load_manifest,
    unblind_decision_packets,
    write_code_recovery_report,
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse a non-model CLI command; live model execution lives in run.py."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check-manifest", help="Report whether every active entry is ready")
    check_parser.add_argument("--manifest", type=Path, required=True)

    coverage_parser = subparsers.add_parser(
        "verify-coverage",
        help="Verify the frozen Stage-0 source-coverage fact table against a corpus",
    )
    coverage_parser.add_argument("--facts", type=Path, required=True)
    coverage_parser.add_argument("--source-root", type=Path, required=True)
    coverage_parser.add_argument("--report", type=Path, required=True)

    freeze_corpus_parser = subparsers.add_parser(
        "freeze-corpus",
        help="Scan the external corpus once into a frozen Stage-1 manifest",
    )
    freeze_corpus_parser.add_argument("--source-root", type=Path, required=True)
    freeze_corpus_parser.add_argument("--corpus-revision", required=True)
    freeze_corpus_parser.add_argument("--created-on", required=True)
    freeze_corpus_parser.add_argument("--manifest", type=Path, required=True)

    verify_corpus_parser = subparsers.add_parser(
        "verify-corpus",
        help="Re-scan the corpus and verify every family against the frozen manifest",
    )
    verify_corpus_parser.add_argument("--manifest", type=Path, required=True)
    verify_corpus_parser.add_argument("--source-root", type=Path, required=True)
    verify_corpus_parser.add_argument("--report", type=Path, required=True)

    retrieval_parser = subparsers.add_parser(
        "score-retrieval",
        help="Score eligible-source retrieval recall from a frozen probe ledger",
    )
    retrieval_parser.add_argument("--targets", type=Path, required=True)
    retrieval_parser.add_argument("--probes", type=Path, required=True)
    retrieval_parser.add_argument("--report", type=Path, required=True)

    fidelity_parser = subparsers.add_parser(
        "verify-translation-fidelity",
        help="Verify that reviewed English full texts still carry every critical native fact",
    )
    fidelity_parser.add_argument("--facts", type=Path, required=True)
    fidelity_parser.add_argument("--reviewed-root", type=Path, required=True)
    fidelity_parser.add_argument("--report", type=Path, required=True)

    increment_parser = subparsers.add_parser(
        "check-increment-denominator",
        help="Validate and verify the frozen cross-disease ACMG increment denominator",
    )
    increment_parser.add_argument("--denominator", type=Path, required=True)
    increment_parser.add_argument(
        "--reviewed-root",
        type=Path,
        default=None,
        help="Root containing reviewed/<case_id>/source.md artifacts",
    )
    increment_parser.add_argument(
        "--clinvar-fused-root",
        type=Path,
        default=None,
        help="Root containing fused_NNN/source.md artifacts",
    )
    increment_parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional verification receipt path",
    )

    inference_parser = subparsers.add_parser(
        "check-direct-inference",
        help="Verify the frozen MECP2 direct-inference table against reviewed sources",
    )
    inference_parser.add_argument("--cases", type=Path, required=True)
    inference_parser.add_argument(
        "--reviewed-root",
        type=Path,
        default=None,
        help="Root containing reviewed/<case_id>/source.md artifacts",
    )
    inference_parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional verification receipt path",
    )

    field_bridge_parser = subparsers.add_parser(
        "check-field-bridge",
        help="Verify catalog-field quotes, parentage absence, and allele bindings",
    )
    field_bridge_parser.add_argument("--cases", type=Path, required=True)
    field_bridge_parser.add_argument("--alleles", type=Path, required=True)
    field_bridge_parser.add_argument("--facts", type=Path, required=True)
    field_bridge_parser.add_argument(
        "--reviewed-root",
        type=Path,
        default=None,
        help="Root containing reviewed/<case_id>/source.md artifacts",
    )
    field_bridge_parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional verification receipt path",
    )

    evidence_item_parser = subparsers.add_parser(
        "check-evidence-item-coverage",
        help="Verify catalog field-item increment across English vs native layers",
    )
    evidence_item_parser.add_argument(
        "--facts",
        type=Path,
        default=None,
        help="Frozen evidence-item fact table; default is the committed JSON",
    )
    evidence_item_parser.add_argument(
        "--reviewed-root",
        type=Path,
        required=True,
        help="Root containing reviewed/<case_id>/source.md artifacts",
    )
    evidence_item_parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional verification receipt path",
    )

    allele_class_parser = subparsers.add_parser(
        "check-allele-class-increment",
        help="Score extra Stage-0 ACMG criterion evidence from native vs English-visible facts",
    )
    allele_class_parser.add_argument(
        "--cases",
        type=Path,
        default=None,
        help="Direct-inference table; default is the committed JSON",
    )
    allele_class_parser.add_argument(
        "--facts",
        type=Path,
        default=None,
        help="Evidence-item coverage table; default is the committed JSON",
    )

    probe_parser = subparsers.add_parser(
        "probe-extraction",
        help="Live-extract selected events and see which field-bridge gates recovery fills",
    )
    probe_parser.add_argument("--cases", type=Path, required=True)
    probe_parser.add_argument("--facts", type=Path, required=True)
    probe_parser.add_argument(
        "--reviewed-root",
        type=Path,
        required=True,
        help="Root containing reviewed/<case_id>/source.md artifacts",
    )
    probe_parser.add_argument("--report", type=Path, required=True)
    probe_parser.add_argument(
        "--event-id",
        action="append",
        dest="event_ids",
        default=None,
        help="Event to probe; repeatable. Default: rett_007_case2_R180X and rett_011_P237R",
    )
    probe_parser.add_argument(
        "--all-on-disk",
        action="store_true",
        help="Probe every on-disk direct-inference event instead of the default pair",
    )

    verify_parser = subparsers.add_parser(
        "verify-sources",
        help="Verify native source hashes without promoting pending entries to a run",
    )
    verify_parser.add_argument("--manifest", type=Path, required=True)
    verify_parser.add_argument("--source-root", type=Path, required=True)
    verify_parser.add_argument(
        "--source-revision",
        default="",
        help="Optional external corpus revision retained in the verification receipt",
    )
    verify_parser.add_argument("--report", type=Path, required=True)

    materialize_parser = subparsers.add_parser("materialize", help="Freeze reviewed inputs into original.json/translated.json")
    materialize_parser.add_argument("--manifest", type=Path, required=True)
    materialize_parser.add_argument("--source-root", type=Path, required=True)
    materialize_parser.add_argument("--output-root", type=Path, required=True)
    materialize_parser.add_argument("--report", type=Path, required=True)

    template_parser = subparsers.add_parser("create-templates", help="Create incomplete label-masked adjudication packets")
    template_parser.add_argument("--manifest", type=Path, required=True)
    template_parser.add_argument("--input-root", type=Path, required=True)
    template_parser.add_argument("--arm-output-root", type=Path, required=True)
    template_parser.add_argument("--arm-run-report", type=Path, required=True)
    template_parser.add_argument("--reviewer-output-root", type=Path, required=True)
    template_parser.add_argument("--gold-reviewer-output-root", type=Path, required=True)
    template_parser.add_argument("--coordinator-output-root", type=Path, required=True)
    template_parser.add_argument(
        "--reviewer-id",
        action="append",
        required=True,
        help="One independent clinical reviewer ID; provide exactly two.",
    )
    template_parser.add_argument("--adjudicator-id", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare-adjudication",
        help="Create neutral adjudicator packets from two completed independent reviewer returns per arm",
    )
    prepare_parser.add_argument("--manifest", type=Path, required=True)
    prepare_parser.add_argument("--coordinator-blinding-map", type=Path, required=True)
    prepare_parser.add_argument(
        "--reviewer-packet",
        type=Path,
        action="append",
        required=True,
        help="Path to one completed opaque reviewer packet; provide six total.",
    )
    prepare_parser.add_argument("--adjudicator-output-root", type=Path, required=True)

    score_parser = subparsers.add_parser("score", help="Unblind and score completed formal-code decisions")
    score_parser.add_argument("--manifest", type=Path, required=True)
    score_parser.add_argument("--gold", type=Path, required=True)
    score_parser.add_argument(
        "--adjudication-packet",
        type=Path,
        action="append",
        required=True,
        help="Path to one completed opaque adjudication packet; provide exactly three.",
    )
    score_parser.add_argument("--coordinator-blinding-map", type=Path, required=True)
    score_parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Dispatch one explicit local experiment operation."""
    args = _parse_args(argv)
    if args.command == "verify-coverage":
        coverage_table = load_source_coverage_fact_table(args.facts)
        coverage_report = verify_source_coverage(coverage_table, args.source_root)
        write_coverage_verification_report(coverage_report, args.report)
        print(
            f"Verified {coverage_report.verified_spans}/{coverage_report.total_positive_spans} "
            f"positive spans across {coverage_report.total_sources} sources"
        )
        return
    if args.command == "freeze-corpus":
        corpus_manifest = scan_corpus(
            args.source_root,
            corpus_revision=args.corpus_revision,
            created_on=args.created_on,
        )
        write_corpus_manifest(corpus_manifest, args.manifest)
        print(
            f"Froze {len(corpus_manifest.families)} source families, "
            f"{len(corpus_manifest.pairing_anchors)} cross-language pairing anchors"
        )
        return
    if args.command == "verify-corpus":
        corpus_manifest = load_corpus_manifest(args.manifest)
        report = verify_corpus_manifest(corpus_manifest, args.source_root)
        write_corpus_verification_report(report, args.report)
        print(
            f"Verified {report.verified_families}/{report.total_families} families "
            f"({len(report.drifted_source_families)} drifted)"
        )
        return
    if args.command == "score-retrieval":
        retrieval_report = score_retrieval_reachability(
            load_retrieval_target_ledger(args.targets),
            load_retrieval_probe_ledger(args.probes),
        )
        write_retrieval_recall_report(retrieval_report, args.report)
        for metric in retrieval_report.metrics:
            print(
                f"{metric.arm}: reached {metric.reached_target_count}/{metric.target_count} targets, "
                f"{metric.reached_event_count}/{metric.eligible_event_total} eligible events"
            )
        return
    if args.command == "verify-translation-fidelity":
        fidelity_report = verify_translation_fidelity(
            load_translation_fidelity_fact_table(args.facts),
            args.reviewed_root,
        )
        write_translation_fidelity_report(fidelity_report, args.report)
        print(
            f"Retained {fidelity_report.retained_fact_count}/{fidelity_report.total_facts} critical facts "
            f"across {fidelity_report.total_entries} {fidelity_report.translation_review_status} translations"
        )
        return
    if args.command == "check-increment-denominator":
        denominator = load_increment_denominator(args.denominator)
        summary = summarize_increment_denominator(denominator)
        report = verify_increment_denominator(
            denominator,
            reviewed_root=args.reviewed_root,
            clinvar_fused_root=args.clinvar_fused_root,
        )
        if args.report is not None:
            write_increment_denominator_report(report, args.report)
        print(
            f"Denominator {denominator.study_id}: {summary.total_slots} slots "
            f"({summary.on_disk} on_disk, {summary.needs_external_corpus} external, "
            f"{summary.needs_workbook_export} workbook); "
            f"verified {report.verified_on_disk_slots}/{report.on_disk_slots} on-disk slots"
        )
        if report.on_disk_slots and report.verified_on_disk_slots != report.on_disk_slots:
            raise SystemExit(1)
        return
    if args.command == "check-direct-inference":
        table = load_direct_inference_table(args.cases)
        summary = summarize_direct_inference(table)
        report = verify_direct_inference(table, reviewed_root=args.reviewed_root)
        if args.report is not None:
            write_direct_inference_report(report, args.report)
        print(
            f"Direct inference {table.study_id}: {summary.total_events} events "
            f"({summary.on_disk} on_disk, {summary.pathogenic} pathogenic, "
            f"bilingual increment {summary.bilingual_increment}; "
            f"without rett_007 {summary.bilingual_increment_without_rett_007}); "
            f"verified {report.verified_on_disk_events}/{report.on_disk_events} on-disk events"
        )
        if report.engine_mismatches:
            raise SystemExit(1)
        if report.on_disk_events and report.verified_on_disk_events != report.on_disk_events:
            raise SystemExit(1)
        return
    if args.command == "check-field-bridge":
        _table, _inference, _registry, report = load_and_verify_field_bridge(
            cases_path=args.cases,
            alleles_path=args.alleles,
            facts_path=args.facts,
            reviewed_root=args.reviewed_root,
        )
        if args.report is not None:
            write_field_bridge_report(report, args.report)
        print(
            f"Field bridge {report.study_id}: verified "
            f"{report.verified_on_disk_events}/{report.on_disk_events} on-disk events "
            f"(allele_mismatches={report.allele_mismatches})"
        )
        if report.allele_mismatches:
            raise SystemExit(1)
        if report.on_disk_events and report.verified_on_disk_events != report.on_disk_events:
            raise SystemExit(1)
        return
    if args.command == "check-evidence-item-coverage":
        table = load_evidence_item_coverage_table(args.facts)
        summary = summarize_evidence_item_coverage(table)
        report = verify_evidence_item_coverage(table, reviewed_root=args.reviewed_root)
        if args.report is not None:
            write_evidence_item_verification_report(report, args.report)
        languages = ",".join(summary.languages)
        print(
            f"Evidence items {table.study_id}: {summary.total_sources} sources ({languages}); "
            f"abstract increment {summary.sources_with_abstract_increment}/"
            f"{summary.total_sources} "
            f"(without rett_007 {summary.abstract_increment_without_rett_007}); "
            f"visible increment {summary.sources_with_visible_increment}/"
            f"{summary.total_sources}; "
            f"verified {report.verified_spans}/{report.total_spans} spans, "
            f"{report.verified_sources}/{report.total_sources} sources"
        )
        if report.missed_spans or report.verified_sources != report.total_sources:
            raise SystemExit(1)
        return
    if args.command == "check-allele-class-increment":
        report = score_allele_class_increment(
            inference=load_direct_inference_table(args.cases),
            coverage=load_evidence_item_coverage_table(args.facts),
        )
        summary = summarize_allele_class_increment(report)
        print(
            f"ACMG evidence increment: scored {summary.scored_events}; "
            f"added codes {summary.evidence_increment_events}/"
            f"{summary.scored_events} "
            f"(without rett_007 {summary.evidence_increment_without_rett_007}, "
            f"{summary.unique_alleles_with_added_codes} alleles); "
            f"class flip {summary.en_missing_to_pathogenic} Pathogenic; "
            f"ClinVar-gap Pathogenic {summary.clinvar_gap_pathogenic}; "
            f"both-hero {summary.both_hero}"
        )
        for row in report.rows:
            added = ",".join(row.added_codes) or "-"
            print(
                f"  {row.event_id}: {row.english_classification}→"
                f"{row.native_classification} added={added} "
                f"clinvar={row.clinvar_match} lane={row.lane}"
            )
        return
    if args.command == "probe-extraction":
        import asyncio

        from src.core.config import get_config
        from src.core.evidence_extraction.api import EvidenceExtractionService

        cfg = get_config()
        if args.all_on_disk:
            event_ids = on_disk_probe_event_ids(load_direct_inference_table(args.cases))
        else:
            event_ids = tuple(args.event_ids or DEFAULT_PROBE_EVENT_IDS)
        service = EvidenceExtractionService(cfg=cfg)
        report = asyncio.run(
            run_live_extraction_probe(
                service,
                reviewed_root=args.reviewed_root,
                event_ids=event_ids,
                cases_path=args.cases,
                facts_path=args.facts,
                fast_model=cfg.llm.model,
                reasoning_model=cfg.reasoning.model,
            )
        )
        write_live_extraction_probe_report(report, args.report)
        print(
            f"Live extraction probe: {len(report.events)} events, "
            f"gates llm={report.llm_gate_count} recovered={report.recovered_gate_count} "
            f"normalized={report.normalized_gate_count} missing={report.missing_gate_count}"
        )
        for event in report.events:
            recovered = ",".join(event.recovered_field_ids) or "-"
            missing = ",".join(gate.field_id for gate in event.gates if gate.origin.value == "missing") or "-"
            engine = event.engine
            live_cls = engine.live_classification if engine is not None else "-"
            frozen_cls = engine.frozen_classification if engine is not None else "-"
            print(
                f"  {event.event_id}: codes={list(event.assigned_acmg_codes) or []} "
                f"recovered={recovered} missing={missing} "
                f"live_engine={live_cls} frozen={frozen_cls}"
            )
        return
    manifest = load_manifest(args.manifest)
    if args.command == "check-manifest":
        print(assess_manifest_readiness(manifest).model_dump_json(indent=2))
        return
    if args.command == "verify-sources":
        report = verify_native_source_artifacts(
            manifest=manifest,
            source_root=args.source_root,
            source_revision=args.source_revision,
        )
        write_native_source_verification_report(report, args.report)
        print(f"Verified {len(report.verified_sources)} native source artifacts")
        return
    if args.command == "materialize":
        report = materialize_reviewed_inputs(
            manifest=manifest,
            source_root=args.source_root,
            output_root=args.output_root,
        )
        write_materialization_report(report, args.report)
        print(f"Materialized {len(report.inputs)} reviewed input bundles")
        return
    if args.command == "create-templates":
        review_panel = ReviewPanel(
            reviewer_ids=tuple(args.reviewer_id),
            adjudicator_id=args.adjudicator_id,
        )
        report = create_adjudication_templates(
            manifest,
            input_root=args.input_root,
            arm_output_root=args.arm_output_root,
            arm_run_report=load_arm_run_report(args.arm_run_report),
            reviewer_output_root=args.reviewer_output_root,
            gold_reviewer_output_root=args.gold_reviewer_output_root,
            coordinator_output_root=args.coordinator_output_root,
            review_panel=review_panel,
        )
        print(
            f"Created {len(report.reviewer_packet_paths)} independent reviewer packets, "
            f"{len(report.gold_reviewer_template_paths)} gold-review templates, and sealed coordinator files"
        )
        return
    if args.command == "prepare-adjudication":
        report = prepare_blinded_adjudication_packets(
            manifest,
            load_blinding_map(args.coordinator_blinding_map),
            reviewer_packet_paths=tuple(args.reviewer_packet),
            adjudicator_output_root=args.adjudicator_output_root,
        )
        print(f"Created {len(report.adjudication_packet_paths)} neutral adjudication packets")
        return
    gold = load_gold_adjudication(args.gold)
    adjudication_packets = tuple(
        load_blinded_adjudication_packet(path)
        for path in args.adjudication_packet
    )
    blinding_map = load_blinding_map(args.coordinator_blinding_map)
    decisions = unblind_decision_packets(manifest, blinding_map, adjudication_packets)
    report = evaluate_code_recovery(manifest, gold, decisions)
    write_code_recovery_report(report, args.report)
    print(f"Scored {len(report.metrics)} arms against {len(gold.events)} formal criterion events")


if __name__ == "__main__":
    main()
