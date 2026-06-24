# Chat Feature

> AI-powered conversational interface for variant classification discussion. Uses `@ant-design/x` UI components and Server-Sent Events (SSE) for streaming.

## Structure

```
features/chat/
|-- index.ts                           # Barrel exports
|-- components/
|   |-- ChatView.tsx                   # Main chat UI (multi-session + single-session modes)
|   |-- SingleSessionChat.tsx          # Lightweight single-session chat (no sidebar)
|   |-- chatConfig.tsx                 # Shared chat config: ChatViewProps, Bubble roles
|   |-- ThinkingIndicator.tsx          # Loading animation during LLM inference
|   |-- WelcomeBlock.tsx               # Welcome screen with quick action buttons
|   |-- ChatActionBubble.tsx           # Renders action intents from the LLM agent
|   |-- useBubbleItems.tsx             # Transforms messages into Bubble.List items
|   |-- useChatProvider.ts             # Manages active AcmgChatProvider per session
|   |-- useSessionConversations.tsx    # Conversations sidebar state and operations
|   |-- useSessionUIState.ts           # Per-session ephemeral UI state (forms, pipeline status)
|   |-- usePipelineActions.ts          # Pipeline confirm/cancel action handlers
|   +-- forms/
|       |-- PipelineSummaryCard.tsx    # Conversational "Ready to start?" confirmation card
|       |-- PipelineStatusCard.tsx     # Pipeline status summary card
|       +-- index.ts                   # Barrel export for forms
|-- hooks/
|   +-- useChatSessions.ts             # Session list management (backend + localStorage)
|-- providers/
|   +-- acmgChatProvider.ts            # AcmgChatProvider: SSE streaming via @ant-design/x-sdk
|-- services/
|   +-- chat.ts                        # REST API: createSession, listSessions, listMessages, appendMessage, streamUrl
|-- types/
|   |-- chat.ts                        # ChatRole, ChatSessionResponse, ChatMessageResponse
|   +-- actions.ts                     # ChatActionIntent, ChatAction (discriminated union)
+-- utils/
    |-- localSessions.ts               # Browser localStorage session persistence
    |-- markdown.tsx                   # ChatMarkdown: Markdown rendering for chat bubbles (GFM + math)
    |-- messageHistory.ts              # Message history conversion to/from @ant-design/x format
    |-- messageRequests.ts             # Message request body construction
    |-- messageStore.ts                # Local message state management
    +-- sse.ts                         # SSE event parsing: text, action, done, keepalive, error
```

## Usage

```tsx
// Full chat with conversation sidebar and task queue
<ChatView />

// Full chat tied to a pipeline run
<ChatView processingRunId="run-abc" />

// Single session mode (direct URL navigation)
<ChatView sessionId="session-xyz" />
```

## Chat Modes

**FullChatView** (default `/chat`): Renders a `Conversations` sidebar from `@ant-design/x` for managing multiple chat sessions, a main bubble area, a `Sender` input, and an optional `TaskQueuePanel`. Standalone sessions are persisted in `localStorage`; pipeline-bound sessions are fetched from the backend.

**SingleSessionChat** (`/chat/:sessionId`): Lightweight view without sidebar. Loads message history from the backend on mount, renders bubbles with markdown and thinking indicators, and streams SSE replies.

## SSE Protocol

Backend streams standard SSE `data:` lines where each data payload is JSON:

| Event Type | Payload | Description |
|------------|---------|-------------|
| `text` | `{"type":"text","content":"..."}` | Incremental assistant text chunk |
| `action` | `{"type":"action","intent":"...","slots":{}}` | Agent action intent with slots |
| `done` | `{"type":"done"}` | Stream complete |
| `keepalive` | `{"type":"keepalive"}` | Connection heartbeat (15s) |
| `error` | `{"type":"error","message":"..."}` | Error message |

The SSE parser in `utils/sse.ts` (`appendAssistantChunk`) accumulates `"text"` chunks into the assistant message content and attaches `"action"` events as structured `ChatAction` objects.

## Chat Action Intents

The LLM backend can emit action intents alongside free-text replies:

| Intent | Behavior |
|--------|----------|
| `confirm-pipeline` | Opens inline pipeline confirmation form |
| `search-evidence` | Navigates to `/evidence?gene=...&variant=...` |
| `review-changes` | Navigates to `/evidence?review_status=...` |
| `check-pipeline-status` | Navigates to `/pipeline/:runId` or `/pipeline` |
| `start-pipeline` | Deprecated (legacy), shows info nudge |
| `upload-pdf` | Deprecated (legacy), shows info nudge |
| `classify-variant` | Recognized but form not yet implemented |
| `interpret-evidence` | Recognized but form not yet implemented |

## Provider Architecture

`AcmgChatProvider` extends `AbstractChatProvider` from `@ant-design/x-sdk`. On request:
1. User message is persisted via `POST /chat/sessions/{id}/messages` (done by `sendChatMessage()` before the provider runs).
2. Provider opens SSE stream via `GET /chat/sessions/{id}/stream?user_message=...`.
3. Tokens are parsed from the SSE stream and accumulated into the assistant bubble.
4. AbortController supports cancellation via the `Sender` cancel button or navigation.

## Hooks

| Hook | Description |
|------|-------------|
| `useChatSessions(runId?)` | Lists/creates sessions. When `runId` is null, manages standalone sessions in `localStorage`; otherwise fetches from backend. |
| `useChatProvider(sessionKey)` | Manages active `AcmgChatProvider` instance per session with `useXChat` integration. |
| `useSessionConversations(runId, clearRef)` | Conversations sidebar: items, active key, create/switch/delete. |
| `useSessionUIState(sessionKey)` | Per-session ephemeral state: active form, pipeline status, dispatched actions. |
| `useBubbleItems(...)` | Transforms `useXChat` messages into `Bubble.List` items with action rendering. |
| `usePipelineActions(...)` | Handles pipeline confirm/cancel from chat action forms. |

## Utils

| Module | Description |
|--------|-------------|
| `localSessions.ts` | Persists standalone session metadata in `localStorage` (`chat.sessions`, `chat.activeSession`) |
| `markdown.tsx` | `ChatMarkdown` component: `react-markdown` with GFM, math (KaTeX), and custom styling |
| `messageHistory.ts` | Converts backend `ChatMessageResponse[]` to `@ant-design/x` format and back |
| `messageRequests.ts` | Builds request body for `POST /chat/sessions/{id}/messages` |
| `messageStore.ts` | Local message state management for optimistic updates |
| `sse.ts` | SSE event parser: `appendAssistantChunk()` accumulates text/action/done/keepalive/error events |

## Standalone Sessions

`/chat` supports standalone sessions without a pipeline run. Session metadata (ID, creation time, message count) is persisted in browser `localStorage`. The active session ID is also stored there so reloads restore the last active conversation. Message history and assistant replies are persisted in the backend database. If a session returns 404, it is automatically removed from localStorage.

## Testing

```bash
cd frontend
bun run test tests/features/chat/
```

Test files cover: `acmgChatProvider`, `ChatActionBubble`, `ChatMarkdown`, `localSessions`, `messageHistory`, `messageRequests`, `messageStore`, `sse`, `useChatSessions`.
