# Frontend Agent Clarification Chat UI (v1) — Design

Date: 2026-03-15

## 1. Goal

Upgrade the existing task creation clarification step into a **chat-style agent interaction UI** while keeping the current backend contract unchanged.

This v1 design is based on the selected entry shape:

- **Option A (chosen):** upgrade the existing route `/tasks/new` (`TaskNewPage`) instead of introducing a new `/tasks/chat` route.

## 2. Context (Current Implementation)

- Page: `src/pages/tasks/task-new-page.tsx`
- Backend APIs:
  - `interactionStart({ user_input })` → `InteractionStartResponse`
  - `interactionRespond({ session_id, user_response })` → `InteractionRespondResponse`
- State (Zustand): `src/store/useTaskFlowStore.ts`
  - `taskForm: TaskFormStructured | null`
  - `interactionSessionId: string | null`
  - `interactionRound: number` (max clarification rounds = 2)
- Utility: `src/hooks/useScrollToBottom.ts` for chat/log auto-scroll.

The current UI is a form + “Question/Answer textarea” block; it is not presented as a conversation transcript.

## 3. Non-Goals (v1)

- No SSE/WebSocket/streaming agent events (no contract found in the current codebase).
- No change to backend payload schemas.
- No new global state shape (reuse `useTaskFlowStore`).

## 4. UX / IA

### 4.1 Page Layout

Keep `/tasks/new` structure:

1) **Task draft form** (Goal/Disease/Country/Language) — unchanged.
2) **Clarification Chat** — new transcript UI replacing the old “Question/Answer” block.
3) **Next** panel (Upload / PubMed candidates) — keep existing behavior, gated by `taskForm` readiness.

### 4.2 Chat Transcript

Show bubbles:

- Assistant: questions returned as `question`.
- User: answers typed in composer.
- System: “Task form ready” / “Max rounds reached”.
- Error bubble: when an API call fails.

Auto-scroll to bottom when new messages arrive using `useScrollToBottom(messages.length)`.

## 5. State Machine

### 5.1 Persistent Store (existing)

- `interactionSessionId`: present after start
- `interactionRound`: increments based on backend response
- `taskForm`: set when backend returns `task_form`

### 5.2 Local UI State (new)

- `messages: ChatMessage[]` (UI transcript only)
- `composerText: string`
- `busy: boolean` (start/respond/upload)

### 5.3 Transitions

- `idle` → `starting`:
  - validate: `draft.goal` + `draft.disease` required
  - call `interactionStart`
  - append user/system message indicating the start (optional)
  - append assistant question bubble if `question` exists
- `awaiting_user` → `responding`:
  - validate: composer not empty
  - call `interactionRespond`
  - append user answer bubble
  - append assistant question bubble (if provided)
- `*` → `ready`:
  - when response includes `task_form`, call `setTaskForm(res.task_form)` and append system bubble

### 5.4 Edge Cases

- If `interactionRound >= 2` and still `taskForm == null`:
  - show system bubble “Max clarification rounds reached”
  - provide a **Restart clarification** action that resets store interaction state and clears transcript
- If backend returns both `question=null` and `task_form=null`:
  - show toast + error bubble
  - allow restart

## 6. Component Structure

Target minimal-but-scalable split:

- `TaskNewPage` remains the orchestration page.
- New component: `AgentClarificationChat`
  - props: draft (for building `user_input`), store state + setters, busy flag
  - internal: transcript rendering and composer
- Optional subcomponents (if needed): `ChatTranscript`, `ChatBubble`.

Styling: dedicated `.css` files using existing CSS variables from `globals.css`.

## 7. Error Handling

- Continue to use toast notifications (`useToastStore`) for visibility.
- Also append an in-context error bubble so the user understands which step failed.
- Avoid empty catches; prefer `ApiError.detail ?? err.message`.

## 8. Verification

After implementation:

- `npm run lint`
- `npx tsc --noEmit`
- `npm run build`

## 9. Future Enhancements (v2+)

- Optional dedicated route `/tasks/chat` once IA is validated.
- Backend-driven streaming events (SSE/WebSocket) if/when a contract exists.
- Task form “preview + confirm” step as a separate UI component (if product wants explicit confirmation).
