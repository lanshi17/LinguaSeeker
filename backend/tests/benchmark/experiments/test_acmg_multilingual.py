"""Tests for the code-level ACMG multilingual experiment slice."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from benchmark.experiments.acmg_multilingual.contracts import (
    ACMG_MULTILINGUAL_ARMS,
    AdjudicationTemplateReport,
    ArmExtractionRun,
    ArmExtractionRunReport,
    ArmCriterionDecision,
    ArmDecisionSet,
    BlindedArmAdjudicationPacket,
    BlindedArmDecisionPacket,
    ClinicalAssertion,
    ExperimentEntry,
    ExperimentManifest,
    GoldAdjudicationSet,
    GoldCriterionEvent,
    GoldReviewerDecisionSet,
    ReviewPanel,
    SourceArtifact,
    SourceArtifactTrack,
    SourceSpan,
    TranslationReview,
)
from benchmark.experiments.acmg_multilingual.adjudication_templates import (
    create_adjudication_templates,
    prepare_blinded_adjudication_packets,
)
from benchmark.experiments.acmg_multilingual.coverage import (
    CoverageSpan,
    SourceCoverageEntry,
    SourceCoverageFactTable,
    VisibilityFacts,
    verify_source_coverage,
)
from benchmark.experiments.acmg_multilingual.four_arm_corpus import (
    SourceFamilyRecord,
    Stage1CorpusManifest,
    VariantPairingAnchor,
    scan_corpus,
    verify_corpus_manifest,
)
from benchmark.experiments.acmg_multilingual.retrieval_reachability import (
    ArmProbe,
    EligibleSource,
    PlannedQuery,
    ProbeSearchResult,
    RetrievalHit,
    RetrievalProbeLedger,
    RetrievalTarget,
    RetrievalTargetLedger,
    load_retrieval_target_ledger,
    normalize_doi,
    probe_retrieval_arms,
    score_retrieval_reachability,
)
from benchmark.experiments.acmg_multilingual.translation_fidelity import (
    CriticalFact,
    TranslationFidelityEntry,
    TranslationFidelityFactTable,
    load_translation_fidelity_fact_table,
    verify_translation_fidelity,
)
from benchmark.experiments.acmg_multilingual.cli import _parse_args
from benchmark.experiments.acmg_multilingual.materialize import (
    materialize_reviewed_inputs,
    verify_native_source_artifacts,
    write_native_source_verification_report,
)
from benchmark.experiments.acmg_multilingual.run import run_ready_arms
from benchmark.experiments.acmg_multilingual.scoring import (
    evaluate_code_recovery,
    fingerprint_manifest,
    load_blinded_adjudication_packet,
    load_blinded_packet,
    load_blinding_map,
    load_manifest,
    unblind_decision_packets,
)


def _sha256(text: str) -> str:
    """Return the deterministic SHA-256 of a UTF-8 test fixture."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_artifact(relative_path: str, text: str, language: str) -> SourceArtifact:
    """Build a source artifact whose hash matches a fixture text."""
    return SourceArtifact(relative_path=Path(relative_path), sha256=_sha256(text), language=language)


def _span(language: str = "zh", artifact_track: SourceArtifactTrack = "original") -> SourceSpan:
    """Return a compact traceable source span for adjudication tests."""
    return SourceSpan(
        location="page 2, table 1",
        quote="The parent samples were wild type.",
        language=language,
        artifact_track=artifact_track,
    )


def _alignment_payload(native: str, english: str) -> str:
    """Return one valid, fully anchored reviewed alignment fixture."""
    return json.dumps(
        [
            {
                "chunk_id": "chunk_001",
                "original_text": native,
                "english_text": english,
                "original_start_offset": 0,
                "original_end_offset": len(native),
                "english_start_offset": 0,
                "english_end_offset": len(english),
                "page": 1,
                "block_index": 0,
                "bbox": [],
                "span_pairs": [],
            }
        ],
        ensure_ascii=False,
    )


def _ready_manifest() -> ExperimentManifest:
    """Create a single, fully reviewed source family for scoring/run tests."""
    native = "原生全文"
    english = "Reviewed English full text"
    alignment = _alignment_payload(native, english)
    entry = ExperimentEntry(
        case_id="case_001",
        source_family_id="article_001",
        family_cluster_id="family_001",
        native_fulltext=_source_artifact("native.md", native, "zh"),
        translation_review=TranslationReview(
            status="human_reviewed",
            english_fulltext=_source_artifact("english.md", english, "en"),
            alignment_relative_path=Path("alignment.json"),
            alignment_sha256=_sha256(alignment),
            reviewer_ids=("reviewer-a", "reviewer-b"),
            reviewed_on=date(2026, 8, 14),
        ),
        status="ready",
        index_assertion=ClinicalAssertion(
            assertion_id="assertion_001",
            gene_symbol="mecp2",
            disease_label="Rett syndrome",
            variant_hgvs_c="c.509C>T",
            planned_criterion_families=("PS2_PM6", "PS3_BS3"),
        ),
    )
    return ExperimentManifest(
        study_id="acmg-multilingual-pilot",
        protocol_version="v1",
        created_on=date(2026, 8, 14),
        entries=(entry,),
    )


def _review_panel() -> ReviewPanel:
    """Return the fixed independent-review panel used by the test fixtures."""
    return ReviewPanel(
        reviewer_ids=("clinical-reviewer-a", "clinical-reviewer-b"),
        adjudicator_id="arm-reviewer",
    )


def _complete_gold(
    manifest: ExperimentManifest,
    events: tuple[GoldCriterionEvent, ...],
) -> GoldAdjudicationSet:
    """Build a final gold set retaining two complete independent reviewer returns."""
    review_panel = _review_panel()
    return GoldAdjudicationSet(
        study_id=manifest.study_id,
        manifest_sha256=fingerprint_manifest(manifest),
        reviewer_ids=review_panel.reviewer_ids,
        review_panel=review_panel,
        reviewer_decision_sets=tuple(
            GoldReviewerDecisionSet(
                study_id=manifest.study_id,
                manifest_sha256=fingerprint_manifest(manifest),
                reviewer_id=reviewer_id,
                is_complete=True,
                events=events,
            )
            for reviewer_id in review_panel.reviewer_ids
        ),
        is_complete=True,
        events=events,
    )


def _write_ready_source_files(source_root: Path) -> None:
    """Write the reviewed source artifacts used by one ready fixture manifest."""
    source_root.mkdir()
    (source_root / "native.md").write_text("原生全文", encoding="utf-8")
    (source_root / "english.md").write_text("Reviewed English full text", encoding="utf-8")
    (source_root / "alignment.json").write_text(
        _alignment_payload("原生全文", "Reviewed English full text"),
        encoding="utf-8",
    )


def _write_neutral_arm_outputs(output_root: Path, manifest: ExperimentManifest) -> ArmExtractionRunReport:
    """Create minimal receipt-bound arm outputs whose payloads do not expose arm labels."""
    input_root = output_root.parent / "input_bundles"
    source_root = output_root.parent / "reviewed_sources"
    _write_ready_source_files(source_root)
    materialize_reviewed_inputs(manifest, source_root, input_root)
    runs: list[ArmExtractionRun] = []
    for entry in manifest.entries:
        if entry.status != "ready":
            continue
        input_dir = input_root / entry.case_id
        input_manifest_path = input_dir / "input_manifest.json"
        input_manifest_sha256 = hashlib.sha256(input_manifest_path.read_bytes()).hexdigest()
        for arm in ACMG_MULTILINGUAL_ARMS:
            result_path = output_root / entry.case_id / arm / "extraction_result.json"
            result_path.parent.mkdir(parents=True, exist_ok=False)
            result_path.write_text(
                json.dumps({"document_id": entry.case_id, "status": "completed"}),
                encoding="utf-8",
            )
            runs.append(
                ArmExtractionRun(
                    case_id=entry.case_id,
                    arm=arm,
                    input_dir=input_dir,
                    input_manifest_sha256=input_manifest_sha256,
                    result_path=result_path,
                    result_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(),
                    duration_seconds=0.0,
                )
            )
    return ArmExtractionRunReport(
        study_id=manifest.study_id,
        manifest_sha256=fingerprint_manifest(manifest),
        runs=tuple(runs),
    )


def _complete_packet(packet: BlindedArmDecisionPacket) -> BlindedArmDecisionPacket:
    """Return a schema-validated completed packet with negative reviewer decisions."""
    return BlindedArmDecisionPacket(
        study_id=packet.study_id,
        manifest_sha256=packet.manifest_sha256,
        review_packet_id=packet.review_packet_id,
        reviewer_id=packet.reviewer_id,
        evidence_artifacts=packet.evidence_artifacts,
        is_complete=True,
        decisions=tuple(
            ArmCriterionDecision(
                event_id=decision.event_id,
                criterion_family=decision.criterion_family,
                outcome="not_qualified",
                reviewer_id=packet.reviewer_id,
            )
            for decision in packet.decisions
        ),
    )


