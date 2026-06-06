# Frontend MVP: Three Modules

**Date**: 2026-06-06
**Status**: Planning

---

## Goal

Simplify frontend to 3 modules: **AI Chat**, **Pipeline** (with workflow status), **Evidence Query**.

---

## Architecture

```
Sidebar Navigation
├── Pipeline     /pipeline              Submit + workflow status flow
├── Evidence     /evidence              Search & browse evidence cards
└── AI Chat      /chat                  @ant-design/x chat interface
```

---

## Module 1: Pipeline (Workflow Status Flow)

**Route**: `/pipeline`
**Existing API**: `POST /pipeline/run`, `GET /pipeline/runs/{id}/status`

### Page Layout
```
┌─────────────────────────────────────────────────┐
│  Pipeline                                  ⟶  │
├─────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────┐    │
│  │  Submit Form                            │    │
│  │  [Online ▾] [query input]  [Start →]   │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │  Workflow Status                        │    │
│  │                                         │    │
│  │  ① Acquisition  ──→  ② Extraction  ──→ ③ Standardization │
│  │     ✅ 12.3s            🔄 running         ⏳ queued    │    │
│  │                                         │    │
│  │  Run ID: abc-123                        │    │
│  │  Started: 2026-06-06 14:30             │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │  Phase Details (expandable cards)       │    │
│  │  ┌─ Phase 1: Document Acquisition ────┐ │    │
│  │  │ Status: completed  Duration: 12.3s │ │    │
│  │  │ Summary: Parsed 15 pages, 3 images │ │    │
│  │  └────────────────────────────────────┘ │    │
│  │  ┌─ Phase 2: Evidence Extraction ─────┐ │    │
│  │  │ Status: running   Elapsed: 45.2s   │ │    │
│  │  └────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

### Implementation
- `PipelineSubmitForm` — source type selector + query input + start button
- `WorkflowTimeline` — 3-phase visual (Ant Design Steps component)
- `PhaseDetailCard` — expandable card per phase (status, timing, summary, error)
- `usePipelineRun` — mutation hook for POST
- `usePipelineStatus` — polling hook (2s interval, stops on terminal)

---

## Module 2: Evidence Query

**Route**: `/evidence`
**Backend gap**: Need `GET /api/v1/evidence/search` endpoint

### Page Layout
```
┌─────────────────────────────────────────────────┐
│  Evidence Search                           ⟶  │
├─────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────┐    │
│  │  Gene [____] Variant [____] Disease [__]│    │
│  │  PMID [____]           [Search →]       │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │  Results Table (antd Table)             │    │
│  │  ┌──────┬────────┬──────┬──────┬─────┐  │    │
│  │  │ Gene │Variant │Disease│Class │PMID │  │    │
│  │  ├──────┼────────┼──────┼──────┼─────┤  │    │
│  │  │BRCA1 │c.5266..│Breast│Patho │1234 │  │    │
│  │  │TP53  │c.743G..│Li-Fe │Patho │5678 │  │    │
│  │  └──────┴────────┴──────┴──────┴─────┘  │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

### Implementation
- `EvidenceSearchForm` — antd Form with gene/variant/disease/PMID fields
- `EvidenceResultsTable` — antd Table with columns for key evidence fields
- `useEvidenceSearch` — TanStack Query mutation hook
- Service: `searchEvidence()` → `GET /api/v1/evidence/search`

### Backend: New API Endpoint Needed
`GET /api/v1/evidence/search` — wires existing `SearchIndexRepository.search()` to HTTP.

---

## Module 3: AI Chat (Already Done)

**Route**: `/chat`
**Status**: ✅ Implemented with @ant-design/x

No changes needed. Already has:
- `Bubble.List` for messages
- `Sender` for input
- `Conversations` for session sidebar
- `Welcome` + `Prompts` for empty state
- Custom `AcmgChatProvider` for SSE streaming

---

## Navigation Changes

### Sidebar (Simplified)
```
Pipeline     (Workflow icon)
Evidence     (Search icon)
AI Chat      (MessageSquare icon)
```

Remove from sidebar: Tasks, Graph, Settings

### Routes
| Route | Page | Module |
|-------|------|--------|
| `/` | Redirect → `/pipeline` | — |
| `/pipeline` | Pipeline submit + workflow status | Pipeline |
| `/evidence` | Evidence search & browse | Evidence |
| `/chat` | AI chat (full view with sidebar) | Chat |

---

## Files to Create/Modify

### New
| File | Purpose |
|------|---------|
| `src/features/evidence-search/` | New feature module for evidence querying |
| `src/features/evidence-search/components/EvidenceSearchForm.tsx` | Search form |
| `src/features/evidence-search/components/EvidenceResultsTable.tsx` | Results table |
| `src/features/evidence-search/hooks/useEvidenceSearch.ts` | Search mutation hook |
| `src/features/evidence-search/services/evidenceSearch.ts` | API service |
| `src/features/evidence-search/types/evidenceSearch.ts` | Search types |
| `src/features/evidence-search/index.ts` | Barrel export |

### Modify
| File | Change |
|------|--------|
| `src/components/layout/Sidebar.tsx` | Simplify to 3 nav items |
| `src/features/pipeline/components/PipelineSubmitForm.tsx` | Refine with antd Form |
| `src/features/pipeline/components/WorkflowTimeline.tsx` | Use antd Steps |
| `src/features/pipeline/components/PhaseDetailCard.tsx` | Use antd Collapse/Card |

### Delete (unused in MVP)
| Directory | Reason |
|-----------|--------|
| `src/features/task-flow/` | Not in MVP |
| `src/features/literature/` | Not in MVP |
| `src/features/delta-audit/` | Not in MVP |
| `src/features/source-link/` | Not in MVP |
| `src/features/document-viewer/` | Not in MVP |
| `src/features/graph/` | Not in MVP |
| `app/(dashboard)/tasks/` | Not in MVP |
| `app/(dashboard)/documents/` | Not in MVP |
| `app/(dashboard)/evidence/[evidenceId]/` | Not in MVP |
| `app/(dashboard)/evidence/audit/` | Not in MVP |
| `app/(dashboard)/requests/` | Not in MVP |
| `app/(dashboard)/graph/` | Not in MVP |
| `app/(dashboard)/settings/` | Not in MVP |

---

## Backend: New Evidence Search Endpoint

`GET /api/v1/evidence/search`

Query params: `gene`, `variant`, `disease`, `pmid`, `doi`, `limit` (default 50)
Response: `{ items: EvidenceSearchResult[], total: int }`

Wires to existing `SearchIndexRepository.search()`.
Needs: Pydantic response model, route handler, router registration.

---

## Verification

1. `npm run type-check` — 0 errors
2. `npm run lint` — 0 warnings
3. `npm run dev` — 3 pages render correctly
4. Pipeline: submit → status polling → phase timeline updates
5. Evidence: search → results table displays
6. Chat: send message → streaming response
