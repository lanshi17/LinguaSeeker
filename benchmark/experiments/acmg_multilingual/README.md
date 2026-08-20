# ACMG Multilingual Code-Recovery Experiment

> A gated, content-controlled three-arm benchmark for source-grounded ACMG criterion-event recovery from non-English full text and a human-reviewed English full-text translation.

## Quick Start

All Python commands use the backend's `uv` environment. The supplied pilot intentionally reports zero ready records until reviewed English full-text translations are available.

```bash
cd backend

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli verify-sources \
  --manifest ../benchmark/experiments/acmg_multilingual/pilot_candidates.json \
  --source-root <annotation-root> --source-revision <external-corpus-revision> \
  --report <source-verification-report.json>

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-manifest \
  --manifest ../benchmark/experiments/acmg_multilingual/pilot_candidates.json
```

Cross-disease increment denominator (Rett multilingual + English `fused_014` PM3 + Parkinson latent mines):

```bash
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-increment-denominator \
  --denominator ../benchmark/experiments/acmg_multilingual/increment_denominator.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed \
  --clinvar-fused-root ../benchmark/data/ground_truth/clinvar_fused \
  --report <increment-denominator-report.json>
```

Stage-0 MECP2 direct inference (facts → codes → Rett VCEP combining; not blinded Stage-1 formal codes):

```bash
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-direct-inference \
  --cases ../benchmark/experiments/acmg_multilingual/direct_inference_cases.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed
```

Catalog-field shadow audit plus the frozen allele registry (source quotes, parentage-confirmation absence, hard non-identities):

```bash
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-field-bridge \
  --cases ../benchmark/experiments/acmg_multilingual/direct_inference_cases.json \
  --alleles ../benchmark/experiments/acmg_multilingual/canonical_alleles.json \
  --facts ../benchmark/experiments/acmg_multilingual/field_bridge_facts.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed
```

Catalog field-item increment (English abstract / English-visible captions vs native full text; not ACMG codes):

```bash
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-evidence-item-coverage \
  --facts ../benchmark/experiments/acmg_multilingual/evidence_item_coverage_facts.json \
  --reviewed-root ../benchmark/experiments/acmg_multilingual/reviewed
```

Extra Stage-0 ACMG criterion codes versus English-visible facts (class flip is a subset; product codes stay empty):

```bash
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli check-allele-class-increment
```

`verify-sources` is read-only: it checks the content-addressed native documents for every entry, including pending candidates, but never promotes an entry or contacts a model.

For a fully `ready` manifest, run the frozen workflow in this order:

```bash
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli materialize \
  --manifest <ready-manifest.json> --source-root <reviewed-source-root> \
  --output-root <input-root> --report <materialization-report.json>

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.run \
  --manifest <ready-manifest.json> --input-root <input-root> \
  --output-root <arm-output-root> --report <arm-run-report.json>

PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli create-templates \
  --manifest <ready-manifest.json> --arm-output-root <arm-output-root> \
  --reviewer-output-root <reviewer-packet-root> \
  --coordinator-output-root <coordinator-only-root>
```

After independent human completion of `gold_adjudication.json` and all three `review_packet.json` files, the coordinator scores the study with the sealed map:

```bash
PYTHONPATH=.. uv run --all-groups -- python -m benchmark.experiments.acmg_multilingual.cli score \
  --manifest <ready-manifest.json> --gold <coordinator-only-root/gold_adjudication.json> \
  --reviewer-packet <reviewer-packet-root/packet-.../review_packet.json> \
  --reviewer-packet <reviewer-packet-root/packet-.../review_packet.json> \
  --reviewer-packet <reviewer-packet-root/packet-.../review_packet.json> \
  --coordinator-blinding-map <coordinator-only-root/blinding_map.json> \
  --report <code-recovery-report.json>
```

## Architecture

```text
reviewed native full text + reviewed English full text + alignment
                              |
                              v
                  materialize.py: frozen input bundle
                    original.json / translated.json
                              |
                              v
run.py: english_pivot | native_only | dual_track product runs
                              |
                              v
adjudication_templates.py: neutral reviewer packets
  packet-<random>/review_packet.json + evidence/<case>.json
                              |                         \
                              |                          \-- coordinator-only
                              v                              gold_adjudication.json
                  human formal-code decisions                blinding_map.json
                              |                                      |
                              +------------- scoring.py ------------+
                                            unblind
                                              |
                                              v
                             exact-code paired precision/recall/F1
```

The three experimental arms are fixed:

| Arm | Input | Purpose |
|---|---|---|
| `english_pivot` | Same source's human-reviewed English full text | Content-equivalent English baseline |
| `native_only` | Native non-English full text | Native-language reading effect |
| `dual_track` | The same native and reviewed English texts | Dual-track recovery effect |

