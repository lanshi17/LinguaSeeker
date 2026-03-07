# Decisions - ACMG Agent Refactor

## Session: ses_33cdadbf8ffef2nE52qpvy8S5B

### [2026-03-07T03:56] Architectural Decisions (from plan)
- Celery remains outer executor; Supervisor graph is internal to Celery tasks
- SupervisorState wraps ProcessingState (TypedDict, not extension)
- Per-task-type feature flags: `use_agent_workflow_pdf/pubmed/web`
- Re-export strategy: `state/schemas.py` re-exports from `domain/models.py`
- Prompt externalization: YAML files + Python format() + hardcoded fallback
- Translation: standalone Supervisor node (not embedded in extraction)
- Three task types: single Supervisor with conditional routing
