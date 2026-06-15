# BIBM Main Paper Pipeline Optimization & Benchmark Plan

**Status:** planned
**Created:** 2026-06-15
**Scope:** BIBM Main Paper (not demo/resource track)
**Owner:** CrossEvidence backend / benchmark team

> **For Claude / executing agents:** This plan is paired with a three-round codebase audit (2026-06-15). The "Current State" sections under each part record the verified baseline so the execution agent does not re-derive it. Resolve blockers top-down: the language-metadata propagation issue gates both Benchmark A and Benchmark B.

## Summary

论文主线锁定为：**CrossEvidence 是跨语言、可溯源的 variant-interpretation evidence augmentation pipeline**。系统不做 ACMG/ClinGen 最终评级，只做证据项提取、原文-译文对齐、可溯源搬运、以及非英文证据增补。

核心创新点分三层：

- **Evidence Extraction:** 准确抽取 gene / disease / variant / phenotype / functional / segregation / frequency 等证据项。
- **Cross-Lingual Evidence Transport:** 对齐原文轨与译文轨，检测 drift/conflict，并要求 accepted evidence 必须绑定可恢复 source span。
- **Evidence Augmentation:** 相比 English-only workflow，纳入中文、日文等非英文文献后，提高 variant interpretation 所需证据覆盖度。

不主张"自动提升临床评级准确率"；只主张"提升 evidence coverage、traceability、curator utility"。

## Current State (Audited 2026-06-15, 3 rounds)

> These facts are machine-verified (commands actually run, tests actually executed), not inferred from file listings.

### ✅ Already delivered

- **Pipeline contracts.** `EvidenceItem` carries the full multilingual metadata set
  (`article_language`, `source_database`, `is_english`, `requires_translation`,
  `target_gene`, `target_disease`, `target_variant`, `evidence_source_language`) at
  `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py:156-188`,
  with a `normalize_language_metadata` validator that auto-fills
  `is_english` / `requires_translation` / `evidence_source_language`.
- **Alignment contract.** `EvidenceAlignmentRecord` + `EvidenceAlignmentLabel`
  (`aligned|partial|drifted|conflict|missing`) + `EvidenceSupportLabel`
  (`supports|contradicts|insufficient`) exist at `contracts.py:137-215`, fields match the
  plan's JSON exactly.
- **Alignment layer logic.** `reconcile/alignment.py` (183 lines) implements
  `build_alignment_records`, `is_alignment_acceptable` (traceability gate),
  relationship-drift / conflict / mismatch decisions.
- **Multilingual corpus.** `benchmark/pipeline/input/ground_truth/` has
  **7 languages × 30 entries = 210 PDFs** (de/en/es/fr/ja/ko/zh).
- **Benchmark A core results.** `main_paper_tables_20260615_194001.md`:
  - Table 2: `context_verifier_reconcile` P=0.9205 R=0.9759 F1=0.9474, sign_test_p=0.0039
    (significant vs all B0–B4 baselines).
  - Table 3 ablation: dual_union 0.8743 → grounded_hard_rule 0.882 →
    source_grounded_reconcile 0.8889 → context_verifier 0.9474 (monotone).
  - Table 4 traceability: CVR=1.0, HCR=0.0, ESR=0.9205, TraceableF1=0.9474.
- **Benchmark B pilot selection.** `benchmark_b_pilot_selection.json`: N=10 cases selected,
  each with ~6 non-English sources.
- **Supporting analysis modules** exist: `alignment_metrics.py`,
  `alignment_annotation_protocol.py`, `benchmark_readiness.py`,
  `evidence_augmentation_metrics.py`, `select_benchmark_b_pilot.py`.
- **Tests pass.** 9 alignment/metrics/protocol tests green.

### ❌ Verified blockers (gate the acceptance criteria)

1. **Language metadata is NOT propagated into extraction artifacts (critical, gates both A and B).**
   `clingen_000/preprocessed/phase_2/extraction_result.json` evidence items have
   `article_language=None`, `is_english=None`, `evidence_source_language=None` across all
   three tracks. `_is_english()` returns `False` on missing fields, so **every item is
   mis-classified as non-English**. Consequence: `evidence_augmentation_metrics` runs but
   reports `NonEnglishYield=1.0` and `CoverageGain=0.0` (denominator 0) — **invalid numbers**.
2. **Alignment gold annotations: 0/30.** `benchmark_readiness_20260615_193750.json` confirms
   `annotated_count=0`, `missing_count=30`. No `alignment_annotations.json` exists.
   → Alignment Accuracy / Drift Detection F1 / Conflict Detection F1 **cannot be computed**;
   `alignment_metrics` returns `N=0`.
