# Chat Feature Module

> AI-powered conversational interface for discussing variant classification, evidence review, and pipeline results. Uses Server-Sent Events (SSE) for streaming responses from the backend. Integrates with `@ant-design/x` for a polished chat UI with conversation sidebar, streaming bubbles, and prompt suggestions.

## Quick Start

```typescript
import { ChatView } from "@/features/chat";

// Full chat with conversation sidebar:
<ChatView processingRunId="run-abc-123" />

// Single session chat (no sidebar):
<ChatView sessionId="session-xyz-456" />
```

## Architecture

```
features/chat/
├── types/chat.ts                    # ChatRole, ChatSessionResponse, ChatMessageResponse, ChatSSEEvent
├── services/chat.ts                 # REST API calls + SSE stream URL builder
├── providers/acmgChatProvider.ts    # Custom fetch adapter: backend SSE → @ant-design/x-sdk SSEOutput
├── hooks/
│   ├── useChatSessions.ts           # Query + mutation for session list management
│   └── useChatMessages.ts           # Query + mutation for message history and sending
├── components/ChatView.tsx          # Main chat UI with XProvider, Bubble.List, Sender, Conversations
└── index.ts                         # Barrel exports
```

### Data Flow

```
User types message in Sender
  → onRequest({ messages: [{ role: "user", content: "..." }] })
    → @ant-design/x-sdk calls provider.request()
      → POST /api/v1/chat/sessions/{id}/messages (sends message)
      → GET  /api/v1/chat/sessions/{id}/stream (SSE stream)
        → acmgFetch transforms backend SSE → SSEOutput stream
          → Bubble.List renders streaming tokens in real-time
```

### Backend SSE Protocol

The backend's chat API is **NOT OpenAI-compatible**. It uses a custom SSE format:

```
event: token
data: some text

event: token
data: more text

event: done
data: [DONE]
```

The `acmgFetch` adapter in `providers/acmgChatProvider.ts` transforms this into the `SSEOutput` shape (`{ data: string; event?: string }`) expected by `@ant-design/x-sdk`.

## Public API

### Components

| Component | Props | Description |
|-----------|-------|-------------|
| `<ChatView />` | `processingRunId?: string, sessionId?: string` | Full-featured chat UI. If `sessionId` provided, shows single-session mode. If `processingRunId` provided, shows conversation sidebar. |

### Hooks

| Hook | Signature | Description |
|------|-----------|-------------|
| `useChatSessions(runId)` | `(runId: string) => { sessions, createSession, ... }` | Manage chat sessions for a pipeline run |
| `useChatMessages(sessionId)` | `(sessionId: string) => { messages, sendMessage, ... }` | Query message history + send new messages |

### Provider Factory

| Function | Signature | Description |
|----------|-----------|-------------|
| `createAcmgChatProvider(sessionId)` | `(sessionId: string) => DefaultChatProvider` | Creates a chat provider configured for a specific session's SSE stream |

### Types

| Type | Description |
|------|-------------|
| `ChatRole` | `"user" \| "assistant" \| "system"` |
| `ChatSessionResponse` | `{ session_id, processing_run_id, created_at, message_count }` |
| `ChatMessageResponse` | `{ message_id, role, content, evidence_id?, entity_id?, created_at }` |
| `ChatSSEEvent` | `{ event: "token" \| "done" \| "error", data: string }` |

### Service Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `createSession(runId)` | `(runId: string) => Promise<ChatSessionResponse>` | `POST /chat/sessions` |
| `listSessions(runId)` | `(runId: string) => Promise<ChatSessionResponse[]>` | `GET /chat/sessions/{runId}` |
| `listMessages(sessionId)` | `(sessionId: string, limit?: number) => Promise<ChatMessageResponse[]>` | `GET /chat/sessions/{id}/messages` |
| `appendMessage(sessionId, content, evidenceId?)` | `(sessionId: string, content: string, evidenceId?: string) => Promise<ChatMessageResponse>` | `POST /chat/sessions/{id}/messages` |
| `streamUrl(sessionId)` | `(sessionId: string) => string` | Returns the SSE stream URL |

## Internal Design

### SSE Stream Adapter

