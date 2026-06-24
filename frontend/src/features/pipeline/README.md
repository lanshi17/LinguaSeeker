# Pipeline Feature

> Manages the 3-phase evidence extraction pipeline: status polling, per-phase visualization, run history, and real-time task queue.

## Structure

```
features/pipeline/
|-- index.ts                           # Barrel exports
|-- components/
|   |-- PipelineStatusView.tsx         # Orchestrates timeline + phase cards for a single run
|   |-- PhaseTimeline.tsx             # Visual step-by-step progress (numbered circles)
|   |-- PhaseDetailCard.tsx           # Per-phase status card with timing, sub-nodes, and errors
|   |-- RunHistory.tsx                # List of past pipeline runs with search/filter
|   |-- RunListItem.tsx               # Individual run row in history list
|   |-- TaskQueuePanel.tsx            # Real-time sidebar panel showing active/recent/failed runs
|   +-- TaskQueueRow.tsx              # Individual row in the task queue panel
|-- hooks/
|   |-- usePipelineRun.ts             # useMutation for POST /pipeline/run
|   |-- usePipelineRuns.ts            # useQuery for listing pipeline runs
|   |-- usePipelineStatus.ts          # useQuery with 2s polling, auto-stops on terminal state
|   +-- usePhaseTimeline.ts           # Projects PipelineStatusResponse to PhaseTimelineStep[]
|-- services/
|   +-- pipeline.ts                   # startPipelineRun(), getPipelineStatus(), listPipelineRuns()
+-- types/
    +-- pipeline.ts                   # PipelineRunRequest/Response, PipelineStatusResponse, PhaseStatus, PhaseNode, etc.
```

## Usage

```tsx
import {
  PipelineStatusView,
  PhaseTimeline,
  RunHistory,
  TaskQueuePanel,
  usePipelineRun,
  usePipelineStatus,
  usePipelineRuns,
} from "@/features/pipeline";

// Status view for a single run
<PipelineStatusView runId="abc-123" />

// Run history page
<RunHistory />

// Task queue sidebar (used inside ChatView)
<TaskQueuePanel onClose={toggleTaskQueue} />

// Programmatic usage
const { mutateAsync: startRun } = usePipelineRun();
const result = await startRun({ source_type: "online", mode: "full", query: "BRCA1" });
const { data } = usePipelineStatus(runId);  // Polls every 2s
```

## Components

| Component | Description |
|-----------|-------------|
| `PipelineStatusView` | Page-level orchestrator for a single run: renders `PhaseTimeline` and `PhaseDetailCard` for each phase. |
| `PhaseTimeline` | Visual step-by-step progress with numbered circles, labels, and status indicators. |
| `PhaseDetailCard` | Per-phase card showing status, timing, sub-node details, counts, metrics, and errors. Exports `PhaseDetailCardSkeleton` for loading state. |
| `RunHistory` | Searchable, filterable list of all pipeline runs with status indicators. |
| `RunListItem` | Individual run row: title, status badge, elapsed time, phase progress. |
| `TaskQueuePanel` | Real-time sidebar panel with three tabs (Active, Recent, Failed). Shows live pipeline status with pulsing indicators and sync timestamp. |
| `TaskQueueRow` | Individual run card in the task queue: status dot, title, elapsed time, phase progress bar. |

## Hooks

| Hook | Returns | Description |
|------|---------|-------------|
| `usePipelineRun` | `useMutation` result | Starts a new pipeline run via `POST /pipeline/run`. |
| `usePipelineStatus(runId)` | `{ data, isLoading, ... }` | Polls `GET /pipeline/runs/{id}/status` every 2s. Auto-stops polling on terminal states (`completed`, `failed`, `skipped`). |
| `usePipelineRuns()` | `{ data, isLoading, isError, dataUpdatedAt }` | Lists all pipeline runs via `GET /pipeline/runs`. Polls every 5s. Tolerates 404/501 gracefully. |
| `usePhaseTimeline(statusData)` | `PhaseTimelineStep[]` | Projects `PipelineStatusResponse` to ordered timeline steps with status and duration. |

## Types

| Type | Description |
|------|-------------|
| `PipelineRunRequest` | POST body: `source_type`, `mode`, `content_base64?`, `filename?`, `pre_parsed_markdown?`, `query?`, `identifiers?`, `target_phase?`, `processing_run_id?`, `target?` |
| `PipelineRunResponse` | POST result: `processing_run_id`, `source_document_id`, `status`, `status_url` |
| `PipelineStatusResponse` | Status: `processing_run_id`, `pipeline_status`, `current_phase?`, `phases` (keyed by phase_id), `error_message?`, `started_at?`, `completed_at?`, `elapsed_seconds?`, `title?` |
| `PhaseStatus` | Per-phase: `status`, `started_at?`, `completed_at?`, `duration_seconds?`, `error?`, `summary?`, `nodes?` (sub-nodes), `count?` |
| `PhaseNode` | Sub-node: `node_id`, `label`, `status`, `progress?`, `started_at?`, `completed_at?`, `duration_seconds?`, `count?`, `metrics?`, `error?` |
| `PipelineRunSummary` | Compact run summary for list view: `processing_run_id`, `pipeline_status`, `title?`, `started_at?`, `completed_at?`, `elapsed_seconds?`, `current_phase?`, `completed_phases?`, `total_phases?` |
| `PipelineRunListResponse` | List response: `items[]`, `total` |
| `PhaseTimelineStep` | Projected step: `phaseId`, `label`, `status`, `duration?` |

## Phases

| Phase ID | Label |
|----------|-------|
| `phase_1` | Document Acquisition |
| `phase_2` | Evidence Extraction |
| `phase_3` | Entity Standardization |

Polling stops automatically on `completed`, `failed`, or `skipped` status.

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/pipeline/run` | POST | Start a new pipeline run |
| `/api/v1/pipeline/runs/{id}/status` | GET | Get status for a single run |
| `/api/v1/pipeline/runs` | GET | List all pipeline runs (paginated) |

## Testing

Tests not yet implemented for pipeline feature. Test directory: `frontend/tests/pipeline/` (planned).

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `@tanstack/react-query` | Data fetching, polling, mutations |
| `react-router-dom` | Navigation (Link, useNavigate) |
| `antd` | Card, Table, Button, Tag, Typography |
| `lucide-react` | Icons (Activity, AlertTriangle, Inbox, etc.) |
| `@/components/ui` | Skeleton, LivePulse, MetricTile |
| `@/lib/hooks` | `useElapsedSeconds` |
| `@/lib/utils` | `formatDuration`, `formatRelative` |