3. **Neither new-metric command has produced a report.** `reports/` has no `*alignment*` or
   `*augment*` files. Main-paper Table 4 currently carries traceability only.
4. **Drift detection is shallow.** `alignment.py` only implements relationship-cue drift +
   conflict-value lookup. Plan §3's **negation loss, numeric drift (allele count / frequency
   / family count), table-row/caption correspondence** are NOT implemented.
5. **Manuscript claim matrix** not present as a standalone artifact.
6. **Repo hygiene.** Working tree has uncommitted `backend/pyproject.toml`, `uv.lock`,
   `lesson.md`; untracked `.qoder/` and `reconcile/README.md`.

---

## Pipeline Optimization

### 1. Multilingual Literature Intake

扩展现有文献输入层，让每篇文献和每个 evidence item 都带语言与来源元数据：

- `article_language`
- `source_database`
- `is_english`
- `requires_translation`
- `target_gene`
- `target_disease`
- `target_variant` if available
- `evidence_source_language`

优先支持三类输入：

- English-only literature set
- Non-English literature set
- Mixed multilingual set

输出必须能区分：某条证据来自英文文献，还是来自中文/日文/其他非英文文献。

**Implementation note (from audit):** the contract fields and validator already exist. The
missing piece is **propagation**: the extraction flow must stamp `article_language` onto
every `EvidenceItem` it emits, sourced from the document's known language track. This is the
single highest-priority pipeline task because both Benchmark A alignment and Benchmark B
augmentation depend on it.

### 2. Original-First Extraction

非英文文献必须先做原文轨抽取，再做译文轨抽取。

每条原文轨 evidence item 至少包含：

- normalized field value
- original text span
- page/block/span metadata if available
- extraction confidence
- language
- evidence type

译文轨只作为理解和交叉验证，不允许替代原文 span 作为最终 citation。

### 3. Translation-With-Anchor

翻译阶段必须保留 block/span 映射。

新增或强化 translation validation：

- gene / variant / disease 是否丢失
- negation 是否丢失
- relationship cue 是否漂移，例如 causative / associated / susceptibility / refuted
- table row / caption 是否保持对应
- numeric evidence 是否改变，例如 allele count、frequency、family count

如果翻译存在漂移，后续 evidence item 只能标记为 `drifted` 或 `needs_review`，不能直接作为 accepted evidence。

**Implementation note (from audit):** current `alignment.py` only covers relationship-cue
drift and conflict-value lookup. Negation-loss and numeric-drift detectors must be added
before Drift Detection F1 can be a credible metric. Implement as pure functions under
`reconcile/alignment.py` to keep it deterministic and unit-testable.

### 4. Original-Translation Alignment Layer

新增核心结构：`EvidenceAlignmentRecord`。

建议字段：

```json
{
  "entry_id": "...",
  "field_id": "...",
  "original_value": "...",
  "translated_value": "...",
  "normalized_value": "...",
  "original_span_id": "...",
  "translated_span_id": "...",
  "alignment_label": "aligned|partial|drifted|conflict|missing",
  "support_label": "supports|contradicts|insufficient",
  "drift_reason": "...",
  "confidence": 0.0
}
```

决策规则：

- `aligned`: 原文与译文支持同一证据项。
- `partial`: 字段主体一致，但边界或限定词不同。
- `drifted`: 译文改变医学语义。
- `conflict`: 原文轨与译文轨给出互斥值。
- `missing`: 单轨有证据，另一轨无对应证据。

accepted evidence 必须满足：

- 原文 span 可恢复；
- span 支持字段值；
- alignment 不为 `drifted` 或 unresolved `conflict`；
- 若只有单轨支持，必须标记为 source-only accepted，而不是 cross-track confirmed。

**Implementation note (from audit):** contract, label enum, decision logic, and the
`is_alignment_acceptable` traceability gate are all in place. The gap is downstream: the
gate is not yet enforced in the reconcile path, and gold annotations (§Benchmark A data) are
absent.

### 5. Evidence Augmentation Matrix

新增 variant interpretation evidence matrix，但不输出最终评级。

每个 variant / gene-disease case 输出：

- English-only evidence count
- multilingual evidence count
- non-English added evidence count
- duplicated evidence count
- conflicting evidence count
- traceable added evidence count
- potential ACMG evidence type: PS3/BS3, PP1, PM2, BA1/BS1, phenotype/case evidence, functional evidence

`potential ACMG evidence type` 只表示证据类别，不表示自动满足 ACMG criterion。