The module never treats extraction fields or `assigned_acmg_codes` as a final ACMG/AMP conclusion. Formal decisions are human-reviewed, source-anchored criterion events. `direct_inference.py` is a separate Stage-0 rule engine over frozen MECP2 facts: it can grant `PM6`/`PVS1`/`PP4`/`PM1` and a combining class, but it does not fill product `assigned_acmg_codes` and does not change the blinded Stage-1 code count (still 0).

## Public API

### Contracts

| Type | Role |
|---|---|
| `ExperimentManifest` / `ExperimentEntry` | Frozen three-arm denominator, source-family deduplication, translation-readiness gate |
| `ClinicalAssertion` | One pre-selected gene–disease–variant assertion per ready source family |
| `GoldAdjudicationSet` / `GoldCriterionEvent` | Independent clinical gold events |
| `ArmCriterionDecision` / `ArmDecisionSet` | Formal reviewed decisions after coordinator-side unblinding |
| `BlindedArmDecisionPacket` | Reviewer-visible packet with an opaque random ID, evidence artifacts, and blank/completed decisions |
| `BlindingMap` / `BlindingMapEntry` | Coordinator-only packet-to-arm association plus evidence-manifest hash |
| `SourceSpan` | Citation anchor with descriptive `language` and authoritative `artifact_track` (`original` or `translated`) |
| `NativeSourceVerificationReport` | Receipt that native source files still match the frozen candidate manifest before translation review completes |

Qualified PS2 requires `parentage_status="confirmed"`. A qualified PM6 decision must state parentage status explicitly. Completed gold sets and reviewer packets reject `not_assessed` or unattributed decisions.

### Workflow Functions

| Function | Signature | Description |
|---|---|---|
| Readiness | `assess_manifest_readiness(manifest)` | Counts ready/excluded records and lists blockers. |
| Verify sources | `verify_native_source_artifacts(manifest, source_root, source_revision)` | Read-only verification of every native source hash, including pending candidates. |
| Materialize | `materialize_reviewed_inputs(manifest, source_root, output_root)` | Verifies source/alignment hashes and writes immutable dual-input bundles. |
| Run | `await run_ready_arms(manifest, input_root, output_root, service, document_builder)` | Reuses each frozen bundle for all three product track modes. |
| Pack | `create_adjudication_templates(manifest, *, arm_output_root, reviewer_output_root, coordinator_output_root)` | Copies neutral model outputs into opaque packets and writes the gold template and sealed map separately. |
| Unblind | `unblind_decision_packets(manifest, blinding_map, reviewer_packets)` | Validates three completed packets and converts them to `ArmDecisionSet` objects. |
| Score | `evaluate_code_recovery(manifest, gold, arm_decision_sets)` | Calculates exact criterion-and-strength recovery and paired contrasts. |
| Direct inference | `infer_event` / `verify_direct_inference` | Stage-0 MECP2 rule engine: grant PM6/PVS1/PP4/PM1, combine, block conflicts. Not Stage-1 formal codes. |
| Field bridge | `verify_field_bridge` / `required_field_ids` | Map granted codes to catalog `field_id`s and verify line-anchored quotes plus parentage absence. Not a live extractor re-run. |
| Evidence items | `verify_evidence_item_coverage` | Stage-0c: which catalog `field_id`s are visible in the English abstract, English figure captions, and native full text of one PDF. |
| Allele class increment | `score_allele_class_increment` | Extra Stage-0 granted codes (PM6/PVS1/PP4/PM1) from native facts versus English-visible facts; combining-class flip is a stronger subset. Not a formal Stage-1 code count. |

JSON loaders and report writers live in `scoring.py` and `materialize.py`; use the CLI for ordinary workflows so packet files are hash-verified before scoring.

## Input and Output Guarantees

`verify-sources` verifies candidate native sources without changing readiness; use it to audit an ignored/local corpus before any translation work. Its receipt records the manifest fingerprint, source root, optional external-corpus revision, and verified relative paths/hashes. A source revision is useful context, but the manifest SHA-256 values remain the content-integrity authority when source files are intentionally untracked.

`materialize.py` requires every non-excluded manifest entry to be `ready`, verifies all source and alignment SHA-256 values, validates alignment offsets/text against both frozen documents, and refuses to overwrite an existing case bundle. `run.py` revalidates that bundle before each arm.

`create_adjudication_templates()` requires a completed result for every ready case and arm. It rejects overlapping or nested arm-output, reviewer-output, and coordinator-output roots. Reviewer packet names use `packet-<32 lowercase hex>`; filenames, packet JSON, and copied output payloads cannot include the three experimental-arm labels. Each packet lists content-addressed evidence files, and the coordinator map stores an independent fingerprint of that list.

The reviewer root must be the only tree sent to arm-decision reviewers. The coordinator root contains the map and must not be distributed with it.

