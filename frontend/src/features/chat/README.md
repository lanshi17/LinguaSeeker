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

Backend uses a custom (non-OpenAI) SSE format: `event: token\ndata: text\n\n` ending with `event: done\ndata: [DONE]`. The adapter in `providers/chatProvider.ts` transforms this into `SSEOutput` for `@ant-design/x-sdk`.

## Hooks

- `useChatSessions(runId)` -- list/create sessions for a pipeline run.
- `useChatMessages(sessionId)` -- message history + send messages.
