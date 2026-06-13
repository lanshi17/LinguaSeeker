# Chat Feature

> AI-powered conversational interface for variant classification discussion. Uses `@ant-design/x` UI and Server-Sent Events (SSE) for streaming.

## Structure

```
features/chat/
├── components/
│   ├── ChatView.tsx             Main chat UI (XProvider, Bubble.List, Sender, Conversations)
│   ├── ChatEmptyState.tsx       Empty state when no session is active
│   ├── ChatEmptyState.css       Styles for empty state
│   ├── prompts.ts               Default prompt suggestions for new conversations
│   └── forms/
│       ├── PipelineStartForm    Form to start a pipeline from chat
│       ├── PipelineStatusCard   Pipeline status summary card
│       └── index.ts             Barrel export for forms
├── hooks/
│   ├── useChatSessions.ts       Query + mutation for session list
│   └── useChatMessages.ts       Query + mutation for message history
├── providers/
│   ├── chatProvider.ts          Backend SSE -> @ant-design/x-sdk adapter
│   └── acmgChatProvider.ts      ACMG-specific chat provider with domain prompts
├── services/chat.ts             REST API calls + SSE stream URL builder
├── types/chat.ts                ChatRole, ChatSessionResponse, ChatMessageResponse, ChatSSEEvent
├── utils/
│   ├── intent.ts                Chat intent detection (question vs. analysis request)
│   ├── localSessions.ts         Browser localStorage session persistence
│   ├── markdown.tsx             Markdown rendering utilities for chat messages
│   ├── messageHistory.ts        Message history loading and management
│   ├── messageRequests.ts       Message send request construction
│   └── sse.ts                   SSE connection management and event parsing
└── index.ts
```

## Usage

```tsx
<ChatView processingRunId="run-abc" />  // Full chat with conversation sidebar
<ChatView sessionId="session-xyz" />    // Single session mode
```

## SSE Protocol

Backend streams standard SSE `data:` lines where each data payload is JSON:
`{"type":"text","content":"..."}`, `{"type":"done"}`, or
`{"type":"error","message":"..."}`. The adapter in `providers/chatProvider.ts`
accumulates `"text"` chunks into the assistant bubble content.

## Hooks

- `useChatSessions(runId?)` -- list/create sessions. When `runId` is null/undefined, manages standalone sessions in browser `localStorage`; when a `runId` is provided, fetches pipeline-bound sessions from the backend.
- `useChatMessages(sessionId)` -- message history + send messages.

## Utils

| Module | Description |
|--------|-------------|
| `intent.ts` | Detects chat message intent (question, analysis, command) for routing |
| `localSessions.ts` | Persists standalone session metadata in browser localStorage |
| `markdown.tsx` | Renders markdown content in chat bubbles with syntax highlighting |
| `messageHistory.ts` | Loads and manages message history for a session |
| `messageRequests.ts` | Constructs message send requests with proper formatting |
| `sse.ts` | Manages SSE connections, reconnection, and event parsing |

## Standalone Sessions

`/chat` supports standalone chat sessions without a pipeline run. Standalone
session metadata (session ID, creation time, message count) is persisted in
browser `localStorage`. The active session ID is also stored there so reloads
restore the last active conversation. All message history and assistant replies
are persisted in the backend database.