def _write_completed_reviewer_packet(path: Path) -> Path:
    """Complete one reviewer packet in place, preserving its assigned reviewer identity."""
    completed_packet = _complete_packet(load_blinded_packet(path))
    path.write_text(completed_packet.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def _complete_adjudication_packet(
    packet: BlindedArmAdjudicationPacket,
) -> BlindedArmAdjudicationPacket:
    """Return an adjudicator-signed negative final decision for each reviewed event."""
    return BlindedArmAdjudicationPacket(
        study_id=packet.study_id,
        manifest_sha256=packet.manifest_sha256,
        review_packet_id=packet.review_packet_id,
        evidence_artifacts=packet.evidence_artifacts,
        review_panel=packet.review_panel,
        reviewer_packets=packet.reviewer_packets,
        is_complete=True,
        decisions=tuple(
            ArmCriterionDecision(
                event_id=decision.event_id,
                criterion_family=decision.criterion_family,
                outcome="not_qualified",
                reviewer_id=packet.review_panel.adjudicator_id,
            )
            for decision in packet.decisions
        ),
    )


def _prepare_completed_adjudication_packets(
    manifest: ExperimentManifest,
    template_report: AdjudicationTemplateReport,
    tmp_path: Path,
) -> tuple[BlindedArmAdjudicationPacket, ...]:
    """Turn six completed reviewer returns into three completed neutral adjudications."""
    adjudication_packet_paths = _prepare_adjudication_packet_templates(
        manifest,
        template_report,
        tmp_path,
    )
    completed_packets: list[BlindedArmAdjudicationPacket] = []
    for path in adjudication_packet_paths:
        completed_packet = _complete_adjudication_packet(load_blinded_adjudication_packet(path))
        path.write_text(completed_packet.model_dump_json(indent=2) + "\n", encoding="utf-8")
        completed_packets.append(load_blinded_adjudication_packet(path))
    return tuple(completed_packets)


def _prepare_adjudication_packet_templates(
    manifest: ExperimentManifest,
    template_report: AdjudicationTemplateReport,
    tmp_path: Path,
) -> tuple[Path, ...]:
    """Complete both reviewer copies and return the three blank adjudicator packets."""
    reviewer_packet_paths = tuple(
        _write_completed_reviewer_packet(path)
        for path in template_report.reviewer_packet_paths
    )
    adjudication_template_report = prepare_blinded_adjudication_packets(
        manifest,
        load_blinding_map(template_report.coordinator_blinding_map_path),
        reviewer_packet_paths=reviewer_packet_paths,
        adjudicator_output_root=tmp_path / "adjudication_packets",
    )
    return adjudication_template_report.adjudication_packet_paths


def test_ready_entry_requires_reviewed_translation() -> None:
    """A pending or machine translation cannot silently become the English arm."""
    with pytest.raises(ValidationError, match="reviewed English full text"):
        ExperimentEntry(
            case_id="case_001",
            source_family_id="article_001",
            family_cluster_id="family_001",
            native_fulltext=_source_artifact("native.md", "原文", "zh"),
            translation_review=TranslationReview(status="pending"),
            status="ready",
            index_assertion=ClinicalAssertion(
                assertion_id="assertion_001",
                gene_symbol="MECP2",
                disease_label="Rett syndrome",
                variant_hgvs_c="c.509C>T",
                planned_criterion_families=("PS2_PM6",),
            ),
        )


def test_model_reviewed_translation_requires_provenance() -> None:
    """A model review must name its single reviewer and record provenance notes."""
    english = _source_artifact("english.md", "English text", "en")
    alignment = _alignment_payload("原文", "English text")
    with pytest.raises(ValidationError, match="one reviewer_ids"):
        TranslationReview(
            status="model_reviewed",
            english_fulltext=english,
            alignment_relative_path=Path("alignment.json"),
            alignment_sha256=_sha256(alignment),
            reviewer_ids=("reviewer-a", "reviewer-b"),
            reviewed_on=date(2026, 8, 15),
            notes="model provenance",
        )
    with pytest.raises(ValidationError, match=r"notes \(model provenance\)"):
        TranslationReview(
            status="model_reviewed",
            english_fulltext=english,
            alignment_relative_path=Path("alignment.json"),
            alignment_sha256=_sha256(alignment),
            reviewer_ids=("model-review-20260815",),
            reviewed_on=date(2026, 8, 15),
        )


def test_ready_entry_accepts_model_reviewed_translation() -> None:
    """A provenance-documented model review satisfies readiness without human review."""
    native = "中文全文"
    english = "Reviewed English full text"
    alignment = _alignment_payload(native, english)
    entry = ExperimentEntry(
        case_id="case_002",
        source_family_id="article_002",
        family_cluster_id="family_002",
        native_fulltext=_source_artifact("native.md", native, "zh"),
        translation_review=TranslationReview(
            status="model_reviewed",
            english_fulltext=_source_artifact("english.md", english, "en"),
            alignment_relative_path=Path("alignment.json"),
            alignment_sha256=_sha256(alignment),
            reviewer_ids=("model-review-20260815",),
            reviewed_on=date(2026, 8, 15),
            notes="Machine-translated and model-reviewed; no human clinician review.",
        ),
        status="ready",
        index_assertion=ClinicalAssertion(
            assertion_id="assertion_002",
            gene_symbol="MECP2",
            disease_label="Rett syndrome",
            variant_hgvs_c="c.502C>T",
            planned_criterion_families=("PS2_PM6",),
        ),
    )
    assert entry.status == "ready"
    assert entry.translation_review.status == "model_reviewed"


def test_case_id_rejects_path_traversal() -> None:
    """A manifest case identifier cannot escape an output directory."""
    with pytest.raises(ValidationError, match="safe path component"):
        ExperimentEntry(
            case_id="../outside",
            source_family_id="article_001",
            family_cluster_id="family_001",
            native_fulltext=_source_artifact("native.md", "原文", "zh"),
            translation_review=TranslationReview(status="pending"),
            status="candidate",
        )


def test_native_experiment_document_must_not_be_english() -> None:
    """An English source cannot masquerade as the native-language arm."""
    with pytest.raises(ValidationError, match="non-English"):
        ExperimentEntry(
            case_id="case_001",
            source_family_id="article_001",
            family_cluster_id="family_001",
            native_fulltext=_source_artifact("native.md", "English full text", "en"),
            translation_review=TranslationReview(status="pending"),
            status="candidate",
        )


def test_ready_entries_deduplicate_family_clusters() -> None:
    """Two source records for one family cluster cannot expand the denominator."""
    first = _ready_manifest().entries[0]
    second = first.model_copy(
        update={
            "case_id": "case_002",
            "source_family_id": "article_002",
            "native_fulltext": _source_artifact("native-2.md", "另一篇原生全文", "zh"),
            "index_assertion": ClinicalAssertion(
                assertion_id="assertion_002",
                gene_symbol="MECP2",
                disease_label="Rett syndrome",
                variant_hgvs_c="c.808C>T",
                planned_criterion_families=("PS2_PM6",),
            ),
        }
    )
    with pytest.raises(ValidationError, match="Duplicate ready family_cluster_id"):
        ExperimentManifest(
            study_id="acmg-multilingual-pilot",
            protocol_version="v1",
            created_on=date(2026, 8, 14),
            entries=(first, second),
        )


def test_qualified_ps2_requires_confirmed_parentage() -> None:
    """The protocol rejects an assumed-de-novo observation as formal PS2."""
    with pytest.raises(ValidationError, match="parentage_status=confirmed"):
        ArmCriterionDecision(
            event_id="event_001",
            criterion_family="PS2_PM6",
            source_eligibility="eligible",
            outcome="qualified",
            criterion="PS2",
            strength="strong",
            parentage_status="not_reported",
            prerequisite_complete=True,
            required_fact_ids=("proband_variant", "parental_genotypes"),
            source_spans=(_span(),),
            reviewer_id="reviewer-a",
        )


def test_qualified_gold_ps2_requires_confirmed_parentage() -> None:
    """The source-grounded gold set applies the same PS2 parentage gate."""
    with pytest.raises(ValidationError, match="parentage_status=confirmed"):
        GoldCriterionEvent(
            event_id="event_001",
            assertion_id="assertion_001",
            source_family_id="article_001",
            criterion_family="PS2_PM6",
            source_eligibility="eligible",
            outcome="qualified",
            criterion="PS2",
            strength="strong",
            parentage_status="not_reported",
            prerequisite_complete=True,
            required_fact_ids=("proband_variant", "parental_genotypes"),
            source_spans=(_span(),),
        )


def test_complete_decision_set_requires_reviewer_attributed_assessments() -> None:
    """A completed arm cannot silently treat an unreviewed event as negative."""
    with pytest.raises(ValidationError, match="assessed, reviewer-attributed"):
        ArmDecisionSet(
            study_id="acmg-multilingual-pilot",
            manifest_sha256="0" * 64,
            arm="english_pivot",
            review_panel=_review_panel(),
            is_complete=True,
            decisions=(
                ArmCriterionDecision(
                    event_id="event_001",
                    criterion_family="PS2_PM6",
                    outcome="not_assessed",
                ),
            ),
        )


def test_materialization_freezes_reviewed_native_and_english_inputs(tmp_path: Path) -> None:
    """Materialized bundles preserve exact source text, hashes, and alignment metadata."""
    manifest = _ready_manifest()
    source_root = tmp_path / "source"
    _write_ready_source_files(source_root)

    report = materialize_reviewed_inputs(manifest, source_root, tmp_path / "inputs")

    original = json.loads((tmp_path / "inputs" / "case_001" / "original.json").read_text(encoding="utf-8"))
    translated = json.loads((tmp_path / "inputs" / "case_001" / "translated.json").read_text(encoding="utf-8"))
    assert report.inputs[0].case_id == "case_001"
    assert original["formatted_text"] == "原生全文"
    assert original["metadata"]["source_language"] == "zh"
    assert translated["formatted_text"] == "Reviewed English full text"
    assert translated["metadata"]["source_language"] == "en"
    expected_alignment = json.loads(_alignment_payload("原生全文", "Reviewed English full text"))
    assert translated["metadata"]["translation_alignment"] == expected_alignment
    assert json.loads((tmp_path / "inputs" / "case_001" / "translation_alignment.json").read_text(encoding="utf-8")) == expected_alignment



def _model_reviewed_manifest() -> ExperimentManifest:
    """Create a ready source family whose English text was model-reviewed, not human-reviewed."""
    native = "原生全文"
    english = "Reviewed English full text"
    alignment = _alignment_payload(native, english)
    entry = ExperimentEntry(
        case_id="case_003",
        source_family_id="article_003",
        family_cluster_id="family_003",
        native_fulltext=_source_artifact("native.md", native, "zh"),
        translation_review=TranslationReview(
            status="model_reviewed",
            english_fulltext=_source_artifact("english.md", english, "en"),
            alignment_relative_path=Path("alignment.json"),
            alignment_sha256=_sha256(alignment),
            reviewer_ids=("model-review-20260815",),
            reviewed_on=date(2026, 8, 15),
            notes="Machine-translated and model-reviewed; no human clinician review.",
        ),
        status="ready",
        index_assertion=ClinicalAssertion(
            assertion_id="assertion_003",
            gene_symbol="MECP2",
            disease_label="Rett syndrome",
            variant_hgvs_c="c.710C>G",
            planned_criterion_families=("PS2_PM6",),
        ),
    )
    return ExperimentManifest(
        study_id="model-review-pilot",
        protocol_version="v1",
        created_on=date(2026, 8, 15),
        entries=(entry,),
    )


def test_materialization_accepts_model_reviewed_translation(tmp_path: Path) -> None:
    """A provenance-documented model review materializes like a human review."""
    manifest = _model_reviewed_manifest()
    source_root = tmp_path / "source"
    _write_ready_source_files(source_root)

    report = materialize_reviewed_inputs(manifest, source_root, tmp_path / "inputs")

    assert report.inputs[0].case_id == "case_003"
    translated = json.loads((tmp_path / "inputs" / "case_003" / "translated.json").read_text(encoding="utf-8"))
    assert translated["formatted_text"] == "Reviewed English full text"
    assert translated["metadata"]["source_language"] == "en"

def test_materialization_rejects_source_hash_drift(tmp_path: Path) -> None:
    """A changed source cannot be run under an older frozen manifest."""
    manifest = _ready_manifest()
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "native.md").write_text("changed native text", encoding="utf-8")
    (source_root / "english.md").write_text("Reviewed English full text", encoding="utf-8")
    (source_root / "alignment.json").write_text(
        _alignment_payload("原生全文", "Reviewed English full text"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Content SHA-256"):
        materialize_reviewed_inputs(manifest, source_root, tmp_path / "inputs")


def test_materialization_rejects_partial_manifest(tmp_path: Path) -> None:
    """Unreviewed entries block a partial materialization run."""
    ready_entry = _ready_manifest().entries[0]
    pending_entry = ExperimentEntry(
        case_id="case_002",
        source_family_id="article_002",
        family_cluster_id="family_002",
        native_fulltext=_source_artifact("native-2.md", "另一篇原生全文", "zh"),
        translation_review=TranslationReview(status="pending"),
        status="needs_translation_review",
    )
    manifest = ExperimentManifest(
        study_id="acmg-multilingual-pilot",
        protocol_version="v1",
        created_on=date(2026, 8, 14),
        entries=(ready_entry, pending_entry),
    )

    with pytest.raises(ValueError, match="Cannot materialize a partial manifest"):
        materialize_reviewed_inputs(manifest, tmp_path / "source", tmp_path / "inputs")
    assert not (tmp_path / "inputs").exists()


def test_native_source_verification_accepts_pending_entries_and_rejects_hash_drift(tmp_path: Path) -> None:
    """Candidate source integrity can be audited before translation review completes."""
    native = "待审校原文"
    entry = ExperimentEntry(
        case_id="case_002",
        source_family_id="article_002",
        family_cluster_id="family_002",
        native_fulltext=_source_artifact("ground_truth/case_002/source.md", native, "zh"),
        translation_review=TranslationReview(status="pending"),
        status="needs_translation_review",
    )
    manifest = ExperimentManifest(
        study_id="acmg-multilingual-pilot",
        protocol_version="v1",
        created_on=date(2026, 8, 14),
        entries=(entry,),
    )
    source_root = tmp_path / "annotation"
    source_path = source_root / entry.native_fulltext.relative_path
    source_path.parent.mkdir(parents=True)
    source_path.write_text(native, encoding="utf-8")

    report = verify_native_source_artifacts(manifest, source_root, source_revision="corpus@abc123")
    receipt_path = tmp_path / "source-verification.json"
    write_native_source_verification_report(report, receipt_path)

    assert report.source_revision == "corpus@abc123"
    assert report.verified_sources[0].case_id == "case_002"
    assert report.verified_sources[0].sha256 == entry.native_fulltext.sha256
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["verified_sources"][0]["relative_path"] == (
        "ground_truth/case_002/source.md"
    )

    source_path.write_text("已经漂移的原文", encoding="utf-8")
    with pytest.raises(ValueError, match="Content SHA-256"):
        verify_native_source_artifacts(manifest, source_root)


def test_local_pilot_native_sources_match_manifest_when_annotation_root_is_configured() -> None:
    """Allow an opt-in integration audit against the ignored local Rett corpus."""
    source_root_text = os.environ.get("ACMG_MULTILINGUAL_ANNOTATION_ROOT")
    if source_root_text is None:
        pytest.skip("set ACMG_MULTILINGUAL_ANNOTATION_ROOT to run the local corpus audit")

    repository_root = Path(__file__).resolve().parents[4]
    manifest = load_manifest(repository_root / "benchmark/experiments/acmg_multilingual/pilot_candidates.json")
    report = verify_native_source_artifacts(
        manifest,
        Path(source_root_text),
        source_revision=os.environ.get("ACMG_MULTILINGUAL_CORPUS_REVISION", ""),
    )

    assert tuple(source.case_id for source in report.verified_sources) == (
        "rett_006",
        "rett_007",
        "rett_011",
        "rett_084",
        "rett_066",
        "rett_004",
    )
    assert report.source_root == Path(source_root_text).resolve()


def test_adjudication_templates_emit_opaque_reviewer_packets_and_sealed_map(tmp_path: Path) -> None:
    """Two isolated reviewers receive opaque copies while the map remains sealed."""
    manifest = _ready_manifest()
    arm_output_root = tmp_path / "arm_outputs"
    arm_run_report = _write_neutral_arm_outputs(arm_output_root, manifest)
    reviewer_output_root = tmp_path / "reviewer_packets"
    gold_reviewer_output_root = tmp_path / "gold_reviewer_packets"
    coordinator_output_root = tmp_path / "coordinator"
    review_panel = _review_panel()

    report = create_adjudication_templates(
        manifest,
        input_root=arm_output_root.parent / "input_bundles",
        arm_output_root=arm_output_root,
        arm_run_report=arm_run_report,
        reviewer_output_root=reviewer_output_root,
        gold_reviewer_output_root=gold_reviewer_output_root,
        coordinator_output_root=coordinator_output_root,
        review_panel=review_panel,
    )

    gold = GoldAdjudicationSet.model_validate_json(report.gold_template_path.read_text(encoding="utf-8"))
    gold_reviewer_sets = tuple(
        GoldReviewerDecisionSet.model_validate_json(path.read_text(encoding="utf-8"))
        for path in report.gold_reviewer_template_paths
    )
    packets = tuple(load_blinded_packet(path) for path in report.reviewer_packet_paths)
    blinding_map = load_blinding_map(report.coordinator_blinding_map_path)
    assert not gold.is_complete
    assert {event.outcome for event in gold.events} == {"not_assessed"}
    assert gold.review_panel == review_panel
    assert len(gold_reviewer_sets) == len(review_panel.reviewer_ids)
    assert {review.reviewer_id for review in gold_reviewer_sets} == set(review_panel.reviewer_ids)
    assert len(packets) == len(ACMG_MULTILINGUAL_ARMS) * len(review_panel.reviewer_ids)
    assert {packet.review_packet_id for packet in packets} == {
        entry.review_packet_id for entry in blinding_map.entries
    }
    assert blinding_map.review_panel == review_panel
    assert {entry.arm for entry in blinding_map.entries} == set(ACMG_MULTILINGUAL_ARMS)
    assert not (reviewer_output_root / "blinding_map.json").exists()
    assert not (gold_reviewer_output_root / "blinding_map.json").exists()
    for review_packet_id in {packet.review_packet_id for packet in packets}:
        assert {
            packet.reviewer_id
            for packet in packets
            if packet.review_packet_id == review_packet_id
        } == set(review_panel.reviewer_ids)
    for path, packet in zip(report.reviewer_packet_paths, packets, strict=True):
        packet_payload = path.read_text(encoding="utf-8")
        assert not packet.is_complete
        assert {decision.outcome for decision in packet.decisions} == {"not_assessed"}
        assert all(arm not in str(path) and arm not in packet_payload for arm in ACMG_MULTILINGUAL_ARMS)
        assert '"arm"' not in packet_payload
        assert {artifact.relative_path for artifact in packet.evidence_artifacts} == {
            Path("evidence/case_001.json")
        }


def test_unblind_completed_packets_produces_one_complete_set_per_arm(tmp_path: Path) -> None:
    """Only the coordinator map unblinds adjudicator-signed neutral packets."""
    manifest = _ready_manifest()
    arm_output_root = tmp_path / "arm_outputs"
    arm_run_report = _write_neutral_arm_outputs(arm_output_root, manifest)
    report = create_adjudication_templates(
        manifest,
        input_root=arm_output_root.parent / "input_bundles",
        arm_output_root=arm_output_root,
        arm_run_report=arm_run_report,
        reviewer_output_root=tmp_path / "reviewer_packets",
        gold_reviewer_output_root=tmp_path / "gold_reviewer_packets",
        coordinator_output_root=tmp_path / "coordinator",
        review_panel=_review_panel(),
    )
    blinding_map = load_blinding_map(report.coordinator_blinding_map_path)
    packets = _prepare_completed_adjudication_packets(manifest, report, tmp_path)

    decision_sets = unblind_decision_packets(manifest, blinding_map, packets)

    assert tuple(decision_set.arm for decision_set in decision_sets) == ACMG_MULTILINGUAL_ARMS
    assert all(decision_set.is_complete for decision_set in decision_sets)
    assert all(
        {decision.reviewer_id for decision in decision_set.decisions} == {blinding_map.review_panel.adjudicator_id}
        for decision_set in decision_sets
    )


def test_unblind_rejects_incomplete_or_missing_reviewer_packets(tmp_path: Path) -> None:
    """A coordinator cannot score incomplete or partial blinded adjudications."""
    manifest = _ready_manifest()
    arm_output_root = tmp_path / "arm_outputs"
    arm_run_report = _write_neutral_arm_outputs(arm_output_root, manifest)
    report = create_adjudication_templates(
        manifest,
        input_root=arm_output_root.parent / "input_bundles",
        arm_output_root=arm_output_root,
        arm_run_report=arm_run_report,
        reviewer_output_root=tmp_path / "reviewer_packets",
        gold_reviewer_output_root=tmp_path / "gold_reviewer_packets",
        coordinator_output_root=tmp_path / "coordinator",
        review_panel=_review_panel(),
    )
    blinding_map = load_blinding_map(report.coordinator_blinding_map_path)
    adjudication_packet_paths = _prepare_adjudication_packet_templates(manifest, report, tmp_path)
    packets = tuple(load_blinded_adjudication_packet(path) for path in adjudication_packet_paths)

    with pytest.raises(ValueError, match="adjudication packet is incomplete"):
        unblind_decision_packets(manifest, blinding_map, packets)

    completed_packets = tuple(_complete_adjudication_packet(packet) for packet in packets)
    with pytest.raises(ValueError, match="adjudication packets do not match blinding map"):
        unblind_decision_packets(manifest, blinding_map, completed_packets[:2])


def test_adjudication_templates_require_separate_coordinator_and_reviewer_roots(tmp_path: Path) -> None:
    """The sealed allocation map cannot be emitted into the reviewer delivery tree."""
    manifest = _ready_manifest()
    arm_output_root = tmp_path / "arm_outputs"
    arm_run_report = _write_neutral_arm_outputs(arm_output_root, manifest)
    shared_output_root = tmp_path / "shared"

    with pytest.raises(ValueError, match="separate, non-nested"):
        create_adjudication_templates(
            manifest,
            input_root=arm_output_root.parent / "input_bundles",
            arm_output_root=arm_output_root,
            arm_run_report=arm_run_report,
            reviewer_output_root=shared_output_root,
            gold_reviewer_output_root=tmp_path / "gold_reviewer_packets",
            coordinator_output_root=shared_output_root,
            review_panel=_review_panel(),
        )

    with pytest.raises(ValueError, match="reviewer_output_root must not contain"):
        create_adjudication_templates(
            manifest,
            input_root=arm_output_root.parent / "input_bundles",
            arm_output_root=arm_output_root,
            arm_run_report=arm_run_report,
            reviewer_output_root=tmp_path / "english_pivot_reviewers",
            gold_reviewer_output_root=tmp_path / "gold_reviewer_packets",
            coordinator_output_root=tmp_path / "coordinator",
            review_panel=_review_panel(),
        )


def test_adjudication_templates_reject_model_outputs_that_disclose_an_arm(tmp_path: Path) -> None:
    """A coordinator cannot accidentally distribute a result with an explicit arm label."""
    manifest = _ready_manifest()
    arm_output_root = tmp_path / "arm_outputs"
    arm_run_report = _write_neutral_arm_outputs(arm_output_root, manifest)
    labelled_result = arm_output_root / "case_001" / "english_pivot" / "extraction_result.json"
    labelled_result.write_text(json.dumps({"selected_mode": "english_pivot"}), encoding="utf-8")
    arm_run_report = arm_run_report.model_copy(
        update={
            "runs": tuple(
                run.model_copy(update={"result_sha256": hashlib.sha256(labelled_result.read_bytes()).hexdigest()})
                if run.result_path == labelled_result
                else run
                for run in arm_run_report.runs
            )
        }
    )

    with pytest.raises(ValueError, match="contains an experimental arm label"):
        create_adjudication_templates(
            manifest,
            input_root=arm_output_root.parent / "input_bundles",
            arm_output_root=arm_output_root,
            arm_run_report=arm_run_report,
            reviewer_output_root=tmp_path / "reviewer_packets",
            gold_reviewer_output_root=tmp_path / "gold_reviewer_packets",
            coordinator_output_root=tmp_path / "coordinator",
            review_panel=_review_panel(),
        )


def test_unblind_rejects_packet_evidence_that_differs_from_the_sealed_map(tmp_path: Path) -> None:
    """Review decisions remain bound to the model outputs issued by the coordinator."""
    manifest = _ready_manifest()
    arm_output_root = tmp_path / "arm_outputs"
    arm_run_report = _write_neutral_arm_outputs(arm_output_root, manifest)
    report = create_adjudication_templates(
        manifest,
        input_root=arm_output_root.parent / "input_bundles",
        arm_output_root=arm_output_root,
        arm_run_report=arm_run_report,
        reviewer_output_root=tmp_path / "reviewer_packets",
        gold_reviewer_output_root=tmp_path / "gold_reviewer_packets",
        coordinator_output_root=tmp_path / "coordinator",
        review_panel=_review_panel(),
    )
    packets = list(_prepare_completed_adjudication_packets(manifest, report, tmp_path))
    first_packet = packets[0]
    altered_artifact = first_packet.evidence_artifacts[0].model_copy(update={"sha256": "0" * 64})
    altered_reviewer_packets = tuple(
        BlindedArmDecisionPacket(
            study_id=reviewer_packet.study_id,
            manifest_sha256=reviewer_packet.manifest_sha256,
            review_packet_id=reviewer_packet.review_packet_id,
            reviewer_id=reviewer_packet.reviewer_id,
            evidence_artifacts=(altered_artifact,),
            is_complete=True,
            decisions=reviewer_packet.decisions,
        )
        for reviewer_packet in first_packet.reviewer_packets
    )
    packets[0] = BlindedArmAdjudicationPacket(
        study_id=first_packet.study_id,
        manifest_sha256=first_packet.manifest_sha256,
        review_packet_id=first_packet.review_packet_id,
        review_panel=first_packet.review_panel,
        evidence_artifacts=(altered_artifact,),
        reviewer_packets=altered_reviewer_packets,
        is_complete=True,
        decisions=first_packet.decisions,
    )

    with pytest.raises(ValueError, match="evidence does not match the sealed blinding map"):
        unblind_decision_packets(
            manifest,
            load_blinding_map(report.coordinator_blinding_map_path),
            tuple(packets),
        )


def test_reviewer_packet_loader_rejects_evidence_hash_drift(tmp_path: Path) -> None:
    """A reviewer decision cannot be scored against a changed copied model result."""
    manifest = _ready_manifest()
    arm_output_root = tmp_path / "arm_outputs"
    arm_run_report = _write_neutral_arm_outputs(arm_output_root, manifest)
    report = create_adjudication_templates(
        manifest,
        input_root=arm_output_root.parent / "input_bundles",
        arm_output_root=arm_output_root,
        arm_run_report=arm_run_report,
        reviewer_output_root=tmp_path / "reviewer_packets",
        gold_reviewer_output_root=tmp_path / "gold_reviewer_packets",
        coordinator_output_root=tmp_path / "coordinator",
        review_panel=_review_panel(),
    )
    packet_path = report.reviewer_packet_paths[0]
    evidence_path = packet_path.parent / "evidence" / "case_001.json"
    evidence_path.write_text(json.dumps({"status": "changed"}), encoding="utf-8")

    with pytest.raises(ValueError, match="evidence artifact SHA-256 does not match packet"):
        load_blinded_packet(packet_path)


def test_cli_score_uses_neutral_packet_and_coordinator_map_arguments() -> None:
    """The supported scoring interface never asks callers to name an arm."""
    args = _parse_args(
        (
            "score",
            "--manifest",
            "manifest.json",
            "--gold",
            "gold.json",
            "--adjudication-packet",
            "packet-a.json",
            "--adjudication-packet",
            "packet-b.json",
            "--adjudication-packet",
            "packet-c.json",
            "--coordinator-blinding-map",
            "map.json",
            "--report",
            "report.json",
        )
    )

    assert args.adjudication_packet == [Path("packet-a.json"), Path("packet-b.json"), Path("packet-c.json")]
    assert args.coordinator_blinding_map == Path("map.json")


def test_cli_verify_sources_keeps_pending_entries_out_of_the_model_run() -> None:
    """The source audit has its own explicit, non-materializing CLI command."""
    args = _parse_args(
        (
            "verify-sources",
            "--manifest",
            "manifest.json",
            "--source-root",
            "annotation",
            "--source-revision",
            "corpus@abc123",
            "--report",
            "source-verification.json",
        )
    )

    assert args.command == "verify-sources"
    assert args.source_root == Path("annotation")
    assert args.source_revision == "corpus@abc123"
    assert args.report == Path("source-verification.json")


def _coverage_entry(
    *,
    case_id: str,
    source_text: str,
    abstract_count: int,
    abstract_spans: tuple[CoverageSpan, ...],
    fulltext_count: int,
    fulltext_spans: tuple[CoverageSpan, ...],
) -> SourceCoverageEntry:
    """Build one deduplicated Stage-0 fact-table entry over a fixture text."""
    return SourceCoverageEntry(
        case_id=case_id,
        canonical_source=f"{case_id} canonical source",
        doi="10.0000/example.0001",
        native_language="zh",
        source_relative_path=f"{case_id}/source.md",
        source_sha256=_sha256(source_text),
        abstract=VisibilityFacts(
            visibility="english_abstract",
            pm6_eligible_count=abstract_count,
            spans=abstract_spans,
        ),
        fulltext=VisibilityFacts(
            visibility="native_fulltext",
            pm6_eligible_count=fulltext_count,
            spans=fulltext_spans,
        ),
        fulltext_increment=fulltext_count - abstract_count,
    )


def _write_coverage_table(
    source_root: Path,
    entry: SourceCoverageEntry,
    source_text: str,
) -> SourceCoverageFactTable:
    """Write one fixture source file and return its frozen fact table."""
    source_path = source_root / entry.source_relative_path
    source_path.parent.mkdir(parents=True)
    source_path.write_text(source_text, encoding="utf-8")
    return SourceCoverageFactTable(
        study_id="stage0-test",
        protocol_version="v1",
        corpus_revision="5b1f7673e7f4ea7922f3ad7efb79f25fdbfedab7",
        created_on="2026-08-15",
        criterion_family="PS2_PM6",
        reviewer_id="test-reviewer",
        provenance="test",
        review_scope_note="test fixture",
        sources=(entry,),
    )


def test_coverage_verifier_confirms_positive_spans(tmp_path: Path) -> None:
    """Every cited positive span is found verbatim and hashes match."""
    source_text = "line one\n父母未携带该变异位点\nline three\n"
    entry = _coverage_entry(
        case_id="case_001",
        source_text=source_text,
        abstract_count=0,
        abstract_spans=(),
        fulltext_count=1,
        fulltext_spans=(CoverageSpan(line=2, quote="父母未携带该变异位点", language="zh"),),
    )
    table = _write_coverage_table(tmp_path, entry, source_text)
    report = verify_source_coverage(table, tmp_path)
    assert report.total_positive_spans == 1
    assert report.verified_spans == 1
    assert report.drifted_sources == ()
    assert report.missed_spans == ()


def test_coverage_verifier_reports_source_hash_drift(tmp_path: Path) -> None:
    """A changed source file is flagged even if its cited line still matches."""
    source_text = "line one\n父母未携带该变异位点\n"
    entry = _coverage_entry(
        case_id="case_001",
        source_text=source_text,
        abstract_count=0,
        abstract_spans=(),
        fulltext_count=1,
        fulltext_spans=(CoverageSpan(line=2, quote="父母未携带该变异位点", language="zh"),),
    )
    table = _write_coverage_table(tmp_path, entry, source_text)
    (tmp_path / entry.source_relative_path).write_text(source_text + "appended\n", encoding="utf-8")
    report = verify_source_coverage(table, tmp_path)
    assert report.drifted_sources == ("case_001",)
    assert report.verified_spans == 1


def test_coverage_verifier_reports_missing_span(tmp_path: Path) -> None:
    """A cited quote absent from its line is reported, not silently ignored."""
    source_text = "line one\n父母未携带该变异位点\n"
    entry = _coverage_entry(
        case_id="case_001",
        source_text=source_text,
        abstract_count=0,
        abstract_spans=(),
        fulltext_count=1,
        fulltext_spans=(CoverageSpan(line=2, quote="父母均携带该变异位点", language="zh"),),
    )
    table = _write_coverage_table(tmp_path, entry, source_text)
    report = verify_source_coverage(table, tmp_path)
    assert report.verified_spans == 0
    assert report.missed_spans == ("case_001:2",)


def test_source_coverage_entry_rejects_inconsistent_increment() -> None:
    """The frozen increment must equal the full-text minus abstract count."""
    with pytest.raises(ValidationError):
        SourceCoverageEntry(
            case_id="case_001",
            canonical_source="src",
            doi="10.0000/example",
            native_language="zh",
            source_relative_path="case_001/source.md",
            source_sha256=_sha256("text"),
            abstract=VisibilityFacts(visibility="english_abstract", pm6_eligible_count=1),
            fulltext=VisibilityFacts(visibility="native_fulltext", pm6_eligible_count=2),
            fulltext_increment=0,
        )


def test_cli_verify_coverage_uses_facts_and_source_root() -> None:
    """The Stage-0 audit reads a fact table, not a code-level manifest."""
    args = _parse_args(
        (
            "verify-coverage",
            "--facts",
            "facts.json",
            "--source-root",
            "corpus",
            "--report",
            "coverage.json",
        )
    )
    assert args.facts == Path("facts.json")
    assert args.source_root == Path("corpus")
    assert args.report == Path("coverage.json")


def _write_corpus_source(root: Path, case_id: str, text: str) -> None:
    """Write one external-corpus source file below a tmp source root."""
    (root / case_id).mkdir(parents=True, exist_ok=True)
    (root / case_id / "source.md").write_text(text, encoding="utf-8")


def test_scan_corpus_deduplicates_and_classifies(tmp_path: Path) -> None:
    """Identical content collapses to one family; native language is script-derived."""
    zh_text = "中文全文内容" * 40
    _write_corpus_source(tmp_path, "rett_001", "This is an English Rett paper. " * 30)
    _write_corpus_source(tmp_path, "rett_002", zh_text)
    _write_corpus_source(tmp_path, "rett_003", zh_text)
    manifest = scan_corpus(tmp_path, corpus_revision="rev", created_on="2026-08-15")
    assert len(manifest.families) == 2
    families = {family.family_id: family for family in manifest.families}
    assert families["rett_001"].language == "en"
    assert families["rett_002"].language == "zh"
    assert families["rett_002"].alias_case_ids == ("rett_003",)


def test_scan_corpus_builds_cross_language_pairing_anchors(tmp_path: Path) -> None:
    """Only variants reported by both an English and a non-English family anchor a pairing."""
    _write_corpus_source(tmp_path, "rett_001", "The variant c.502C>T is reported here.")
    _write_corpus_source(tmp_path, "rett_002", "变异 c.502C>T 与 c.808C>T" + "中文" * 100)
    manifest = scan_corpus(tmp_path, corpus_revision="rev", created_on="2026-08-15")
    anchors = {anchor.variant: anchor for anchor in manifest.pairing_anchors}
    assert set(anchors) == {"c.502C>T"}
    assert anchors["c.502C>T"].english_family_ids == ("rett_001",)
    assert anchors["c.502C>T"].non_english_family_ids == ("rett_002",)


def test_verify_corpus_manifest_reports_hash_drift(tmp_path: Path) -> None:
    """A source changed after freezing is reported as drifted, not silently trusted."""
    _write_corpus_source(tmp_path, "rett_001", "English paper content. " * 20)
    _write_corpus_source(tmp_path, "rett_002", "中文" * 150)
    manifest = scan_corpus(tmp_path, corpus_revision="rev", created_on="2026-08-15")
    (tmp_path / "rett_001" / "source.md").write_text("Drifted English content. " * 20, encoding="utf-8")
    report = verify_corpus_manifest(manifest, tmp_path)
    assert report.total_families == 2
    assert report.verified_families == 1
    assert report.drifted_source_families == ("rett_001",)


def test_source_family_record_rejects_noncanonical_alias() -> None:
    """An alias that sorts before the canonical family id is rejected."""
    with pytest.raises(ValidationError):
        SourceFamilyRecord(
            family_id="rett_010",
            language="en",
            source_relative_path="rett_010/source.md",
            source_sha256=_sha256("x"),
            alias_case_ids=("rett_005",),
        )


def test_stage1_corpus_manifest_rejects_anchor_language_mismatch() -> None:
    """A pairing anchor must list English families under English, not non-English."""
    english = SourceFamilyRecord(
        family_id="rett_001",
        language="en",
        source_relative_path="rett_001/source.md",
        source_sha256=_sha256("a"),
    )
    chinese = SourceFamilyRecord(
        family_id="rett_002",
        language="zh",
        source_relative_path="rett_002/source.md",
        source_sha256=_sha256("b"),
    )
    with pytest.raises(ValidationError):
        Stage1CorpusManifest(
            study_id="s",
            protocol_version="v1",
            created_on="d",
            corpus_revision="r",
            corpus_note="n",
            families=(english, chinese),
            pairing_anchors=(
                VariantPairingAnchor(
                    variant="c.502C>T",
                    english_family_ids=("rett_002",),
                    non_english_family_ids=("rett_001",),
                ),
            ),
        )


def test_cli_freeze_corpus_and_verify_corpus() -> None:
    """The Stage-1 corpus commands read a source root, not a code-level manifest."""
    freeze = _parse_args(
        (
            "freeze-corpus",
            "--source-root",
            "corpus",
            "--corpus-revision",
            "rev",
            "--created-on",
            "2026-08-15",
            "--manifest",
            "manifest.json",
        )
    )
    assert freeze.source_root == Path("corpus")
    assert freeze.corpus_revision == "rev"
    assert freeze.manifest == Path("manifest.json")

    verify = _parse_args(
        (
            "verify-corpus",
            "--manifest",
            "manifest.json",
            "--source-root",
            "corpus",
            "--report",
            "report.json",
        )
    )
    assert verify.source_root == Path("corpus")
    assert verify.report == Path("report.json")


def test_code_recovery_uses_exact_formal_code_not_field_labels() -> None:
    """Scoring counts only exact expert-reviewed code recovery across paired arms."""
    manifest = _ready_manifest()
    manifest_sha256 = fingerprint_manifest(manifest)
    positive_event = GoldCriterionEvent(
        event_id="event_pm6",
        assertion_id="assertion_001",
        source_family_id="article_001",
        criterion_family="PS2_PM6",
        source_eligibility="eligible",
        outcome="qualified",
        criterion="PM6",
        strength="supporting",
        parentage_status="not_reported",
        prerequisite_complete=True,
        required_fact_ids=("proband_variant", "parental_genotypes"),
        source_spans=(_span(),),
    )
    negative_event = GoldCriterionEvent(
        event_id="event_ps3",
        assertion_id="assertion_001",
        source_family_id="article_001",
        criterion_family="PS3_BS3",
        outcome="not_qualified",
    )
    gold = _complete_gold(manifest, (positive_event, negative_event))
    qualified_pm6 = ArmCriterionDecision(
        event_id="event_pm6",
        criterion_family="PS2_PM6",
        source_eligibility="eligible",
        outcome="qualified",
        criterion="PM6",
        strength="supporting",
        parentage_status="not_reported",
        prerequisite_complete=True,
        required_fact_ids=("proband_variant", "parental_genotypes"),
        source_spans=(_span(),),
        reviewer_id="arm-reviewer",
    )
    english_decisions = ArmDecisionSet(
        study_id=manifest.study_id,
        manifest_sha256=manifest_sha256,
        arm="english_pivot",
        review_panel=_review_panel(),
        is_complete=True,
        decisions=(
            ArmCriterionDecision(
                event_id="event_pm6",
                criterion_family="PS2_PM6",
                outcome="not_qualified",
                reviewer_id="arm-reviewer",
            ),
            ArmCriterionDecision(
                event_id="event_ps3",
                criterion_family="PS3_BS3",
                source_eligibility="eligible",
                outcome="qualified",
                criterion="PS3",
                strength="strong",
                prerequisite_complete=True,
                required_fact_ids=("assay",),
                source_spans=(_span("en", "translated"),),
                reviewer_id="arm-reviewer",
            ),
        ),
    )
    native_decisions = ArmDecisionSet(
        study_id=manifest.study_id,
        manifest_sha256=manifest_sha256,
        arm="native_only",
        review_panel=_review_panel(),
        is_complete=True,
        decisions=(
            qualified_pm6,
            ArmCriterionDecision(
                event_id="event_ps3",
                criterion_family="PS3_BS3",
                outcome="not_qualified",
                reviewer_id="arm-reviewer",
            ),
        ),
    )
    dual_decisions = ArmDecisionSet(
        study_id=manifest.study_id,
        manifest_sha256=manifest_sha256,
        arm="dual_track",
        review_panel=_review_panel(),
        is_complete=True,
        decisions=(
            qualified_pm6,
            ArmCriterionDecision(
                event_id="event_ps3",
                criterion_family="PS3_BS3",
                outcome="not_qualified",
                reviewer_id="arm-reviewer",
            ),
        ),
    )

    report = evaluate_code_recovery(manifest, gold, (english_decisions, native_decisions, dual_decisions))

    english_metric, native_metric, dual_metric = report.metrics
    assert (english_metric.true_positive_count, english_metric.false_positive_count, english_metric.false_negative_count) == (
        0,
        1,
        1,
    )
    assert (native_metric.precision, native_metric.recall, dual_metric.f1) == (1.0, 1.0, 1.0)
    comparison = report.comparisons[0]
    assert comparison.comparison_arm == "native_only"
    assert comparison.comparison_only_event_ids == ("event_pm6",)


def test_wrong_qualified_strength_counts_as_false_positive_and_false_negative() -> None:
    """A qualified but wrong-strength call is not a precision-neutral miss."""
    ready_entry = _ready_manifest().entries[0]
    manifest = ExperimentManifest(
        study_id="acmg-multilingual-pilot",
        protocol_version="v1",
        created_on=date(2026, 8, 14),
        entries=(
            ready_entry.model_copy(
                update={
                    "index_assertion": ClinicalAssertion(
                        assertion_id="assertion_001",
                        gene_symbol="MECP2",
                        disease_label="Rett syndrome",
                        variant_hgvs_c="c.509C>T",
                        planned_criterion_families=("PS2_PM6",),
                    )
                }
            ),
        ),
    )
    manifest_sha256 = fingerprint_manifest(manifest)
    event = GoldCriterionEvent(
        event_id="event_pm6",
        assertion_id="assertion_001",
        source_family_id="article_001",
        criterion_family="PS2_PM6",
        source_eligibility="eligible",
        outcome="qualified",
        criterion="PM6",
        strength="supporting",
        parentage_status="not_reported",
        prerequisite_complete=True,
        required_fact_ids=("proband_variant", "parental_genotypes"),
        source_spans=(_span(),),
    )
    gold = _complete_gold(manifest, (event,))
    wrong_strength = ArmCriterionDecision(
        event_id=event.event_id,
        criterion_family=event.criterion_family,
        source_eligibility="eligible",
        outcome="qualified",
        criterion="PM6",
        strength="moderate",
        parentage_status="not_reported",
        prerequisite_complete=True,
        required_fact_ids=("proband_variant", "parental_genotypes"),
        source_spans=(_span(),),
        reviewer_id="arm-reviewer",
    )
    decision_sets = tuple(
        ArmDecisionSet(
            study_id=manifest.study_id,
            manifest_sha256=manifest_sha256,
            arm=arm,
            review_panel=_review_panel(),
            is_complete=True,
            decisions=(
                wrong_strength.model_copy(
                    update={
                        "source_spans": (
                            _span(
                                "en" if arm == "english_pivot" else "zh",
                                "translated" if arm == "english_pivot" else "original",
                            ),
                        )
                    }
                ),
            ),
        )
        for arm in ACMG_MULTILINGUAL_ARMS
    )

    report = evaluate_code_recovery(manifest, gold, decision_sets)

    assert all(
        (metric.true_positive_count, metric.false_positive_count, metric.false_negative_count) == (0, 1, 1)
        for metric in report.metrics
    )


def test_scoring_enforces_visible_source_artifacts_not_source_span_language() -> None:
    """Visibility follows frozen input artifacts, so original English captions stay valid."""
    ready_entry = _ready_manifest().entries[0]
    manifest = ExperimentManifest(
        study_id="acmg-multilingual-pilot",
        protocol_version="v1",
        created_on=date(2026, 8, 14),
        entries=(
            ready_entry.model_copy(
                update={
                    "index_assertion": ClinicalAssertion(
                        assertion_id="assertion_001",
                        gene_symbol="MECP2",
                        disease_label="Rett syndrome",
                        variant_hgvs_c="c.509C>T",
                        planned_criterion_families=("PS2_PM6",),
                    )
                }
            ),
        ),
    )
    manifest_sha256 = fingerprint_manifest(manifest)
    event = GoldCriterionEvent(
        event_id="event_pm6",
        assertion_id="assertion_001",
        source_family_id="article_001",
        criterion_family="PS2_PM6",
        source_eligibility="eligible",
        outcome="qualified",
        criterion="PM6",
        strength="supporting",
        parentage_status="not_reported",
        prerequisite_complete=True,
        required_fact_ids=("proband_variant", "parental_genotypes"),
        source_spans=(_span(),),
    )
    gold = _complete_gold(manifest, (event,))
    decision_sets = tuple(
        ArmDecisionSet(
            study_id=manifest.study_id,
            manifest_sha256=manifest_sha256,
            arm=arm,
            review_panel=_review_panel(),
            is_complete=True,
            decisions=(
                ArmCriterionDecision(
                    event_id=event.event_id,
                    criterion_family=event.criterion_family,
                    source_eligibility="eligible",
                    outcome="qualified",
                    criterion="PM6",
                    strength="supporting",
                    parentage_status="not_reported",
                    prerequisite_complete=True,
                    required_fact_ids=("proband_variant", "parental_genotypes"),
                    source_spans=(_span(),),
                    reviewer_id="arm-reviewer",
                ),
            ),
        )
        for arm in ACMG_MULTILINGUAL_ARMS
    )

    with pytest.raises(ValueError, match="english_pivot: event_pm6 cites 'original' artifact"):
        evaluate_code_recovery(manifest, gold, decision_sets)

    visible_decision_sets = tuple(
        ArmDecisionSet(
            study_id=manifest.study_id,
            manifest_sha256=manifest_sha256,
            arm=arm,
            review_panel=_review_panel(),
            is_complete=True,
            decisions=(
                ArmCriterionDecision(
                    event_id=event.event_id,
                    criterion_family=event.criterion_family,
                    source_eligibility="eligible",
                    outcome="qualified",
                    criterion="PM6",
                    strength="supporting",
                    parentage_status="not_reported",
                    prerequisite_complete=True,
                    required_fact_ids=("proband_variant", "parental_genotypes"),
                    source_spans=(
                        _span(
                            "en",
                            "translated" if arm == "english_pivot" else "original",
                        ),
                    ),
                    reviewer_id="arm-reviewer",
                ),
            ),
        )
        for arm in ACMG_MULTILINGUAL_ARMS
    )

    report = evaluate_code_recovery(manifest, gold, visible_decision_sets)

    assert all(metric.true_positive_count == 1 for metric in report.metrics)


def test_scoring_rejects_unplanned_or_mismatched_gold_events() -> None:
    """Gold events must retain the frozen assertion-source-family and endpoint pairing."""
    first = _ready_manifest().entries[0]
    second = first.model_copy(
        update={
            "case_id": "case_002",
            "source_family_id": "article_002",
            "family_cluster_id": "family_002",
            "native_fulltext": _source_artifact("native-2.md", "另一篇原生全文", "zh"),
            "index_assertion": ClinicalAssertion(
                assertion_id="assertion_002",
                gene_symbol="MECP2",
                disease_label="Rett syndrome",
                variant_hgvs_c="c.808C>T",
                planned_criterion_families=("PM3",),
            ),
        }
    )
    manifest = ExperimentManifest(
        study_id="acmg-multilingual-pilot",
        protocol_version="v1",
        created_on=date(2026, 8, 14),
        entries=(first, second),
    )
    manifest_sha256 = fingerprint_manifest(manifest)
    mismatched_event = GoldCriterionEvent(
        event_id="event_pm6",
        assertion_id="assertion_001",
        source_family_id="article_002",
        criterion_family="PS2_PM6",
        outcome="not_qualified",
    )
    unplanned_event = GoldCriterionEvent(
        event_id="event_pm3",
        assertion_id="assertion_001",
        source_family_id="article_001",
        criterion_family="PM3",
        outcome="not_qualified",
    )
    decision_sets = tuple(
        ArmDecisionSet(
            study_id=manifest.study_id,
            manifest_sha256=manifest_sha256,
            arm=arm,
            review_panel=_review_panel(),
            is_complete=True,
            decisions=(
                ArmCriterionDecision(
                    event_id=mismatched_event.event_id,
                    criterion_family=mismatched_event.criterion_family,
                    outcome="not_qualified",
                    reviewer_id="arm-reviewer",
                ),
            ),
        )
        for arm in ACMG_MULTILINGUAL_ARMS
    )
    mismatched_gold = _complete_gold(manifest, (mismatched_event,))
    with pytest.raises(ValueError, match="does not belong to its assertion source family"):
        evaluate_code_recovery(manifest, mismatched_gold, decision_sets)

    unplanned_gold = _complete_gold(manifest, (unplanned_event,))
    unplanned_decision_sets = tuple(
        ArmDecisionSet(
            study_id=manifest.study_id,
            manifest_sha256=manifest_sha256,
            arm=arm,
            review_panel=_review_panel(),
            is_complete=True,
            decisions=(
                ArmCriterionDecision(
                    event_id=unplanned_event.event_id,
                    criterion_family=unplanned_event.criterion_family,
                    outcome="not_qualified",
                    reviewer_id="arm-reviewer",
                ),
            ),
        )
        for arm in ACMG_MULTILINGUAL_ARMS
    )
    with pytest.raises(ValueError, match="uses an unplanned criterion family"):
        evaluate_code_recovery(manifest, unplanned_gold, unplanned_decision_sets)


class _FakeResult(BaseModel):
    """Tiny persisted result used to test runner arm selection without model calls."""

    selected_mode: str


class _FakeService:
    """Captures mode selection for a synthetic no-network extraction run."""

    def __init__(self) -> None:
        self.modes: list[str] = []
        self.translation_traceback_enabled: list[bool] = []

    async def run_dual(
        self,
        documents: object,
        *,
        extraction_track_mode: str,
        enable_translation_traceback: bool,
    ) -> BaseModel:
        self.modes.append(extraction_track_mode)
        self.translation_traceback_enabled.append(enable_translation_traceback)
        return _FakeResult(selected_mode=extraction_track_mode)


def _fake_document_builder(input_dir: Path, assertion: ClinicalAssertion) -> object:
    """Return an opaque object because the fake service does not inspect documents."""
    del input_dir, assertion
    return object()


@pytest.mark.asyncio
async def test_runner_executes_frozen_inputs_in_all_three_track_modes(tmp_path: Path) -> None:
    """The runner reuses one prepared bundle and never asks the service to translate anew."""
    manifest = _ready_manifest()
    source_root = tmp_path / "source"
    _write_ready_source_files(source_root)
    input_root = tmp_path / "inputs"
    materialize_reviewed_inputs(manifest, source_root, input_root)
    service = _FakeService()

    report = await run_ready_arms(
        manifest=manifest,
        input_root=input_root,
        output_root=tmp_path / "outputs",
        service=service,
        document_builder=_fake_document_builder,
    )

    assert service.modes == ["english_pivot", "original_only", "dual"]
    assert service.translation_traceback_enabled == [False, True, True]
    assert len(report.runs) == 3
    assert {run.result_path.name for run in report.runs} == {"extraction_result.json"}
    assert all(run.result_path.is_file() for run in report.runs)


@pytest.mark.asyncio
async def test_runner_rejects_changed_materialized_bundle(tmp_path: Path) -> None:
    """The runner refuses an input edit before it invokes an extraction arm."""
    manifest = _ready_manifest()
    source_root = tmp_path / "source"
    _write_ready_source_files(source_root)
    input_root = tmp_path / "inputs"
    materialize_reviewed_inputs(manifest, source_root, input_root)
    translated_path = input_root / "case_001" / "translated.json"
    translated = json.loads(translated_path.read_text(encoding="utf-8"))
    translated["formatted_text"] = "Changed after materialization"
    translated_path.write_text(json.dumps(translated), encoding="utf-8")
    service = _FakeService()

    with pytest.raises(ValueError, match="content SHA-256"):
        await run_ready_arms(
            manifest=manifest,
            input_root=input_root,
            output_root=tmp_path / "outputs",
            service=service,
            document_builder=_fake_document_builder,
        )
    assert service.modes == []


_TEST_ENGLISH_QUERY = PlannedQuery(
    provider_language="en",
    query="MECP2 c.710C>G Rett syndrome de novo parents",
)
_TEST_NATIVE_QUERY = PlannedQuery(
    provider_language="zh",
    query="MECP2 基因 c.710C>G Rett综合征 父母未携带该变异位点",
)


def _retrieval_target(
    *,
    target_id: str = "mecp2_c710cg_ps2pm6",
    doi: str = "10.20047/j.issn1673-7210.2024.05.45",
    eligible_event_count: int = 1,
) -> RetrievalTarget:
    """Build one retrieval target whose multilingual arm supersets the English arm."""
    return RetrievalTarget(
        target_id=target_id,
        gene_symbol="MECP2",
        disease_label="Rett syndrome",
        variant_hgvs_c="c.710C>G",
        criterion_family="PS2_PM6",
        eligible_sources=(
            EligibleSource(
                source_family_id="rett_011",
                doi=doi,
                native_language="zh",
                eligible_event_count=eligible_event_count,
            ),
        ),
        english_only_queries=(_TEST_ENGLISH_QUERY,),
        multilingual_queries=(_TEST_ENGLISH_QUERY, _TEST_NATIVE_QUERY),
    )


def _retrieval_ledger(
    *targets: RetrievalTarget,
    english_source_adjudication: str = "complete",
) -> RetrievalTargetLedger:
    """Build a frozen retrieval ledger around the given targets."""
    return RetrievalTargetLedger(
        study_id="retrieval-test",
        protocol_version="v1",
        created_on="2026-08-18",
        corpus_revision="5b1f7673e7f4ea7922f3ad7efb79f25fdbfedab7",
        provenance="test",
        denominator_note="test fixture",
        english_source_adjudication=english_source_adjudication,
        targets=targets,
    )


def _arm_probes(
    ledger: RetrievalTargetLedger,
    *,
    english_hits: tuple[RetrievalHit, ...],
    multilingual_hits: tuple[RetrievalHit, ...],
) -> RetrievalProbeLedger:
    """Record one English-only and one multilingual probe per ledger target."""
    probes: list[ArmProbe] = []
    for target in ledger.targets:
        probes.append(
            ArmProbe(
                target_id=target.target_id,
                arm="english_only",
                probed_on="2026-08-18",
                queries=target.english_only_queries,
                providers=("crossref",),
                hits=english_hits,
            )
        )
        probes.append(
            ArmProbe(
                target_id=target.target_id,
                arm="multilingual",
                probed_on="2026-08-18",
                queries=target.multilingual_queries,
                providers=("crossref",),
                hits=multilingual_hits,
            )
        )
    return RetrievalProbeLedger(
        study_id=ledger.study_id,
        target_ledger_fingerprint=ledger.fingerprint(),
        probes=tuple(probes),
    )


def test_normalize_doi_strips_resolver_prefix() -> None:
    """A resolver URL and a bare DOI normalize to the same matching key."""
    assert normalize_doi("https://doi.org/10.20047/J.ISSN1673-7210.2024.05.45") == (
        "10.20047/j.issn1673-7210.2024.05.45"
    )
    assert normalize_doi("  doi:10.3969/J.ISSN.1000-3606.2018.11.005 ") == (
        "10.3969/j.issn.1000-3606.2018.11.005"
    )


def test_retrieval_target_requires_multilingual_superset() -> None:
    """The all-source arm may add queries but must never drop an English-only query."""
    with pytest.raises(ValidationError):
        RetrievalTarget(
            target_id="mecp2_c710cg_ps2pm6",
            gene_symbol="MECP2",
            disease_label="Rett syndrome",
            variant_hgvs_c="c.710C>G",
            criterion_family="PS2_PM6",
            eligible_sources=(
                EligibleSource(
                    source_family_id="rett_011",
                    doi="10.20047/j.issn1673-7210.2024.05.45",
                    native_language="zh",
                    eligible_event_count=1,
                ),
            ),
            english_only_queries=(_TEST_ENGLISH_QUERY,),
            multilingual_queries=(_TEST_NATIVE_QUERY,),
        )


def test_eligible_source_rejects_unnormalized_doi() -> None:
    """Gold DOIs must be stored normalized so matching stays a plain equality."""
    with pytest.raises(ValidationError):
        EligibleSource(
            source_family_id="rett_011",
            doi="https://doi.org/10.20047/j.issn1673-7210.2024.05.45",
            native_language="zh",
            eligible_event_count=1,
        )


def test_score_retrieval_blocks_pending_english_adjudication() -> None:
    """Scoring refuses to run while the English gold side is unadjudicated."""
    ledger = _retrieval_ledger(_retrieval_target(), english_source_adjudication="pending")
    probes = _arm_probes(ledger, english_hits=(), multilingual_hits=())
    with pytest.raises(ValueError, match="english_source_adjudication"):
        score_retrieval_reachability(ledger, probes)


def test_score_retrieval_credits_only_doi_matches() -> None:
    """A multilingual-only DOI hit becomes a discordant pair, a title hit does not."""
    ledger = _retrieval_ledger(_retrieval_target())
    probes = _arm_probes(
        ledger,
        english_hits=(
            RetrievalHit(
                provider="crossref",
                doi="10.1038/gim.2015.30",
                title="Standards and guidelines",
            ),
        ),
        multilingual_hits=(
            RetrievalHit(
                provider="crossref",
                doi="10.20047/j.issn1673-7210.2024.05.45",
                title="MECP2 case report",
            ),
        ),
    )
    report = score_retrieval_reachability(ledger, probes)
    metric_by_arm = {metric.arm: metric for metric in report.metrics}
    assert metric_by_arm["english_only"].reached_target_count == 0
    assert metric_by_arm["english_only"].zero_reach_target_ids == ("mecp2_c710cg_ps2pm6",)
    assert metric_by_arm["multilingual"].reached_target_count == 1
    assert metric_by_arm["multilingual"].event_recall == 1.0
    comparison = report.comparisons[0]
    assert comparison.comparison_only_count == 1
    assert comparison.baseline_only_count == 0
    assert comparison.comparison_only_target_ids == ("mecp2_c710cg_ps2pm6",)


def test_score_retrieval_matches_on_pmid_when_record_has_no_doi() -> None:
    """PubMed records for Chinese journals carry a PMID but no DOI, and still count."""
    target = RetrievalTarget(
        target_id="mecp2_c316ct_ps2pm6",
        gene_symbol="MECP2",
        disease_label="Rett syndrome",
        variant_hgvs_c="c.316C>T",
        criterion_family="PS2_PM6",
        eligible_sources=(
            EligibleSource(
                source_family_id="rett_006",
                doi="10.7499/j.issn.1008-8830.2014.04.017",
                pmid="24750837",
                native_language="zh",
                eligible_event_count=1,
            ),
        ),
        english_only_queries=(_TEST_ENGLISH_QUERY,),
        multilingual_queries=(_TEST_ENGLISH_QUERY, _TEST_NATIVE_QUERY),
    )
    ledger = _retrieval_ledger(target)
    pmid_only = (RetrievalHit(provider="pubmed", pmid="24750837", title="[Clinical features]"),)
    report = score_retrieval_reachability(
        ledger,
        _arm_probes(ledger, english_hits=pmid_only, multilingual_hits=pmid_only),
    )
    assert all(result.reached for result in report.reachability)
    assert report.comparisons[0].both_reached_count == 1


def test_retrieval_hit_rejects_non_numeric_pmid() -> None:
    """A malformed PMID must not silently become an unmatchable identifier."""
    with pytest.raises(ValidationError):
        RetrievalHit(provider="pubmed", pmid="PMID24750837")


def test_score_retrieval_ignores_title_only_match() -> None:
    """A hit without a DOI never counts as reaching a gold source."""
    ledger = _retrieval_ledger(_retrieval_target())
    title_only = (RetrievalHit(provider="crossref", title="MECP2 基因变异所致Rett综合征1例"),)
    report = score_retrieval_reachability(
        ledger,
        _arm_probes(ledger, english_hits=title_only, multilingual_hits=title_only),
    )
    assert all(not result.reached for result in report.reachability)
    assert report.comparisons[0].neither_reached_count == 1


def test_score_retrieval_flags_missing_probe() -> None:
    """An unprobed target/arm pair is reported instead of silently scoring as a miss."""
    ledger = _retrieval_ledger(_retrieval_target())
    probes = RetrievalProbeLedger(
        study_id=ledger.study_id,
        target_ledger_fingerprint=ledger.fingerprint(),
        probes=(
            ArmProbe(
                target_id="mecp2_c710cg_ps2pm6",
                arm="multilingual",
                probed_on="2026-08-18",
                queries=ledger.targets[0].multilingual_queries,
                providers=("crossref",),
                hits=(),
            ),
        ),
    )
    report = score_retrieval_reachability(ledger, probes)
    assert report.missing_probe_keys == ("mecp2_c710cg_ps2pm6:english_only",)


def test_score_retrieval_rejects_fingerprint_drift() -> None:
    """Probes recorded against edited targets cannot be scored."""
    ledger = _retrieval_ledger(_retrieval_target())
    probes = _arm_probes(ledger, english_hits=(), multilingual_hits=())
    edited = _retrieval_ledger(_retrieval_target(eligible_event_count=4))
    with pytest.raises(ValueError, match="different target ledger fingerprint"):
        score_retrieval_reachability(edited, probes)


class _FakeSearcher:
    """Records probe queries and returns fixed candidates without network access."""

    def __init__(self, hits_by_language: dict[str, tuple[RetrievalHit, ...]]) -> None:
        self.calls: list[tuple[str, str]] = []
        self._hits_by_language = hits_by_language

    async def __call__(self, *, planned: PlannedQuery, candidate_limit: int) -> ProbeSearchResult:
        del candidate_limit
        self.calls.append((planned.provider_language, planned.query))
        return ProbeSearchResult(
            providers=(f"{planned.provider_language}-provider",),
            hits=self._hits_by_language.get(planned.provider_language, ()),
        )


@pytest.mark.asyncio
async def test_probe_retrieval_arms_sends_frozen_queries_per_arm() -> None:
    """Each arm sends exactly its frozen query set and repeated candidates collapse."""
    ledger = _retrieval_ledger(_retrieval_target())
    shared_hit = RetrievalHit(provider="crossref", doi="10.20047/j.issn1673-7210.2024.05.45")
    searcher = _FakeSearcher({"en": (shared_hit,), "zh": (shared_hit,)})

    probes = await probe_retrieval_arms(ledger, probed_on="2026-08-18", searcher=searcher)

    assert [language for language, _ in searcher.calls] == ["en", "en", "zh"]
    probe_by_arm = {probe.arm: probe for probe in probes.probes}
    assert probe_by_arm["english_only"].providers == ("en-provider",)
    assert probe_by_arm["multilingual"].providers == ("en-provider", "zh-provider")
    assert len(probe_by_arm["multilingual"].hits) == 1
    assert probes.target_ledger_fingerprint == ledger.fingerprint()


def test_frozen_retrieval_target_ledger_is_loadable_and_still_gated() -> None:
    """The committed ledger enumerates the eleven Stage-0 targets and blocks scoring."""
    repository_root = Path(__file__).resolve().parents[4]
    ledger = load_retrieval_target_ledger(
        repository_root / "benchmark/experiments/acmg_multilingual/retrieval_targets.json"
    )
    assert len(ledger.targets) == 11
    assert sum(target.eligible_event_total() for target in ledger.targets) == 11
    assert ledger.english_source_adjudication == "pending"
    assert ledger.pending_doi_source_family_ids == ("rett_004", "rett_066", "rett_085")
    rett_006_pmids = {
        source.pmid
        for target in ledger.targets
        for source in target.eligible_sources
        if source.source_family_id == "rett_006"
    }
    assert rett_006_pmids == {"24750837"}


def test_cli_score_retrieval_reads_targets_and_probes() -> None:
    """The retrieval endpoint is scored from frozen files, never a live search."""
    args = _parse_args(
        (
            "score-retrieval",
            "--targets",
            "targets.json",
            "--probes",
            "probes.json",
            "--report",
            "retrieval.json",
        )
    )
    assert args.targets == Path("targets.json")
    assert args.probes == Path("probes.json")
    assert args.report == Path("retrieval.json")


def _write_fidelity_case(
    reviewed_root: Path,
    *,
    native_text: str,
    english_text: str,
    facts: tuple[CriticalFact, ...],
    case_id: str = "case_001",
) -> TranslationFidelityFactTable:
    """Write one native/English/alignment triple and return its frozen fact table."""
    case_dir = reviewed_root / case_id
    case_dir.mkdir(parents=True)
    (case_dir / "source.md").write_text(native_text, encoding="utf-8")
    (case_dir / "english_fulltext.md").write_text(english_text, encoding="utf-8")
    alignment_text = json.dumps(
        [{"chunk_id": f"{case_id}-whole", "original_text": native_text, "english_text": english_text}],
        ensure_ascii=False,
    )
    (case_dir / "alignment.json").write_text(alignment_text, encoding="utf-8")
    return TranslationFidelityFactTable(
        study_id="fidelity-test",
        protocol_version="v1",
        created_on="2026-08-18",
        translation_review_status="model_reviewed",
        provenance="test",
        scope_note="test fixture",
        entries=(
            TranslationFidelityEntry(
                case_id=case_id,
                native_relative_path=f"{case_id}/source.md",
                native_sha256=_sha256(native_text),
                english_relative_path=f"{case_id}/english_fulltext.md",
                english_sha256=_sha256(english_text),
                alignment_relative_path=f"{case_id}/alignment.json",
                alignment_sha256=_sha256(alignment_text),
                facts=facts,
            ),
        ),
    )


def test_translation_fidelity_confirms_retained_fact(tmp_path: Path) -> None:
    """A fact surviving into the English full text is retained at both levels."""
    table = _write_fidelity_case(
        tmp_path,
        native_text="标题\n父母未携带该变异位点\n",
        english_text="Title\nthe parents did not carry this variant site\n",
        facts=(
            CriticalFact(
                fact_id="parental_negative",
                native_line=2,
                native_quote="父母未携带该变异位点",
                required_english_tokens=("the parents did not carry",),
            ),
        ),
    )
    report = verify_translation_fidelity(table, tmp_path)
    assert report.retained_fact_count == 1
    assert report.lost_fact_ids == ()
    assert report.drifted_artifacts == ()
    assert report.entries[0].facts[0].retained_in_aligned_chunk is True


def test_translation_fidelity_reports_fact_lost_in_translation(tmp_path: Path) -> None:
    """A dropped parental-negative sentence is named, not averaged away."""
    table = _write_fidelity_case(
        tmp_path,
        native_text="标题\n父母未携带该变异位点\n",
        english_text="Title\na de novo variant was identified\n",
        facts=(
            CriticalFact(
                fact_id="parental_negative",
                native_line=2,
                native_quote="父母未携带该变异位点",
                required_english_tokens=("the parents did not carry",),
            ),
        ),
    )
    report = verify_translation_fidelity(table, tmp_path)
    assert report.retained_fact_count == 0
    assert report.lost_fact_ids == ("case_001:parental_negative",)
    assert report.entries[0].facts[0].missing_english_tokens == ("the parents did not carry",)


def test_translation_fidelity_matches_hgvs_despite_ocr_spacing(tmp_path: Path) -> None:
    """LaTeX-spaced OCR HGVS still matches a clean English token after collapsing."""
    table = _write_fidelity_case(
        tmp_path,
        native_text="标题\n错义变异 $_ { \\mathrm { c . 7 1 0 C > G } }$ 经 Sanger 测序证实\n",
        english_text="Title\nmissense variant c.710C>G confirmed by Sanger sequencing\n",
        facts=(
            CriticalFact(
                fact_id="target_variant",
                native_line=2,
                native_quote="c.710C>G",
                required_english_tokens=("c.710C>G",),
            ),
        ),
    )
    report = verify_translation_fidelity(table, tmp_path)
    assert report.unverified_native_quote_ids == ()
    assert report.retained_fact_count == 1


def test_translation_fidelity_flags_artifact_drift(tmp_path: Path) -> None:
    """An edited English full text is reported even when the fact still survives."""
    table = _write_fidelity_case(
        tmp_path,
        native_text="标题\n父母未携带该变异位点\n",
        english_text="Title\nthe parents did not carry this variant site\n",
        facts=(
            CriticalFact(
                fact_id="parental_negative",
                native_line=2,
                native_quote="父母未携带该变异位点",
                required_english_tokens=("the parents did not carry",),
            ),
        ),
    )
    english_path = tmp_path / "case_001" / "english_fulltext.md"
    english_path.write_text(
        "Title\nthe parents did not carry this variant site\nappended\n",
        encoding="utf-8",
    )
    report = verify_translation_fidelity(table, tmp_path)
    assert report.drifted_artifacts == ("case_001:case_001/english_fulltext.md",)
    assert report.retained_fact_count == 1


def test_frozen_translation_fidelity_facts_cover_both_ready_sources() -> None:
    """The committed fidelity table pins the eight Stage-0 facts of the ready sources."""
    repository_root = Path(__file__).resolve().parents[4]
    table = load_translation_fidelity_fact_table(
        repository_root / "benchmark/experiments/acmg_multilingual/translation_fidelity_facts.json"
    )
    assert tuple(entry.case_id for entry in table.entries) == ("rett_007", "rett_011")
    assert sum(len(entry.facts) for entry in table.entries) == 8
    assert table.translation_review_status == "model_reviewed"


def test_cli_verify_translation_fidelity_reads_reviewed_root() -> None:
    """The fidelity audit runs on frozen reviewed artifacts, not on a live translation."""
    args = _parse_args(
        (
            "verify-translation-fidelity",
            "--facts",
            "fidelity.json",
            "--reviewed-root",
            "reviewed",
            "--report",
            "report.json",
        )
    )
    assert args.facts == Path("fidelity.json")
    assert args.reviewed_root == Path("reviewed")
    assert args.report == Path("report.json")


def test_frozen_increment_denominator_covers_three_tracks() -> None:
    """The committed cross-disease ledger freezes Rett, fused_014, and Parkinson mines."""
    from benchmark.experiments.acmg_multilingual.increment_denominator import (
        load_increment_denominator,
        summarize_increment_denominator,
        verify_increment_denominator,
    )

    repository_root = Path(__file__).resolve().parents[4]
    denominator = load_increment_denominator(
        repository_root / "benchmark/experiments/acmg_multilingual/increment_denominator.json"
    )
    summary = summarize_increment_denominator(denominator)
    assert summary.total_slots == 35
    assert summary.on_disk == 31
    assert summary.needs_external_corpus == 1
    assert summary.needs_workbook_export == 3
    assert dict(summary.family_counts)["PM3"] == 1
    assert dict(summary.family_counts)["PS2_PM6"] >= 14
    assert tuple(track.track_id for track in denominator.tracks) == (
        "multilingual_pm6_pvs1",
        "english_pm3_ready",
        "parkinson_latent_pp1_ps3_ps4",
    )
    report = verify_increment_denominator(
        denominator,
        reviewed_root=repository_root / "benchmark/experiments/acmg_multilingual/reviewed",
        clinvar_fused_root=repository_root / "benchmark/data/ground_truth/clinvar_fused",
    )
    assert report.verified_on_disk_slots == report.on_disk_slots == 31


def test_increment_slot_requires_partner_allele_for_pm3() -> None:
    """PM3-ready slots must name the second allele; negative controls may omit it."""
    from pydantic import ValidationError

    from benchmark.experiments.acmg_multilingual.increment_denominator import IncrementSlot

    with pytest.raises(ValidationError, match="partner_allele"):
        IncrementSlot(
            slot_id="bad_pm3",
            case_id="fused_014",
            gene="DCLRE1C",
            disease="SCID",
            target_hgvs_c="c.241C>T",
            criterion_family="PM3",
            eligibility_tier="source_fact_eligible",
            materialization_status="needs_external_corpus",
            source_root_kind="clinvar_fused",
            native_language="en",
        )


def test_cli_check_increment_denominator_parses_roots() -> None:
    """The increment-denominator CLI keeps reviewed and ClinVar-fused roots separate."""
    args = _parse_args(
        (
            "check-increment-denominator",
            "--denominator",
            "denom.json",
            "--reviewed-root",
            "reviewed",
            "--clinvar-fused-root",
            "clinvar_fused",
            "--report",
            "report.json",
        )
    )
    assert args.denominator == Path("denom.json")
    assert args.reviewed_root == Path("reviewed")
    assert args.clinvar_fused_root == Path("clinvar_fused")
    assert args.report == Path("report.json")
