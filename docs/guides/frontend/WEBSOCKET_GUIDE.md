# Frontend WebSocket Guide

## Scope

This guide describes the current frontend WebSocket implementation used by the ACMG-Lingua request monitor flow. The source of truth is:

- `apps/frontend/src/services/websocket.ts`
- `apps/frontend/src/store/workflowStore.ts`
- `apps/frontend/src/store/useWorkflowStore.ts`
- `apps/frontend/src/pages/requests/request-monitor-page.tsx`

This document intentionally replaces older guidance that no longer matches the current implementation.

## Current architecture

The frontend uses a small shared WebSocket service plus a Zustand workflow store:

1. `createWebSocketService(...)` creates a service that can open request and task streams, parse JSON payloads, and fan out messages to subscribers.
2. `workflowStore.ts` subscribes to those channels and stores the latest request/task snapshots, derived workflow timelines, and connection metadata.
3. `useWorkflowStore.ts` exports the single app-facing store instance created with `wsService`.
4. `RequestMonitorPage` combines stream data with HTTP hydration and request polling so the UI can stay live without depending on polling alone.

## WebSocket service

`apps/frontend/src/services/websocket.ts` exports:

- `createWebSocketService(options?)`
- `wsService`

### Practical API

The returned service exposes four methods:

- `subscribe(channel, listener)`
- `connectToRequest(requestId)`
- `connectToTask(taskId)`
- `disconnectAll()`

### URL construction

The service derives its base WebSocket URL from the frontend API base URL:

- If the configured API base is HTTP/HTTPS, it is converted to `ws://` or `wss://`
- If running in the browser without an explicit absolute API base, it falls back to the current browser host
- If running outside the browser, it falls back to `ws://localhost:8000`

### Current stream endpoints

The current implementation connects to these endpoints:

- Request stream: `WS /api/v1/stream/requests/{request_id}`
- Task stream: `WS /api/v1/stream/{task_id}`

Examples:

```text
ws://localhost:8000/api/v1/stream/requests/req-123
ws://localhost:8000/api/v1/stream/task-456
```

### Message handling behavior

The service expects each WebSocket message to be JSON. On message receipt it:

1. Parses `event.data` as JSON
2. Notifies listeners on the matching channel
3. Emits a synthetic error payload when parsing fails

Current error payloads produced by the service are:

- `{ error: 'invalid_json', raw: ev.data }` when the message is not valid JSON
- `{ error: 'socket_error' }` from `socket.onerror`
- `{ error: 'socket_close_failed' }` on the `system` channel if `disconnectAll()` throws while closing a socket

Caveat: the service is intentionally minimal. It does not currently implement reconnect logic, heartbeat handling, or channel-specific validation beyond JSON parsing.

## Workflow store

`apps/frontend/src/store/workflowStore.ts` is the main state layer for stream-driven request/task monitoring.

### Stored state

The store keeps:

- `currentRequest: TaskRequestStatusResponse | null`
- `currentTask: TaskStatusResponse | null`
- `requestTimeline: WorkflowTimelineStep[]`
- `taskTimeline: WorkflowTimelineStep[]`
- `requestConnection: { requestId: string | null; connected: boolean }`
- `taskConnection: { taskId: string | null; connected: boolean }`

### Watching a request

`watchRequest(requestId)` does two things:

1. Subscribes to channel `request:${requestId}`
2. Calls `service.connectToRequest(requestId)`

When payloads arrive, the store treats them as `TaskRequestStatusResponse` and updates:

- `currentRequest`
- `requestTimeline`
- `requestConnection`

### Watching a task

`watchTask(taskId)` similarly:

1. Subscribes to channel `task:${taskId}`
2. Calls `service.connectToTask(taskId)`

When payloads arrive, the store treats them as `TaskStatusResponse` and updates:

- `currentTask`
- `taskTimeline`
- `taskConnection`

