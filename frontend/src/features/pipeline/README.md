# Pipeline Feature Module

> Manages the 3-phase evidence extraction pipeline lifecycle: submission, real-time status polling, and per-phase result visualization. This is the primary workflow surface of ACMG Lingua.

## Quick Start

```typescript
import { usePipelineRun, PipelineSubmitForm } from "@/features/pipeline";

// Declarative — drop the form into any page:
<PipelineSubmitForm />

// Programmatic — start a run from custom UI:
const { mutateAsync: startRun } = usePipelineRun();
const result = await startRun({ source_type: "online", mode: "full", query: "BRCA1 pathogenic" });
router.push(`/pipeline/${result.processing_run_id}`);
```

## Architecture

```
features/pipeline/
├── types/pipeline.ts              # PipelineRunRequest, PipelineRunResponse, PipelineStatusResponse, PhaseStatus, PhaseTimelineStep
├── services/pipeline.ts           # startPipelineRun(), getPipelineStatus() — thin wrappers over apiClient
├── hooks/
│   ├── usePipelineRun.ts          # useMutation for POST /pipeline/run
│   ├── usePipelineStatus.ts       # useQuery with 2s polling, auto-stops on terminal state
│   └── usePhaseTimeline.ts        # Projects status dict → ordered PhaseTimelineStep[]
├── components/
│   ├── PipelineSubmitForm.tsx     # Source type selector + file upload / query input
│   ├── PipelineStatusView.tsx     # Orchestrates timeline + phase cards for a given runId
│   ├── PhaseTimeline.tsx          # Visual step-by-step pipeline progress (numbered circles + connectors)
│   └── PhaseDetailCard.tsx        # Per-phase status card with timing, summary, and error info
└── index.ts                       # Barrel exports
```

### Data Flow

```
User submits form
  → usePipelineRun (mutation)
    → POST /pipeline/run
      → Returns { processing_run_id, status_url }
        → Navigate to /pipeline/{runId}

PipelineStatusView renders with runId
  → usePipelineStatus (query, 2s poll)
    → GET /pipeline/runs/{runId}/status
      → Returns PipelineStatusResponse
        → usePhaseTimeline projects to PhaseTimelineStep[]
          → PhaseTimeline renders visual progress
          → PhaseDetailCard renders per-phase detail
```

### Polling Strategy

`usePipelineStatus` uses `refetchInterval` from TanStack Query:
- Polls every **2 seconds** while `pipeline_status` is `queued` or `running`
- Stops polling when status reaches a terminal state: `completed`, `failed`, or `cancelled`
- No manual cleanup needed — TanStack Query handles interval lifecycle

## Public API

### Hooks

| Hook | Signature | Description |
|------|-----------|-------------|
| `usePipelineRun()` | `() => UseMutationResult<PipelineRunResponse, Error, PipelineRunRequest>` | Mutation to start a new pipeline run |
| `usePipelineStatus(runId)` | `(runId: string) => UseQueryResult<PipelineStatusResponse>` | Polls pipeline status every 2s until terminal |
| `usePhaseTimeline(status)` | `(status: PipelineStatusResponse \| undefined) => PhaseTimelineStep[]` | Projects status dict to ordered timeline array |

### Components

| Component | Props | Description |
|-----------|-------|-------------|
| `<PipelineSubmitForm />` | — | Full form: source type, query/file upload, submit button |
| `<PipelineStatusView runId={id} />` | `runId: string` | Complete status page: timeline + phase cards |
| `<PhaseTimeline steps={steps} />` | `steps: PhaseTimelineStep[]` | Visual numbered-circle timeline with connectors |
| `<PhaseDetailCard phaseId={id} phase={phase} />` | `phaseId: string, phase: PhaseStatus` | Single phase detail with status badge |

### Types

| Type | Description |
|------|-------------|
| `PipelineRunRequest` | Submission body: `source_type`, `mode`, `query?`, `file_content?`, `filename?`, `identifiers?`, `target_phase?` |
| `PipelineRunResponse` | Response: `processing_run_id`, `source_document_id`, `status`, `status_url` |
| `PipelineStatusResponse` | Full status: `pipeline_status`, `current_phase`, per-phase `phases` dict, timing, errors |
| `PhaseStatus` | Per-phase: `status`, `started_at`, `completed_at`, `duration_seconds`, `error`, `summary` |
| `PhaseTimelineStep` | Projected step: `phaseId`, `label`, `status`, `duration` |

