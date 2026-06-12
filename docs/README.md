# Documentation Index

Project documentation organized by lifecycle status.

```text
docs/
├── active/           # Current active documentation
├── plans/            # Skill-authored implementation plans pending execution
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
- `plans/` -- Skill-authored implementation plans pending execution.
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
| 2026-06-06 | [ClinGen-based Layer 3 Pipeline Evaluation](active/2026-06-06-clingen-layer3-evaluation.md) | in-progress |
| 2026-05-09 | [PRD](active/PRD.md) | active -- v2.0 tab-based UI |
| 2026-05-09 | [Application Flow](active/APP_FLOW.md) | active -- v2.0 tab navigation |
| 2026-05-09 | [Technology Stack](active/TECH_STACK.md) | active -- v2.0 SSE, Vercel AI SDK, shadcn/ui |
| 2026-05-09 | [Frontend Guidelines](active/FRONTEND_GUIDELINES.md) | active -- v2.0 four-tab layout |
| 2026-05-09 | [Backend Structure](active/BACKEND_STRUCTURE.md) | active -- v2.0 APIs |
| 2026-05-09 | [Implementation Plan](active/IMPLEMENTATION_PLAN.md) | active -- v2.0 frontend tasks |
| 2026-05-13 | [Phase Workflow Overview](active/phase_workflow_overview.md) | active -- four-phase pipeline reference |

## Planned Work

| Date | Title | Status |
|------|-------|--------|
| 2026-06-11 | [Pipeline Correctness Remediation](plans/2026-06-11-pipeline-correctness-remediation.md) | planned |
| 2026-06-11 | [Standalone Chat Upload AI](plans/2026-06-11-standalone-chat-upload-ai.md) | planned |
| 2026-06-11 | [VS Code Settings Sync Profiles](plans/2026-06-11-vscode-settings-sync-profiles.md) | planned |

## Diagrams

| File | Content |
|------|---------|
| [phase1.mmd](diagrams/phase1.mmd) | Phase 1: literature acquisition, parsing |
| [phase2.mmd](diagrams/phase2.mmd) | Phase 2: translation, dual evidence extraction |
| [phase3.mmd](diagrams/phase3.mmd) | Phase 3: entity standardization, knowledge alignment |
| [phase4.mmd](diagrams/phase4.mmd) | Phase 4: evidence visualization, expert feedback |

## Archive Index

The `archive/plans/` directory contains 64 completed plans (the bilingual comparison UX plan was added to this count after the 2026-06-12 rebase onto current dev). The `archive/codereview/` directory contains 22 resolved code reviews. See individual directories for full listings.

## Module README Index

Every `backend/` module has its own `README.md` developer guide. Key modules:

- **[backend/app/](../backend/app/README.md)** -- FastAPI application entry point
- **[backend/src/agents/](../backend/src/agents/README.md)** -- Pipeline orchestrator (LangGraph)
- **[backend/src/api/](../backend/src/api/README.md)** -- HTTP boundary, dependency injection
- **[backend/src/core/](../backend/src/core/README.md)** -- Vertical feature slices
- **[backend/src/dao/](../backend/src/dao/README.md)** -- Persistence layer
- **[backend/libs/](../backend/libs/README.md)** -- Rust native extensions (rust-io, net-io, files-io)
- **[services/model-server/](../services/model-server/README.md)** -- Embedding/Rerank/LLM server