If the task payload contains `error`, or `status === 'failure'`, the store also pushes a toast with title `Task stream error`.

### Timeline projection

The store derives simple three-step timelines for both requests and tasks:

- `Queued`
- `Running`
- `Completed`

For request snapshots:

- `queued` is always marked completed once a request payload has arrived
- `success` marks all steps completed
- non-success request payloads leave the request in a running state

For task snapshots:

- `workflow_status_description` is copied into the running/completed step description when present
- `progress_percentage` is copied into the step progress when present
- `failure` marks the running step as `error`
- `success` marks all steps completed

### Reset behavior

`reset()` unsubscribes request/task listeners, calls `service.disconnectAll()`, and resets all request/task data, timelines, and connection state back to their initial values.

## useWorkflowStore

`apps/frontend/src/store/useWorkflowStore.ts` is intentionally thin:

```ts
export const useWorkflowStore = createWorkflowStore(wsService);
```

This file does not add extra behavior. It simply exports the app store instance built from the shared `wsService` singleton.

## RequestMonitorPage data flow

`apps/frontend/src/pages/requests/request-monitor-page.tsx` is the clearest example of how stream data, polling, and app-store hydration work together.

### What happens on page load

When `RequestMonitorPage` mounts for a `requestId`, it starts two independent flows:

1. `fetchRequest(requestId)` hydrates request data into the app store through `useAppStore`
2. `watchRequest(requestId)` starts the request WebSocket watch through `useWorkflowStore`

On unmount, the page calls `resetWorkflow()`.

### Stream-first request selection

The page only trusts stream data when the active stream connection and payload both match the current route `requestId`.

In practice, it builds:

- `streamedSnapshot` from `workflowStore.currentRequest` when the streamed request matches the active request id
- `pollingSnapshot` from `useRequestPolling(...)` when polling has fetched the active request id
- `appStoreSnapshot` from `useAppStore().currentRequest` when the hydration fetch matches the active request id

The chosen request data is:

```ts
data = streamedSnapshot ?? pollingSnapshot ?? appStoreSnapshot;
```

So the precedence is:

1. Matching active stream snapshot
2. Polling snapshot
3. App-store hydration snapshot

### Polling fallback relationship

Polling is not the primary source of truth. It is enabled only when the page does not currently have a matching streamed request snapshot:

```ts
enabled: Boolean(requestId && !streamedRequest)
```

That means the page behavior is:

- Prefer the request stream when a matching stream snapshot exists
- Fall back to HTTP polling every 2 seconds when stream request data is absent
- Fall back again to the app-store hydration snapshot if polling has not yet produced data

`useRequestPolling` also skips work while the browser tab is hidden, because it defers each polling tick when `document.visibilityState === 'hidden'`.

### Task stream usage on the page

Task streams are not opened for every paper immediately. Instead, when a paper row is expanded the page:

1. Calls `watchTask(p.paper_task_id)`
2. Loads paper detail via HTTP

The expanded paper then renders workflow information from the current task stream when `currentTask.paper_task_id` matches that paper.

## Recommended usage pattern

If you need live request/task status elsewhere in the frontend, follow the current pattern:

1. Use `useWorkflowStore` rather than creating ad hoc WebSocket code in components
2. Call `watchRequest(requestId)` for request-level monitoring
3. Call `watchTask(taskId)` only when task-level detail is actually needed
4. Keep a non-stream fallback path for initial hydration or cases where no matching stream snapshot exists
5. Call `reset()` when leaving the monitored screen so sockets and listeners are cleaned up

## Implementation notes

- The WebSocket service is intentionally minimal: there is no reconnect or heartbeat logic in the current frontend code.
- `workflowStore.ts` treats parsed payloads as request/task response shapes, but it does not perform runtime schema validation beyond JSON parsing.
- `requestConnection.connected` and `taskConnection.connected` become `true` after matching payloads are received, so they are better read as "stream has produced data for this id" than as a low-level socket-open flag.
