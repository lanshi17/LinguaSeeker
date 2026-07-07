# Pipeline Path Exploration

**Status:** in-progress
**Created:** 2026-07-04
**Completed:** --
**PR:** --

## Goal

Explore a better path than the current evidence pipeline, using the current codebase and benchmark artifacts as evidence. This document is a design memo, not an implementation record.

## Current Pipeline Boundary

The backend automatic pipeline is a 3-node LangGraph:

1. Phase 1: acquire and parse source documents.
2. Phase 2: translate, run dual-track evidence extraction, review, target guard, normalization, and reconciliation.
3. Phase 3: standardize entities and persist canonical evidence.

Phase 4 is not currently an automatic graph node. It is implemented through expert-in-loop APIs and UI surfaces for chat, evidence review, source linking, and audit.

Evidence from code:

- `backend/src/agents/orchestrator.py` builds only `phase_1`, `phase_2`, and `phase_3`.
- `backend/src/agents/phase_2_adapter.py` passes extraction profile, ablation flags, target guard, and `review_reject_policy` into `EvidenceExtractionService.run_dual()`.
- `backend/src/agents/phase_3_adapter.py` loads Phase 2 output, runs `EntityStandardizationService.run_dual_result()`, and skips only when `skip_phase_3_reason` is already set.
- Current production defaults already include tri-state review, target guarding, HGVS protein alias normalization, and `unknown_not_reported` completion for in-scope `C.de_novo_status`.

## Evidence From Recent Experiments

### What Did Not Work Reliably

The older Dataset D optimization plan showed that broader extraction without validation increases false positives. The documented failure modes were:

- high-FP fields such as `B.mode_of_inheritance_reported` and `B.age_of_onset`;
- clinical-context supplement passes converting missing fields into wrong values;
- profile restriction that became too aggressive and produced all-missing entries;
- Phase 3 gene-variant coexistence gate dropping identity fields until it was relaxed.

Relevant document: Dataset D pipeline optimization design (archived).

### What Did Work Better

The 53-document Rett/MECP2 benchmark supports a governance-first path:

- Raw GPT-5 full-text prompt-only: F1 `0.189`, TP/FP/FN `5/41/2`.
- Lingua Seeker governed DB-ready pipeline: F1 `0.833`, TP/FP/FN `5/0/2`.
- Main results packet reports the governance-assisted candidate-gated row at F1 `0.8571`, TP/FP/FN `6/1/1`.
- Error decomposition shows the DB-ready candidate gate reduced outside-governed-domain predictions from `58` to `0`.
- Exploratory GPT-5 full-text reached F1 `0.8333`, which shows context sufficiency, but it is not the scalable production path because it lacks the governed DB/export boundary.

Relevant artifacts:

- `benchmark/paper/reports/final_benchmark_registry/rett_benchmark_registry_20260704_172954.md`

## Candidate Paths

| Path | Summary | Upside | Main Risk | Decision |
| --- | --- | --- | --- | --- |
| Full-document prompt-only | Send the whole document to a frontier model and score output directly. | Strong context availability; simple to run. | High false positives and weak provenance/export control. | Use only as baseline or context-sufficiency ablation. |
| Field-budgeted extraction | Restrict fields and add field-specific prompt rules. | Lower attention dilution; useful for benchmark-specific profiles. | Can become too narrow and miss identity/variant fields. | Keep as optional profile, not the main path. |
| Governance-first hybrid | Generate high-recall candidates, then constrain them with target guard, source support, entity normalization, DB-ready candidate gates, and expert audit. | Best observed precision/claim safety; aligns with clinical evidence workflow. | Must avoid gold leakage and label the gate as governance-assisted. | Recommended. |
| Full graph rewrite | Replace the 3-phase graph with a larger multi-agent topology. | Could expose more observability points. | High implementation cost without evidence that topology is the bottleneck. | Defer. |

## Recommended Better Path

The better path is a governance-first hybrid pipeline:

1. Keep the current 3-phase graph as the top-level orchestrator.
2. Strengthen Phase 2 as a high-recall candidate generator, not a final authority.
3. Insert a typed DB-ready candidate gate before canonical export. This gate should keep only candidates whose source document, target entity, source span, and normalized entity bindings are internally consistent.
4. Treat `unknown_not_reported` completion and cDNA/protein alias repair as explicit, auditable post-processing components.
5. Keep expert review and delta audit as the final clinical readiness boundary.

This path improves over the current pipeline by moving the reliability claim from "LLM extracted the answer" to "the system generated, constrained, normalized, and audited a source-grounded candidate."

## Implementation Direction

Recommended next implementation slice:

1. Generalize the Rett DB-ready candidate gate into a backend feature slice, without Rett-specific gold labels.
2. Define typed contracts for:
   - candidate key: source document, gene, variant, disease, patient/cohort where applicable;
   - source support: span, page/block, track, grounding status;
   - export readiness: normalized entity IDs, variant IDs, review status, audit status.
3. Wire the gate into Phase 3 canonical evidence persistence rather than adding a new graph node first.
4. Add a report that counts candidates before/after the gate and breaks rejection reasons into domain, source, target, normalization, and review buckets.
5. Validate on the existing N=50 comparison design before broad claims.

## Acceptance Gates

Do not call the new path better unless it passes these checks:

| Gate | Required Evidence |
| --- | --- |
| Precision control | False positives drop versus ungated extraction on the same entries. |
| Recall preservation | Recall does not collapse after gating; missing cases are explained by rejection categories. |
| Source grounding | Every DB-ready row has a recoverable source span or explicit expert override. |
| Entity consistency | Variant/gene/disease bindings use normalized IDs where available. |
| Claim safety | Reports separate raw model baselines, governance-assisted gates, and post-adjudication export quality. |
| Coverage | Baselines used for main comparisons cover the same manifest; partial baselines are labeled partial. |

## Claim Boundary

Current evidence supports a controlled Rett/MECP2 pilot claim and a design direction. It does not prove universal superiority across all ACMG literature tasks. The main caution is that DB-ready gating is governance-assisted because it uses governed candidate keys; it must not be presented as a pure model-only benchmark.

## Next Steps

1. Convert this design into an implementation plan for a generic DB-ready candidate gate.
2. Add focused tests around target/entity/source consistency.
3. Run the planned N=50 comparison only after the gate produces per-entry audit reports.
4. Archive or update older pipeline optimization docs after the generic implementation starts.