### Service Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `startPipelineRun(body)` | `(body: PipelineRunRequest) => Promise<PipelineRunResponse>` | `POST /pipeline/run` |
| `getPipelineStatus(runId)` | `(runId: string) => Promise<PipelineStatusResponse>` | `GET /pipeline/runs/{runId}/status` |

## Internal Design

### Phase Ordering

`usePhaseTimeline` enforces a fixed ordering: `phase_1` -> `phase_2` -> `phase_3`. Labels are defined in `PHASE_LABELS`:

| Phase ID | Label |
|----------|-------|
| `phase_1` | Document Acquisition |
| `phase_2` | Evidence Extraction |
| `phase_3` | Entity Standardization |

Phases not present in the response are filtered out. This handles cases where phase 3 is skipped (e.g., `skip_phase_3_reason`).

### Visual Status Mapping

`PhaseTimeline` maps status to color styles:

| Status | Visual |
|--------|--------|
| `queued` | Gray circle |
| `running` | Blue circle with pulse animation |
| `completed` | Green circle |
| `failed` | Red circle |
| `cancelled` | Light gray circle |

Connector lines between phases turn green when the preceding phase is completed.

## Usage Patterns

### Start a pipeline and navigate to status

```typescript
const { mutateAsync: startRun } = usePipelineRun();
const router = useRouter();

async function handleStart(query: string) {
  const result = await startRun({ source_type: "online", mode: "full", query });
  router.push(`/pipeline/${result.processing_run_id}`);
}
```

### Embed status in a custom layout

```typescript
import { usePipelineStatus, usePhaseTimeline, PhaseTimeline } from "@/features/pipeline";

function MiniStatus({ runId }: { runId: string }) {
  const { data } = usePipelineStatus(runId);
  const steps = usePhaseTimeline(data);
  return <PhaseTimeline steps={steps} />;
}
```

### React to pipeline completion

```typescript
const { data } = usePipelineStatus(runId);

useEffect(() => {
  if (data?.pipeline_status === "completed") {
    // Navigate to results, show celebration, etc.
  }
  if (data?.pipeline_status === "failed") {
    addToast({ level: "error", title: "Pipeline failed", message: data.error_message ?? undefined });
  }
}, [data?.pipeline_status]);
```

## Extension Guide

### Adding a new phase (e.g., phase_4)

1. Add the new phase ID to the `PhaseId` union type in `@/lib/types/common`
2. Add the label to `PHASE_LABELS` in `usePhaseTimeline.ts`
3. The `PipelineStatusResponse.phases` dict will automatically include it
4. `PhaseTimeline` will render it as a new numbered circle

### Custom polling intervals

Override the default 2s interval by passing options to `usePipelineStatus` or wrapping it:

```typescript
// In the hook, change refetchInterval:
refetchInterval: (query) => {
  const status = query.state.data?.pipeline_status;
  if (["completed", "failed", "cancelled"].includes(status ?? "")) return false;
  return 5000; // 5 seconds instead
}
```

## Performance Notes

- **Polling overhead**: 2s interval is aggressive but appropriate for pipeline runs that typically complete in 30s-5min. Each poll is a lightweight JSON GET.
- **Memory**: `usePipelineStatus` uses TanStack Query's cache, so stale data is automatically garbage-collected after the component unmounts.
- **No WebSocket**: The backend does not currently expose a WebSocket endpoint. If one is added, `usePipelineStatus` should be updated to use `useSubscription` or a custom WS hook instead of polling.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `@tanstack/react-query` | ^5.50.0 | `useQuery` with `refetchInterval` for polling, `useMutation` for submission |
| `next/navigation` | (Next.js built-in) | `useRouter` for navigation after pipeline start |
| `lucide-react` | ^1.17.0 | Icons (via layout components) |

## Testing

Tests live in `frontend/tests/features/pipeline/`.

```bash
cd frontend
npm run test -- --testPathPattern=pipeline
```