## Blinding Boundary

This is **allocation-label masking**, not content-blind adjudication. A reviewer needs source-grounding information, and language, original/translated track evidence, or a single-versus-dual result can make the allocation inferable. The design prevents accidental arm-label disclosure and protects the gold process by keeping gold reviewers away from arm outputs; it must not be described as fully language-blinded review.

The scoring gate uses `SourceSpan.artifact_track`, rather than quote language, to establish whether a citation was visible to an arm. This matters because a native-language article can legitimately contain English figure captions or abstracts inside its `original` artifact.

## Usage Patterns

### Add a ready source family

1. Store native full text, reviewed English full text, and a non-empty paragraph/table alignment JSON below a source root.
2. Set their SHA-256 values, reviewer IDs (two for `human_reviewed`, one model identifier for `model_reviewed`), review date, one `index_assertion`, and predeclared criterion families in the manifest.
3. Change the entry status to `ready`, then rerun `check-manifest` before materialization.

Do not use an author English abstract or an on-the-fly machine translation as `english_fulltext`. A `model_reviewed` translation is model-produced and model-reviewed (with mandatory provenance `notes`), not human-reviewed; downstream claims must state this and never label it as human review.

### Complete a reviewer packet

For every predeclared event, set an assessed outcome and `reviewer_id`. A qualified decision also needs the exact criterion, strength, eligibility, prerequisite facts, source spans, and any PS2/PM6 parentage prerequisites. Cite `artifact_track="original"` for the native frozen input and `artifact_track="translated"` for the reviewed English input.

### Investigate a scoring refusal

The scorer deliberately stops on a mismatched study/hash, incomplete packet, duplicate/missing packet, evidence-hash drift, unknown event, omitted predeclared event, wrong criterion family, or citation of an invisible artifact. Correct the audited input rather than editing the report.

## Extension Guide

- Add a new criterion family by extending `CriterionFamily`, `FormalCriterion`, and `_CRITERION_FAMILY_BY_CODE`, then add prerequisite validators and scoring tests together.
- Add a new experimental arm only by changing the fixed `ACMG_MULTILINGUAL_ARMS` contract, runner track map, packet map validator, scoring comparisons, protocol, and tests. The current study intentionally fixes exactly three arms.
- Keep new external source artifacts under a caller-provided root, use content hashes, and reject traversal/overwrite paths.
- Keep clinical interpretation rules in contracts/scoring rather than embedding them in the product workflow. The runner only selects frozen documents and extraction modes.

## Performance Notes

Materialization verifies complete source content and alignment before writing anything, so its work is proportional to document size. The runner currently processes ready entries and arms sequentially to preserve a clear receipt and avoid changing model budget/concurrency as an experimental variable. Packet creation copies one JSON result per ready case and arm; it is I/O-bound and intentionally validates every result before creating any reviewer-visible tree.

## Dependencies

| Dependency | Version source | Purpose |
|---|---|---|
| Python | `>=3.12` | Runtime |
| Pydantic | `>=2.7.0` | Immutable contracts and JSON validation |
| `pytest` | backend dev dependency | Unit and async test execution |
| `ruff` | backend dev dependency | Linting |
| Evidence extraction service | `backend/src/core/evidence_extraction/` | Production dual-track execution facade |
| Translation alignment contract | `backend/src/core/cross_lingual_translation/` | Alignment JSON validation |

## Testing

```bash
cd backend
uv run ruff check ../benchmark/experiments/acmg_multilingual tests/benchmark/experiments/test_acmg_multilingual.py tests/benchmark/experiments/test_acmg_direct_inference.py tests/benchmark/experiments/test_acmg_field_bridge.py tests/benchmark/experiments/test_acmg_evidence_item_coverage.py tests/benchmark/experiments/test_acmg_allele_class_increment.py
PYTHONPATH=.. uv run --all-groups -- python -m pytest \
  tests/benchmark/experiments/test_acmg_multilingual.py \
  tests/benchmark/experiments/test_acmg_direct_inference.py \
  tests/benchmark/experiments/test_acmg_field_bridge.py \
  tests/benchmark/experiments/test_acmg_evidence_item_coverage.py \
  tests/benchmark/experiments/test_acmg_allele_class_increment.py -q
```

To audit an ignored local corpus in CI-like form, set `ACMG_MULTILINGUAL_ANNOTATION_ROOT` (and optionally `ACMG_MULTILINGUAL_CORPUS_REVISION`) before running the targeted source-verification test.

The tests cover readiness, source deduplication, pending-source verification, reviewed-translation and alignment gates, hash drift, three-track mode selection, output-label leakage, separate coordinator/reviewer roots, opaque packet generation, sealed-map unblinding, artifact visibility, exact code/strength scoring, the frozen cross-disease increment denominator, and the MECP2 direct-inference protocol.
