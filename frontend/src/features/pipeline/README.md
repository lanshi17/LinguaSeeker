# Pipeline Feature

> Manages the 3-phase evidence extraction pipeline: submission, status polling, and per-phase visualization.

## Structure

```
features/pipeline/
├── components/
│   ├── PipelineSubmitForm.tsx   Source type selector + file upload / query input
│   ├── PipelineStatusView.tsx   Orchestrates timeline + phase cards
│   ├── PhaseTimeline.tsx        Visual step-by-step progress (numbered circles)
│   ├── PhaseDetailCard.tsx      Per-phase status card with timing and errors
│   ├── RunHistory.tsx           List of past pipeline runs
│   └── RunListItem.tsx          Individual run row in history list
├── hooks/
│   ├── usePipelineRun.ts        useMutation for POST /pipeline/run
│   ├── usePipelineRuns.ts       useQuery for listing pipeline runs
│   ├── usePipelineStatus.ts     useQuery with 2s polling, auto-stops on terminal state
│   └── usePhaseTimeline.ts      Projects status dict to ordered PhaseTimelineStep[]
├── services/pipeline.ts         startPipelineRun(), getPipelineStatus()
├── types/pipeline.ts            PipelineRunRequest/Response, PipelineStatusResponse, PhaseStatus
└── index.ts
```

## Usage

```tsx
<PipelineSubmitForm />
const { mutateAsync: startRun } = usePipelineRun();
const result = await startRun({ source_type: "online", mode: "full", query: "BRCA1" });
const { data } = usePipelineStatus(runId);  // Polls every 2s
const steps = usePhaseTimeline(data);
```

## Phases

| Phase ID | Label |
|----------|-------|
| `phase_1` | Document Acquisition |
| `phase_2` | Evidence Extraction |
| `phase_3` | Entity Standardization |
Polling stops automatically on `completed`, `failed`, or `cancelled`.