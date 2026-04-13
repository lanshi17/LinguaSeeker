# Frontend Agent Clarification Chat UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade `/tasks/new` agent clarification into a chat-style transcript + composer UI while preserving existing backend API contracts and task flow.

**Architecture:** Keep `TaskNewPage` as the orchestration page; introduce a small chat UI component that renders a transcript and drives `interactionStart/interactionRespond`, persisting only the official outputs (`session_id`, `round`, `task_form`) via the existing Zustand store.

**Tech Stack:** React 19 + TypeScript, React Router DOM, Zustand, CSS (globals.css variables), existing API layer (`src/services/api.ts`).

---

## Task 1: Create chat UI types + styling

**Files:**
- Create: `src/components/chat/agent-clarification-chat.css`

**Step 1: Add minimal CSS tokens**

Create styles for:

- `.chat-shell` (panel-like container)
- `.chat-transcript` (scroll container)
- `.chat-bubble` with variants: `data-role="assistant" | "user" | "system" | "error"`
- `.chat-composer` (textarea + send button)

**Step 2: Verify CSS is picked up**

Run: `npm run build`
Expected: build succeeds.

---

## Task 2: Add AgentClarificationChat component

**Files:**
- Create: `src/components/chat/agent-clarification-chat.tsx`
- Create: `src/components/chat/types.ts`

**Step 1: Define transcript types**

In `types.ts`:

```ts
export type ChatRole = 'assistant' | 'user' | 'system' | 'error';

export type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  createdAtMs: number;
};
```

**Step 2: Implement component skeleton**

Requirements:
- Renders transcript list with role-based styling
- Uses `useScrollToBottom(messages.length)`
- Provides composer (textarea) + Send button
- Exposes callbacks for `onStart`, `onSend`, `onRestart` (implemented in page or inside component)

**Step 3: Type-check**

Run: `npx tsc --noEmit`
Expected: no type errors.

---

## Task 3: Integrate chat into TaskNewPage (replace Q/A block)

**Files:**
- Modify: `src/pages/tasks/task-new-page.tsx`

**Step 1: Replace “Question + textarea” UI with transcript + composer**

Implementation notes:
- Keep existing draft form fields and `buildUserInput(draft)` behavior.
- On start:
  - Validate required fields
  - Call `interactionStart`
  - Append assistant question bubble if `res.question`
  - If `res.task_form`, call `setTaskForm(res.task_form)` and append system message.
- On respond:
  - Append user message (answer)
  - Call `interactionRespond`
  - Append assistant question bubble if present
  - If `res.task_form`, set store + system message.

**Step 2: Add “Restart clarification”**

Reset:
- `setInteraction(null, 0)`
- `setTaskForm(null)`
- Clear local transcript state

Show restart CTA when:
- `interactionRound >= 2 && !taskForm`
- or when an unrecoverable empty response is returned.

**Step 3: Preserve Next panel behavior**

Do not regress:
- upload validation (`validateUploadFiles`)
- navigation to `/tasks/pubmed/candidates`

**Step 4: Lint + typecheck**

Run:
- `npm run lint`
- `npx tsc --noEmit`

Expected: both succeed.

---

## Task 4: Verification build

**Step 1: Production build**

Run: `npm run build`
Expected: build succeeds.

---

## Notes / Constraints

- Do NOT introduce SSE/WebSocket in v1.
- Do NOT use `any`, `as any`, `@ts-ignore`.
- Do NOT commit changes unless explicitly requested.
