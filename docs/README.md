# Documentation Index

Project documentation organized by lifecycle status.

```text
docs/
├── active/           # In-progress plans & living reference docs
├── planned/          # Planned work that has not started
├── codereview/       # Active code reviews (.gitkeep)
├── diagrams/         # Mermaid flowcharts (phase1-phase4)
├── archive/
│   ├── plans/        # Completed or superseded plans
│   └── codereview/   # Completed code reviews
└── templates/        # plan.md, codereview.md templates
```

## Classification Rules

- `active/` -- In-progress implementation plans and living reference documents.
- `planned/` -- Planned work that has not started (`YYYY-MM-DD-<topic>.md`).
- `codereview/` -- Active code review reports.
- `diagrams/` -- Mermaid flowcharts (`.mmd`) for the four pipeline phases.
- `archive/plans/` -- Completed or superseded plans.
- `archive/codereview/` -- Completed code reviews.
- `templates/` -- Reusable documentation templates.

### When to Move Documents

| Trigger | From | To |
|---------|------|----|
| Work starts on a plan | `planned/` | `active/` |
| Plan completed / merged | `active/` | `archive/plans/` |
| Code review resolved | `codereview/` | `archive/codereview/` |

## Naming Convention

Use `YYYY-MM-DD-<kebab-case-description>.md` for new documents.

## Active Plans & References

| Date | Title | Status |
|------|-------|--------|
| 2026-06-15 | [BIBM Main Paper Manuscript Draft](active/2026-06-15-bibm-main-paper-manuscript-draft.md) | in-progress |
| 2026-06-15 | [BIBM Main Paper Claim Matrix](active/2026-06-15-bibm-main-paper-claim-matrix.md) | in-progress |
| 2026-06-15 | [BIBM Main Paper Outline](active/2026-06-15-bibm-main-paper-outline.md) | in-progress |
| 2026-06-15 | [BIBM Main Paper Limitations](active/2026-06-15-bibm-main-paper-limitations.md) | in-progress |
| 2026-06-15 | [BIBM Main Paper Pipeline Optimization & Benchmark Plan](active/2026-06-15-bibm-main-paper-pipeline-optimization-and-benchmark-plan.md) | in-progress |
| 2026-06-15 | [Main Paper Tables Developer Guide](active/2026-06-15-main-paper-tables-guide.md) | in-progress |
| 2026-06-15 | [Learned Arbitrator Gate A Report](active/2026-06-15-learned-arbitrator-gate-a-report.md) | negative ablation |
| 2026-06-15 | [BIBM Main Paper LaTeX](active/2026-06-15-bibm-main-paper-tex/) | in-progress |
| 2026-06-14 | [BIBM Main Paper G3 Semantic Boundary Repair Implementation Plan](active/2026-06-14-bibm-main-paper-g3-semantic-boundary-repair-plan.md) | in-progress |
| 2026-06-14 | [Traceability Metrics Developer Guide](active/2026-06-14-traceability-metrics-guide.md) | in-progress |
| 2026-06-14 | [BIBM Main Paper Detailed Execution Plan](active/2026-06-14-bibm-main-paper-detailed-execution-plan.md) | in-progress |
| 2026-06-14 | [BIBM Main Paper Roadmap](active/2026-06-14-bibm-main-paper-roadmap.md) | in-progress |
| 2026-06-14 | [BIBM Main Paper Effect Improvement Plan](active/2026-06-14-bibm-main-paper-effect-improvement-plan.md) | in-progress |
| 2026-06-14 | [BIBM Main Paper Rescue](active/2026-06-14-bibm-main-paper-rescue.md) | in-progress |
| 2026-06-13 | [BIBM G1 Decision Memo](active/2026-06-13-bibm-g1-decision.md) | in-progress |
| 2026-06-12 | [BIBM Novelty Diagnosis](active/2026-06-12-bibm-novelty.md) | in-progress |
| 2026-05-09 | [PRD](active/PRD.md) | reference |
| 2026-05-09 | [Application Flow](active/APP_FLOW.md) | reference |
| 2026-05-09 | [Technology Stack](active/TECH_STACK.md) | reference |
| 2026-05-09 | [Frontend Guidelines](active/FRONTEND_GUIDELINES.md) | reference |
| 2026-05-09 | [Backend Structure](active/BACKEND_STRUCTURE.md) | reference |
| 2026-05-09 | [Implementation Plan](active/IMPLEMENTATION_PLAN.md) | reference |
| 2026-05-13 | [Phase Workflow Overview](active/phase_workflow_overview.md) | reference |

## Planned Work

| Date | Title | Status |
|------|-------|--------|
| 2026-06-16 | [Benchmark B Completion Plan](planned/2026-06-16-benchmark-b-completion-plan.md) | planned |
| 2026-06-14 | [BIBM Main Paper Next Gate Plan](planned/2026-06-14-bibm-main-paper-next-gate-plan.md) | planned |
| 2026-06-14 | [BIBM Main Paper Detailed Plan](planned/2026-06-14-bibm-main-paper-detailed-plan.md) | planned |
| 2026-06-14 | [BIBM Main Paper Rescue Plan](planned/2026-06-14-bibm-main-paper-rescue.md) | planned |
| 2026-06-14 | [BIBM Main Paper Effect Plan](planned/2026-06-14-bibm-main-paper-effect-plan.md) | planned |

## Diagrams

| File | Content |
|------|---------|
| [phase1.mmd](diagrams/phase1.mmd) | Phase 1: literature acquisition, parsing |
| [phase2.mmd](diagrams/phase2.mmd) | Phase 2: translation, dual evidence extraction |
| [phase3.mmd](diagrams/phase3.mmd) | Phase 3: entity standardization, knowledge alignment |
| [phase4.mmd](diagrams/phase4.mmd) | Phase 4: evidence visualization, expert feedback |

## Archive Index

| Date | Title | Status |
|------|-------|--------|
| 2026-06-15 | [BIBM Benchmark A/B Readiness Plan](archive/plans/2026-06-15-bibm-benchmark-a-b-readiness-plan.md) | completed |
| 2026-06-15 | [BIBM Benchmark Expansion Phase C Implementation Plan](archive/plans/2026-06-15-bibm-benchmark-expansion-phase-c-plan.md) | completed |

The `archive/plans/` directory contains 76 completed plans. The `archive/codereview/` directory contains 24 resolved code reviews. See individual directories for full listings.

## Module README Index

Every `backend/` module has its own `README.md` developer guide. Key modules:

- **[backend/app/](../backend/app/README.md)** -- FastAPI application entry point
- **[backend/src/agents/](../backend/src/agents/README.md)** -- Pipeline orchestrator (LangGraph)
- **[backend/src/api/](../backend/src/api/README.md)** -- HTTP boundary, dependency injection
- **[backend/src/core/](../backend/src/core/README.md)** -- Vertical feature slices
- **[backend/src/dao/](../backend/src/dao/README.md)** -- Persistence layer
- **[backend/libs/](../backend/libs/README.md)** -- Rust native extensions (rust-io, net-io, files-io)
- **[services/model-server/](../services/model-server/README.md)** -- Embedding/Rerank/LLM server
