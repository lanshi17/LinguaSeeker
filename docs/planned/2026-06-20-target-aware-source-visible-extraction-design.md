# Target-Aware Source-Visible Extraction Design

**Status:** planned
**Created:** 2026-06-20
**Owner:** CrossEvidence benchmark team

## Goal

Improve fused-75 source-visible F1 by changing production Phase 2 extraction behavior, not by filtering benchmark scores after extraction.

## Starting Point

The previous fused-75 optimization round found:

| Variant | Split | Source-Visible F1 | Precision | Recall |
|---|---|---:|---:|---:|
| contextual-reconcile-baseline | dev | 0.3660 | 0.3182 | 0.4308 |
| adjudicated-field-filter | dev | 0.5138 | 0.6364 | 0.4308 |
| adjudicated-field-filter | test | 0.4340 | 0.5897 | 0.3433 |

The dev gain came from removing unsupported field false positives in scoring. It did not improve extraction recall. The next round must target candidate generation and field eligibility inside the live extractor.

## Recommended Direction

Implement a production-side target-aware extraction variant with two controls:

1. **Field eligibility before LLM calls**: choose which catalog fields are worth asking for before `CatalogExtractionStage` builds prompts. This turns the benchmark-side field filter into a real extraction behavior and should reduce unsupported predictions, token use, and runtime.
2. **Recall-first target block expansion**: keep current target-gene/disease scoring, but include neighboring blocks around high-scoring target blocks so evidence immediately before or after the target mention is not dropped.

The design intentionally avoids a new pipeline topology. It stays inside the existing Phase 2 vertical slice:

- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/catalog_extraction.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/block_selection.py`
- `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py`
- existing contextual reconcile and fused75 benchmark runner

## Field Eligibility Policy

When no `ExtractionTarget` is present, behavior remains unchanged.

When a target is present, the policy builds a conservative allowed field set:

- Always include core identity fields: `A.gene_symbol`, `A.gene_disease_relationship`, `B.disease_diagnosis`.
- Include target variant fields when `ExtractionTarget.variant_hgvs_p` is present or target/blocks contain variant cues.
- Include case/phenotype fields when the evidence map or selected blocks contain case, phenotype, proband, patient, or diagnosis cues.
- Include inheritance fields when disease/gene context contains inheritance or zygosity cues.
- Include functional/experimental fields only when selected blocks contain assay, functional, cell, animal, model, rescue, expression, or biochemical cues.
- Include population/frequency fields only when selected blocks contain cohort, control, gnomAD, ExAC, allele frequency, ancestry, or population cues.
- Keep `curation` group excluded, as today.

This policy must be deterministic and typed. It must not return bare `dict`.

## Prompt Contract

The catalog prompt should tell the LLM that the provided catalog is already scoped:

- Extract only the listed eligible fields.
- Do not add fields outside the eligible catalog.
- Use `not_found` for eligible-but-absent fields.
- Preserve existing target, relationship, disease-boundary, and verbatim-source rules.

## Benchmark Strategy

Use the existing frozen fused-75 split discipline:

- Tune only on adjudicated dev.
- Run held-out test only with `--checkpoint`.
- Do not change adjudication labels.
- Do not promote a production change unless test improves over the current checkpoint.

Primary success:

```text
held-out test source-visible F1 > 0.4340
```

Secondary success:

```text
test recall >= 0.45
dev source-visible F1 > 0.5138, or test F1 improves enough to justify lower dev filter-only score
runtime/token count does not increase versus contextual-reconcile full-artifact dev run
```

## Risks

- Over-tight eligibility can lower recall. Mitigation: default to including a field family when cues are weak but target evidence is present.
- Neighbor expansion can increase runtime. Mitigation: cap selected blocks and measure chunk/task count.
- Prompt-only changes may not affect deterministic artifact replay. Mitigation: regenerate Phase 2 artifacts for dev before scoring the new production variant.

## Decision Gate

Promote the change only if:

1. focused unit tests prove prompt/catalog/block behavior,
2. dev artifacts generated with the new behavior improve or explain their error tradeoff,
3. one frozen test checkpoint beats `0.4340`,
4. final results document records F1, precision, recall, runtime, and token/call counts.