**Implementation note (from audit):** `evidence_augmentation_metrics.py` computes the matrix
and all six derived metrics, and the CLI runs. But its output is **currently invalid**
(`NonEnglishYield=1.0`, `CoverageGain=0.0`) because extraction artifacts lack language
metadata. Fixing blocker #1 (language propagation) is the prerequisite; after that, re-run
`--write` to materialize the first real report.

---

## Benchmark Design

### Benchmark A: Cross-Lingual Evidence Transport

目标：证明系统能准确、可溯源地搬运跨语言证据，并检测翻译漂移和冲突。

数据：

- 使用当前 frozen N=30 ClinGen/ACMG-style set 作为 Core Set。
- 给每个 scorable field 补充人工标注：
  - original source span
  - translated source span if available
  - alignment label
  - support label
  - drift/conflict reason if applicable

评估字段：

- `A.gene_symbol`
- `B.disease_diagnosis`
- `A.gene_disease_relationship`
- 可扩展字段：variant, phenotype, functional assay, segregation, population frequency

Baselines：

- original-only
- translated-only
- translate-then-extract
- dual-union without reconciliation
- prompt-only citation LLM
- RAG + LLM
- single-agent CoT
- CrossEvidence full
- ablation: no alignment
- ablation: no traceability gate
- ablation: no drift detection

指标：

- Precision / Recall / F1
- CVR: accepted citation span 可恢复比例
- HCR: accepted citation 不可定位比例
- ESR: source span 语义支持字段值比例
- TraceableF1: 字段正确且 citation valid 才算 TP
- Alignment Accuracy
- Drift Detection F1
- Conflict Detection F1
- Source-only Accepted Rate
- Cross-track Confirmed Rate

主表建议：

- Table 1: dataset composition and alignment labels
- Table 2: extraction P/R/F1
- Table 3: CVR/HCR/ESR/TraceableF1
- Table 4: alignment and drift/conflict detection
- Table 5: ablation study

**Implementation note (from audit):** Tables 2, 3, 5 are already produced and significant.
Table 4 (alignment & drift/conflict) is **blocked on gold annotations (0/30)**. The
annotation work uses the schema already validated by `alignment_annotation_protocol.py`
(`AlignmentAnnotationFile` / `EvidenceAlignmentRecord`). Annotation effort is scoped to 3
scorable fields × 30 entries = 90 records.

### Benchmark B: Multilingual Evidence Augmentation for Variant Interpretation

目标：证明非英文文献能补充 English-only workflow 漏掉的 evidence base。

数据：

- 选择 20-50 个 variant / gene-disease cases。
- 每个 case 构造两套文献：
  - English-only literature set
  - multilingual literature set，包括中文、日文等非英文文献
- gold label 不是最终 pathogenicity classification，而是 evidence items 和 source spans。

实验分组：

- English-only pipeline
- English + translate-then-extract non-English pipeline
- CrossEvidence multilingual full pipeline

指标：

- Evidence Coverage Gain: 相比 English-only 多发现的 gold-supported evidence item 数量或比例。
- Non-English Evidence Yield: accepted evidence 中来自非英文文献的比例。
- Unique Evidence Gain: 非英文文献提供的非重复证据数量。
- Traceable Augmentation Rate: 新增非英文证据中 source-valid 的比例。
- Interpretation-Relevant Evidence Gain: 新增证据中可映射到 potential ACMG evidence type 的比例。
- Reviewer Burden: 新增证据中需要人工复核、冲突处理或 drift review 的比例。

主结论写法：

- 允许说：CrossEvidence improves evidence coverage available for variant interpretation.
- 不允许说：CrossEvidence improves clinical variant classification accuracy.

**Implementation note (from audit):** pilot case selection is done (N=10) and the 7-language
corpus exists. The metric module runs but produces invalid output until blocker #1 is fixed.
Start with the N=10 pilot, report real yield numbers, then decide on N=30 / N=50 expansion
per the Implementation Order.

---

## Implementation Order

1. **Repo hygiene first**
   - 当前有未提交文档变更和 `.qoder/` 未跟踪目录。
   - 执行前先检查 `git status`，只保留与本方案相关的文档或新建干净 worktree。

2. **Evaluation-first minimal path**
   - 先做 Benchmark A，不先做 learned arbitrator。
   - 补 `alignment_label` 与 `support_label` 标注 schema。
   - 在现有 `benchmark/layer3` 上新增 alignment/augmentation analysis 脚本。
   - 复用已有 traceability metrics、prompt model baselines、reconcile ablation reports。