The `acmgFetch` function wraps the native `fetch` response and transforms the backend's SSE stream into a `ReadableStream<SSEOutput>`:

```typescript
// Backend sends: "event: token\ndata: some text\n\n"
// acmgFetch converts to: { data: "some text", event: "token" }
```

This allows `@ant-design/x-sdk`'s `XRequest` to consume the stream as if it were a standard OpenAI-compatible API, even though the protocol is different.

### Conversation Sidebar

`FullChatView` uses `useXConversations` from `@ant-design/x-sdk` to manage multiple chat sessions. Users can:
- Create new sessions (linked to the current `processingRunId`)
- Switch between sessions via the sidebar
- Each session gets its own `DefaultChatProvider` cached in a `Map`

### Welcome Screen and Prompts

When no messages exist, `ChatView` displays:
- `<Welcome>` component with title and description
- `<Prompts>` component with 3 ACMG-specific suggestions:
  - "ACMG Classification"
  - "Evidence Review"
  - "Explain Result"

Clicking a prompt automatically sends the associated message.

### Abort / Cancel

The `<Sender>` component exposes an `onCancel` handler that calls `abort()` from `useXChat`, which cancels the in-flight SSE request.

## Usage Patterns

### Embed chat in a pipeline results page

```typescript
import { ChatView } from "@/features/chat";

function PipelineResultsPage({ runId }: { runId: string }) {
  return (
    <div>
      <h1>Pipeline Results</h1>
      <ChatView processingRunId={runId} />
    </div>
  );
}
```

### Link to a specific session

```typescript
<Link href={`/chat/${session.session_id}`}>
  Open Session {session.session_id.slice(0, 8)}
</Link>
```

### Custom message rendering

For custom UI, use the hooks directly:

```typescript
const { messages, sendMessage } = useChatMessages(sessionId);

return (
  <ul>
    {messages.map((m) => (
      <li key={m.message_id}>{m.role}: {m.content}</li>
    ))}
  </ul>
);
```

## Extension Guide

### Adding evidence linking

Messages can reference specific evidence cards via `evidence_id`:

```typescript
await sendMessage({
  content: "Explain this evidence",
  evidenceId: "evidence-abc-123",
});
```

The backend can then include the evidence context in the AI response.

### Adding tool use / function calling

To enable the AI to call tools (e.g., search evidence, run classification):
1. Extend the backend SSE protocol with `event: tool_call` and `event: tool_result`
2. Update `acmgFetch` to parse these events and surface them to the UI
3. Add a tool registry in `ChatView` that dispatches tool calls to feature modules

### Switching to OpenAI-compatible backend

If the backend is refactored to use the OpenAI chat completions format:
1. Replace `acmgFetch` with the default fetch (remove the custom adapter)
2. Update `XRequest` to use the standard OpenAI streaming protocol
3. The rest of the UI remains unchanged

## Performance Notes

- **Streaming**: Tokens arrive in real-time via SSE. No buffering — each token is rendered immediately.
- **Message history**: `listMessages` defaults to `limit=100`. For longer conversations, implement pagination or virtualization.
- **Provider caching**: `FullChatView` caches providers in a `Map` keyed by session ID, so switching sessions doesn't recreate the provider.
- **No local persistence**: Messages are stored only in the backend database. TanStack Query caches them in memory.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `@ant-design/x` | ^2.7.0 | Chat UI components: `XProvider`, `Bubble`, `Sender`, `Conversations`, `Welcome`, `Prompts` |
| `@ant-design/x-sdk` | ^2.7.0 | `DefaultChatProvider`, `XRequest`, `useXChat`, `useXConversations` |
| `@ant-design/icons` | ^6.2.5 | `RobotOutlined`, `UserOutlined` for avatars |
| `antd` | ^6.4.3 | `Avatar`, `message` (toast notifications) |
| `@tanstack/react-query` | ^5.50.0 | Session and message queries/mutations |

## Testing

Tests live in `frontend/tests/features/chat/`.

```bash
cd frontend
npm run test -- --testPathPattern=chat
```

Current test gaps:
- SSE streaming integration tests require a running backend
- Provider adapter (`acmgFetch`) is difficult to unit test without mocking `fetch` and `ReadableStream`
