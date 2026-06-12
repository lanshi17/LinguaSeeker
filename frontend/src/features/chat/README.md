# Chat Feature

> AI-powered conversational interface for variant classification discussion. Uses `@ant-design/x` UI and Server-Sent Events (SSE) for streaming.

## Structure

```
features/chat/
├── components/
│   ├── ChatView.tsx           Main chat UI (XProvider, Bubble.List, Sender, Conversations)
│   └── forms/
│       ├── PipelineStartForm  Form to start a pipeline from chat
│       └── PipelineStatusCard Pipeline status summary card
├── hooks/
│   ├── useChatSessions.ts     Query + mutation for session list
│   └── useChatMessages.ts     Query + mutation for message history
├── providers/chatProvider.ts  Backend SSE -> @ant-design/x-sdk adapter
├── services/chat.ts           REST API calls + SSE stream URL builder
├── types/chat.ts              ChatRole, ChatSessionResponse, ChatMessageResponse, ChatSSEEvent
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

## Standalone Sessions

`/chat` supports standalone chat sessions without a pipeline run. Standalone
session metadata (session ID, creation time, message count) is persisted in
browser `localStorage`. The active session ID is also stored there so reloads
restore the last active conversation. All message history and assistant replies
are persisted in the backend database.