3. **Pipeline improvement path**
   - 增强 source-grounded evidence item 的语言与 span metadata。
   - 新增 original-translation alignment records。
   - 在 reconcile 阶段加入 drift/conflict reject or review policy。
   - 输出 evidence augmentation matrix。

4. **Benchmark B path**
   - 先做 N=10 pilot case study。
   - 如果结果显示非英文证据 yield 明显，再扩到 N=30 或 N=50。
   - 最终论文可以把 B 作为 second experiment 或 case-study experiment。

**Sequencing fix (from audit):** the original order lists "Evaluation-first minimal path"
before "Pipeline improvement path", but the audit proves that Benchmark B augmentation and
Benchmark A alignment-table both depend on the pipeline propagating language metadata. The
effective execution order must interleave:

```
Step 0  →  Repo hygiene (commit / clean working tree)
Step 1  →  Pipeline: propagate article_language into EvidenceItem (blocker #1)
            Verify: extraction_result.json items carry non-null article_language per track
Step 2a →  Benchmark A: annotate 30 entries × 3 fields (alignment_annotations.json)
Step 2b →  Pipeline: add negation + numeric drift detectors (blocker #4)
Step 3  →  Run alignment_metrics --write and evidence_augmentation_metrics --write
            Verify: reports land in benchmark/layer3/reports/; numbers are plausible
Step 4  →  Merge Table 4 (alignment/drift/conflict) into main_paper_tables
Step 5  →  Benchmark B N=10 pilot; gate N=30/N=50 expansion on measured yield
Step 6  →  Manuscript claim matrix; finalize
```

## Test Plan

Backend unit tests：

- alignment label assignment
- original/translated span mapping
- drift detection rule cases
- conflict detection rule cases
- traceability gate rejects source-invalid evidence
- augmentation matrix counts English-only vs non-English evidence correctly

**New unit tests required by audit:**

- `_is_english` correctly classifies items with explicit language vs None
- extraction flow stamps `article_language` onto emitted `EvidenceItem` (regression for
  blocker #1)
- negation-loss drift detector (new)
- numeric-drift detector on allele count / frequency / family count (new)
- `evidence_augmentation_metrics` produces `english_only_evidence_count > 0` and a finite,
  in-range `evidence_coverage_gain` on a toy multilingual fixture (regression for the
  invalid `CoverageGain=0.0` case)

Benchmark tests：

- annotation schema validation
- metric calculation for CVR/HCR/TraceableF1
- metric calculation for Alignment Accuracy / Drift Detection F1 / Conflict Detection F1
- Evidence Coverage Gain and Non-English Evidence Yield on toy fixtures
- no leakage from `expected.json`, ClinGen classification, or evaluator matches into runtime extraction

End-to-end evaluation commands:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.traceability_metrics --strategy context_verifier_reconcile --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.prompt_model_baseline_tables --write
```

New expected commands after implementation:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.alignment_metrics --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.evidence_augmentation_metrics --write
```

**Verification gates (from audit):**

- `alignment_metrics --limit 2` must report `N>0` (currently `N=0` due to missing
  annotations).
- `evidence_augmentation_metrics --limit 2` must report a finite
  `evidence_coverage_gain` and `NonEnglishYield` in (0,1) (currently `CoverageGain=0.0`,
  `NonEnglishYield=1.0` — invalid, because all items lack language metadata).
- `benchmark_readiness` must show `annotated_count=30` before Benchmark A Table 4 is
  publishable.

Acceptance criteria:

- Benchmark A reports Extraction F1, CVR, HCR, ESR, TraceableF1, Alignment Accuracy, Drift Detection F1, Conflict Detection F1.
- CrossEvidence has competitive F1 and better traceability than prompt-only citation baselines.
- Full method outperforms no-alignment and no-traceability ablations on TraceableF1 or HCR.
- Benchmark B pilot shows measurable non-English evidence yield with source-valid spans.
- Manuscript claim matrix explicitly states the system does not perform autonomous ACMG classification.

## Assumptions

- Main paper target is BIBM Main Paper, not demo/resource track.
- Current N=30 frozen benchmark remains the first controlled evaluation.
- Non-English evidence augmentation is evaluated as evidence coverage, not clinical classification accuracy.
- `context_verifier_reconcile` remains the main method unless new experiments prove a better strategy.
- Prompt-only baselines use same-release-window model aliases and the existing integrated provider gateway.
- If time is limited, prioritize Benchmark A and a small Benchmark B pilot over N=60 expansion.

## Progress Log

- [2026-06-15] Plan authored; paired with a 3-round codebase audit recording the verified baseline. [planned]
