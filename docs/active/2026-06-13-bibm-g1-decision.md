# BIBM G1 Decision Memo

**Status:** in-progress
**Created:** 2026-06-13
**Completed:**
**PR:**

## Decision Needed

Milestone 1 diagnostics are sufficient to make a provisional G1 decision, but they are not sufficient to enter a Main Full Paper strengthening branch. The paper owner should choose one of three next steps:

1. Run a current full-system ClinGen N=30 benchmark despite runtime risk.
2. Pivot to Demo/Resource Track using the system, benchmark assets, and traceability workbench as the contribution.
3. Invest in a real direction C algorithm first: cross-track reconcile/ranking plus grounding ablation.

Recommended decision: **do not start Milestone 2.A or 2.B for Main Paper now.** Direction A has no positive signal, direction B has no evaluable artifacts, and direction C is promising only as a small feasibility signal until a real reconcile/ranking algorithm and full evaluation exist.

## Evidence Inventory

| Evidence | File / command | Result |
|---|---|---|
| Machine-readable G1 report | `benchmark/layer3/reports/g1_decision_20260613_034015.json` | `recommendation=owner_decision_required`, `main_paper_ready=false` |
| Full LLM baselines | `benchmark/layer3/reports/baseline_b0_20260613_013114.json` through `baseline_b4_20260613_031120.json` | ClinGen N=30 complete; best F1 range `0.8957`-`0.9286` |
| Reusable system coverage | `python -m benchmark.layer3.analysis.inventory_system_runs --vault ...` | Only `3/30` ClinGen entries are safely mappable in PostgreSQL |
| DB-derived system subset | `benchmark/layer3/reports/eval_db_inventory_20260613_033106.json` | `N=3/30`, P=`0.8`, R=`1.0`, F1=`0.8889` |
| Matched subset baselines | `python -m benchmark.layer3.analysis.diagnose_baselines --matched-only` | B0-B4 all F1=`0.9412` on the same 3 entries |
| Grounding diagnostic | `python -m benchmark.analysis.diagnose_grounding` | CVR=`1.0`, HCR=`0.0`, `span_evidence=9`, but only N=3 |
| Native-gain diagnostic | `python -m benchmark.analysis.diagnose_native_gain` | unavailable: no rett dual-track extraction artifacts discovered |

## G1 Table

| Direction | Signal | Key numbers | Data legality | Missing work |
|---|---|---:|---|---|
| A. Structured ACMG extraction | No-go | System subset F1=`0.8889` vs matched B0-B4 F1=`0.9412`; historical adjusted N=10 also loses to baselines | ClinGen GT is valid for field P/R/F1, but current system coverage is only 3/30 | Current full-system N=30; statistically significant win over B1/B4 |
| B. Native-language gain | Not evaluable | `files_discovered=0`, `files_analyzed=0` for current rett dual-track artifacts | rett is native multilingual, but no GT and no extraction artifacts | Run rett through dual-track extraction; create dual annotator GT or at least validated recall proxy |
| C. Grounded traceability | Weak feasibility signal | DB subset CVR=`1.0`, HCR=`0.0`, `span_evidence=9`; system still below baselines on F1 | Source-span validity is measurable on subset; semantic correctness remains separate | Full report with spans; reconcile/ranking algorithm; grounding ablation; ESR/span-boundary annotation |

Reproduce this table:

```bash
PYTHONPATH=.:backend uv run --project /data/yangzs/Projects/01_ACMG_Lingua/backend --no-sync python -m benchmark.layer3.analysis.g1_decision --vault /data/yangzs/Projects/01_ACMG_Lingua/backend/config/vault/development.yaml --write
```

## BIBM Position

Current evidence does **not** support the Main Paper claim "cross-lingual multi-stage extraction outperforms strong LLM baselines." The simple baselines are stronger on available matched samples.

The defensible novelty statement today is narrower:

> ACMG Lingua provides a bilingual, source-grounded ACMG evidence extraction workbench whose accepted evidence can be audited through programmatically verifiable source spans; current diagnostics show traceability feasibility, while full scientific superiority over strong LLM baselines remains unproven.

This is closer to **Demo/Resource Track** unless direction C is upgraded into a real algorithmic contribution.

## Owner Options

| Option | What it proves | Cost / risk | Recommended? |
|---|---|---|---|
| Full current N=30 system rerun | Whether A can recover with current code | High runtime risk; prior single-entry run took about 20.7 min and failures/timeouts occurred | Only if Main Paper is still the target |
| Demo/Resource pivot | End-to-end system, benchmark suite, traceability UI, reproducible diagnostics | Lower risk; still needs a polished narrative and demo evidence | Yes, if deadline is tight |
| Direction C implementation | Potential Main Paper novelty through source-grounded cross-track reconcile/ranking | Requires new algorithm, tests, ablation, and full evaluation | Yes, if schedule allows new research work |

## Claim Guardrails

- Do not write "100% accurate traceability." Use "citation-valid by construction" only for spans that are programmatically verified.
- Do not claim native-language benefit from ClinGen, because the non-English ClinGen data is machine translated.
- Do not use the DB-derived `N=3/30` subset as paper main-result evidence.
- Do not describe "fusion" or "cross-validation fusion" as implemented novelty until a real reconcile/ranking step exists.
