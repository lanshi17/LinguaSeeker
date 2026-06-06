# Ant Design X AI Chat Page

**Date**: 2026-06-06
**Status**: Planning

---

## Goal

Replace the custom chat components with `@ant-design/x` — Ant Design's AI chat component library. Get a production-quality AI chat page with streaming, conversation management, and typing animations out of the box.

---

## Packages to Install

```bash
npm install antd @ant-design/x @ant-design/x-sdk @ant-design/icons
```

| Package | Purpose |
|---------|---------|
| `antd` | Base UI library (peer dependency of @ant-design/x) |
| `@ant-design/x` | AI chat components: Bubble, Sender, Conversations, Welcome, Prompts |
| `@ant-design/x-sdk` | Hooks: useXChat, useXConversations; Providers: OpenAIChatProvider |
| `@ant-design/icons` | Ant Design icon set |

---

## Architecture

### Custom Backend Provider

Our backend is NOT OpenAI-compatible. We need a custom `AbstractChatProvider` that:
- Calls `POST /api/v1/chat/sessions/{id}/messages` to send user messages
- Connects to `GET /api/v1/chat/sessions/{id}/stream` for SSE streaming
- Maps our `ChatSSEEvent` format to `MessageInfo` objects

### Component Mapping

| Old Custom Component | New @ant-design/x Component |
|---------------------|----------------------------|
| `ChatMessageList` | `Bubble.List` |
| `ChatMessageBubble` | `Bubble` (via Bubble.List items) |
| `ChatComposer` | `Sender` |
| `ChatSessionList` | `Conversations` |
| (new) | `Welcome` + `Prompts` (empty state) |

### Files to Create/Modify

| File | Action |
|------|--------|
| `src/features/chat/providers/acmgChatProvider.ts` | **Create** — custom provider for our backend |
| `src/features/chat/components/ChatView.tsx` | **Rewrite** — use Bubble.List, Sender, Conversations |
| `src/features/chat/components/ChatMessageList.tsx` | **Delete** — replaced by Bubble.List |
| `src/features/chat/components/ChatMessageBubble.tsx` | **Delete** — replaced by Bubble |
| `src/features/chat/components/ChatComposer.tsx` | **Delete** — replaced by Sender |
| `src/features/chat/components/ChatSessionList.tsx` | **Delete** — replaced by Conversations |
| `src/features/chat/index.ts` | **Update** — remove deleted exports, add ChatView |
| `app/(dashboard)/chat/page.tsx` | **Keep** — already wires ChatView |
| `app/(dashboard)/chat/[sessionId]/page.tsx` | **Keep** — already wires ChatView |
| `app/layout.tsx` | **Update** — add antd style provider if needed |

---

## ChatView Component Design

```
┌─────────────────────────────────────────────────────┐
│  XProvider                                          │
│  ┌──────────┬──────────────────────────────────────┐│
│  │Convrsatns│           Main Area                  ││
│  │          │  ┌────────────────────────────────┐  ││
│  │ + New    │  │  Welcome + Prompts (empty)     │  ││
│  │          │  │  -- or --                       │  ││
│  │ Conv 1   │  │  Bubble.List (messages)         │  ││
│  │ Conv 2   │  │    user: "What is BRCA1?"       │  ││
│  │ Conv 3   │  │    assistant: "BRCA1 is..."     │  ││
│  │          │  └────────────────────────────────┘  ││
│  │          │  ┌────────────────────────────────┐  ││
│  │          │  │  Sender (input + send/cancel)  │  ││
│  │          │  └────────────────────────────────┘  ││
│  └──────────┴──────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

### Flow

1. Page loads → `useXConversations` initializes conversation list
2. User clicks "+ New" → creates conversation via `POST /api/v1/chat/sessions`
3. User types message → `Sender.onSubmit` → `useXChat.onRequest`
4. Custom provider sends `POST /api/v1/chat/sessions/{id}/messages`
5. Provider opens SSE to `GET /api/v1/chat/sessions/{id}/stream`
6. SSE tokens update message via `onUpdate` callback
7. `Bubble.List` renders streaming message with typing animation
8. SSE `done` event → provider calls `onSuccess` → message status = `success`

---

## Verification

1. `npm run type-check` — 0 errors
2. `npm run lint` — 0 warnings
3. `npm run dev` — chat page loads with Welcome + Prompts
4. Sending a message shows streaming response with typing animation
