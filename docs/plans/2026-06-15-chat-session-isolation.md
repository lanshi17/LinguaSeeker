# Chat Session Isolation Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure that creating a new chat session (clicking the `+` button in the Conversations sidebar, XPath `/html/body/div[2]/div[2]/main/div/div/div/ul/li[1]`) yields a genuinely empty conversation, and that switching between sessions never shows messages, form state, or pipeline status that belong to a different session.

**Architecture:** The chat UI is built on `@ant-design/x-sdk`'s `useXChat` + `useXConversations`. `useXChat` stores messages inside a **module-level** `chatMessagesStoreHelper: Map<conversationKey, ChatMessagesStore>` (`node_modules/@ant-design/x-sdk/es/x-chat/store.js`). Stores are created on demand and **never destroyed**, so any session the user has visited still has its messages sitting in global memory. When the active key flips back to an old session, the cached store is reused and the stale messages render until the async `defaultMessages` replaces them. Two additional sources of cross-session bleed live in `ChatView.tsx`: `activeForm` / `activeFormSlots` and `pipelineStatus` are component-level state that survive session switches, and the SDK's `queueRequest` flow means a message dispatched during the create-and-switch transition can be picked up by the previous provider. The fix replaces the SDK's implicit `defaultMessages` hydration with an explicit effect that **clears → fetches → sets** messages on every session transition, moves per-session ephemeral UI state into a keyed map, and defensively destroys a store when a session is removed.

**Tech Stack:** Next.js 15 (App Router), React 18, TypeScript, `@ant-design/x-sdk`, `@ant-design/x`, Vitest, `@testing-library/react`, `msw`.

---

## Root-Cause Summary

Read the following files before starting — they contain every line that matters:

- `frontend/src/features/chat/components/ChatView.tsx` — main view, holds `activeForm`, `activeFormSlots`, `pipelineStatus`, `dispatchedActions`, `sessionLabels`, and wires `useXChat` + `useXConversations`.
- `frontend/src/features/chat/hooks/useChatSessions.ts` — creates sessions via the backend, manages the local-session list.
- `frontend/src/features/chat/utils/localSessions.ts` — localStorage persistence of the session list + remembered active session.
- `frontend/node_modules/@ant-design/x-sdk/es/x-chat/store.js` — the SDK's **global** `chatMessagesStoreHelper` and `ChatMessagesStore` class. Stores persist forever once created.
- `frontend/node_modules/@ant-design/x-sdk/es/x-chat/index.js` — `useXChat`. The `defaultMessages` prop is only read during store construction; subsequent changes don't trigger a reload.

Three interacting bugs:

1. **Global message cache, no cleanup.** `chatMessagesStoreHelper._chatMessagesStores` is a module-level `Map`. Once a session's store is created, it lives for the lifetime of the tab. Switching back to that session reuses the stale store; `defaultMessages` runs asynchronously and briefly renders the old messages before replacing them.
2. **Per-session UI state is actually component state.** `activeForm`, `activeFormSlots`, `pipelineStatus`, `dispatchedActions`, `sessionLabels` in `ChatView.tsx` are `useState` hooks. They never reset when `activeConversationKey` changes, so a form opened in session A keeps rendering after you switch to session B.
3. **`queueRequest` + stale provider.** In `handleSendMessage`, when a new session is created mid-send, the message is queued against the new `sessionKey` but `activeProvider` may still point at the old session's provider at the moment `onRequest` fires, causing the SSE stream to hit the wrong backend URL. The queued message's reply is then merged into whichever store is currently active.

The fix addresses all three in one pass.

---

## Files Changed (Overview)

| Action | Path | Why |
|---|---|---|
| **Modify** | `frontend/src/features/chat/components/ChatView.tsx` | Replace `defaultMessages` with explicit effect; move per-session ephemeral state into keyed maps; harden the create-then-send path. |
| **Create** | `frontend/src/features/chat/utils/messageStore.ts` | Thin wrapper around the SDK's global store helper for safe `clear` / `destroy` operations. Keeps the SDK import surface in one place. |
| **Create** | `frontend/tests/features/chat/sessionIsolation.test.tsx` | Vitest + MSW integration test that reproduces the bug (create session, send message, click `+`, verify empty; switch back, verify original messages still there). |
| **Modify** | `frontend/tests/features/chat/localSessions.test.ts` | Add a case for the new `clearLocalMessageStore` helper if we choose to expose it. |

No backend changes required — `GET /api/v1/chat/sessions/{session_id}/messages` already filters correctly by `session_id` (see `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py:160-176`).

---

### Task 1: Add an MSW-backed integration test that reproduces the bug

**Files:**
- Create: `frontend/tests/features/chat/sessionIsolation.test.tsx`
- Modify: `frontend/vitest.config.ts` (only if MSW setup hook is missing — check first)

**Why this first:** We need a failing test that captures the exact user-reported symptom before touching `ChatView.tsx`. If we can't reproduce the bug in a test, we can't be sure we fixed it.

**Step 1: Inspect the existing test harness**

Read:
- `frontend/tests/features/chat/localSessions.test.ts`
- `frontend/tests/features/chat/messageRequests.test.ts`
- `frontend/tests/features/chat/sse.test.ts`
- `frontend/vitest.config.ts`

Confirm whether MSW (or a fetch-mock) is already wired up. If tests use `vi.stubGlobal('fetch', ...)` instead, match that pattern — do not introduce a second mocking layer.

**Step 2: Write the failing test**

```ts
// frontend/tests/features/chat/sessionIsolation.test.tsx
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ChatView } from "@/features/chat";

vi.mock("@/lib/api/client", async () => {
  const actual = await import("axios");
  const instance = actual.default.create();
  return { apiClient: instance, default: instance };
});

const sessions = new Map<string, Array<{ message_id: string; role: "user" | "assistant"; content: string; chat_session_id: string; created_at: string }>>();
let nextSessionCounter = 1;

const server = setupServer(
  http.post("/api/v1/chat/sessions", async () => {
    const id = `sess-${nextSessionCounter++}`;
    sessions.set(id, []);
    return HttpResponse.json({
      chat_session_id: id,
      processing_run_id: null,
      created_at: new Date().toISOString(),
      message_count: 0,
    });
  }),
  http.post("/api/v1/chat/sessions/:id/messages", async ({ params, request }) => {
    const body = (await request.json()) as { content: string; role: string };
    const list = sessions.get(params.id as string) ?? [];
    list.push({
      message_id: `m-${list.length + 1}`,
      role: body.role as "user",
      content: body.content,
      chat_session_id: params.id as string,
      created_at: new Date().toISOString(),
    });
    return HttpResponse.json(list.at(-1));
  }),
  http.get("/api/v1/chat/sessions/:id/messages", ({ params }) => {
    return HttpResponse.json(sessions.get(params.id as string) ?? []);
  }),
  http.get("/api/v1/chat/sessions/:id/stream", function* ({ params }) {
    const target = params.id as string;
    if (!sessions.has(target)) {
      throw new HttpResponse(`data: ${JSON.stringify({ type: "error", message: "wrong session" })}\n\n`, { status: 500 });
    }
    yield `data: ${JSON.stringify({ type: "text", content: "reply-from-" })}\n\n`;
    yield `data: ${JSON.stringify({ type: "text", content: target })}\n\n`;
    yield `data: ${JSON.stringify({ type: "done" })}\n\n`;
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  sessions.clear();
  nextSessionCounter = 1;
  window.localStorage.clear();
});
afterAll(() => server.close());

it("new session via + button is empty even after previous session had messages", async () => {
  const user = userEvent.setup();
  render(<ChatView />);

  // Create first session and send a message.
  await user.click(await screen.findByRole("button", { name: /new conversation/i }));
  const input = await screen.findByPlaceholderText(/ask the cross evidence/i);
  await user.type(input, "hello from session one");
  await user.keyboard("{Enter}");

  await waitFor(() => {
    expect(screen.getByText(/reply-from-/i)).toBeInTheDocument();
  });

  // Click the + button again to create a SECOND session.
  await user.click(screen.getByRole("button", { name: /new conversation/i }));

  // The newly-active session MUST render no bubbles from the previous session.
  await waitFor(() => {
    expect(screen.queryByText(/hello from session one/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/reply-from-/i)).not.toBeInTheDocument();
  });
});

it("switching back to an old session re-hydrates its messages, not another session's", async () => {
  const user = userEvent.setup();
  render(<ChatView />);

  await user.click(await screen.findByRole("button", { name: /new conversation/i }));
  const input = await screen.findByPlaceholderText(/ask the cross evidence/i);
  await user.type(input, "session-A-content");
  await user.keyboard("{Enter}");
  await waitFor(() => expect(screen.getByText(/reply-from-sess-1/i)).toBeInTheDocument());

  // Create session B, send a different message.
  await user.click(screen.getByRole("button", { name: /new conversation/i }));
  const inputB = await screen.findByPlaceholderText(/ask the cross evidence/i);
  await user.type(inputB, "session-B-content");
  await user.keyboard("{Enter}");
  await waitFor(() => expect(screen.getByText(/reply-from-sess-2/i)).toBeInTheDocument());

  // Switch back to session A via the sidebar item.
  await user.click(await screen.findByText(/session-A-content/i, { selector: "span" }));

  await waitFor(() => {
    expect(screen.getByText(/session-A-content/i)).toBeInTheDocument();
    expect(screen.getByText(/reply-from-sess-1/i)).toBeInTheDocument();
    expect(screen.queryByText(/session-B-content/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/reply-from-sess-2/i)).not.toBeInTheDocument();
  });
});
```

> Note: selector text (`/new conversation/i`, sidebar labels) depends on the current `@ant-design/x` Conversations rendering. Inspect the actual DOM with Playwright or `screen.debug()` during the first run and adjust the role/name queries. The XPath the user reported (`/html/body/div[2]/div[2]/main/div/div/div/ul/li[1]`) targets the first `<li>` in the Conversations `<ul>` — which in `@ant-design/x` is the `+` (creation) item.

**Step 3: Run the test to confirm it fails**

```bash
cd frontend
npx vitest run tests/features/chat/sessionIsolation.test.tsx
```

Expected: both tests FAIL because either (a) messages from session 1 remain visible after creating session 2, or (b) switching back to session A shows session B's messages.

**Step 4: Commit the failing test (red)**

```bash
cd frontend
git add tests/features/chat/sessionIsolation.test.tsx
git commit -m "test(chat): add failing session-isolation integration test"
```

---

### Task 2: Add a safe wrapper around the SDK's global message store

**Files:**
- Create: `frontend/src/features/chat/utils/messageStore.ts`

**Why:** `chatMessagesStoreHelper` is a module-level global with no public `clear` or `destroy` API. We need a single place that encapsulates "reset the cached messages for this conversation key" so `ChatView` doesn't reach into SDK internals.

**Step 1: Write the helper**

```ts
// frontend/src/features/chat/utils/messageStore.ts
import { chatMessagesStoreHelper } from "@ant-design/x-sdk/es/x-chat/store";

/**
 * Drop the cached ChatMessagesStore for a single conversation key.
 *
 * The x-sdk keeps every conversation's messages in a module-level Map
 * for the lifetime of the tab. When we delete or reset a session we
 * must also drop the cached store, otherwise the next visit to the
 * same key rehydrates stale messages before `defaultMessages` resolves.
 */
export function clearCachedMessages(conversationKey: string | undefined): void {
  if (!conversationKey) return;
  const store = chatMessagesStoreHelper.get(conversationKey);
  if (!store) return;
  // Best-effort: empty the in-place snapshot so any still-subscribed
  // consumers render an empty list synchronously, then drop the entry.
  if (typeof store.setMessages === "function") {
    store.setMessages([]);
  }
  if (typeof store.destroy === "function") {
    store.destroy();
  }
  chatMessagesStoreHelper.delete(conversationKey);
}

/**
 * Clear every cached conversation store. Used in tests and during
 * hard navigation events (e.g. full logout) where the tab survives
 * but user state must not.
 */
export function clearAllCachedMessages(): void {
  // chatMessagesStoreHelper exposes a .delete per key only — iterate
  // a snapshot of keys so we don't mutate the map while walking it.
  const keys: string[] = [];
  // The helper's internal map is `_chatMessagesStores`. We iterate
  // via the public get() to avoid depending on the private field.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const internal = (chatMessagesStoreHelper as any)._chatMessagesStores as
    | Map<string, unknown>
    | undefined;
  if (internal) {
    for (const k of internal.keys()) keys.push(k);
  }
  for (const k of keys) clearCachedMessages(k);
}
```

**Step 2: Unit-test the helper**

```ts
// frontend/tests/features/chat/messageStore.test.ts
import { describe, expect, it } from "vitest";
import { chatMessagesStoreHelper } from "@ant-design/x-sdk/es/x-chat/store";
import { clearAllCachedMessages, clearCachedMessages } from "@/features/chat/utils/messageStore";

describe("clearCachedMessages", () => {
  it("empties and removes a specific store", () => {
    const store = new (class {
      destroyed = false;
      messages = [{ id: "1" }, { id: "2" }];
      setMessages(m: unknown[]) { this.messages = m; }
      destroy() { this.destroyed = true; }
    })();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (chatMessagesStoreHelper as any)._chatMessagesStores.set("k1", store);

    clearCachedMessages("k1");

    expect(store.destroyed).toBe(true);
    expect(store.messages).toEqual([]);
    expect(chatMessagesStoreHelper.get("k1")).toBeUndefined();
  });

  it("is a no-op for unknown keys", () => {
    expect(() => clearCachedMessages("nope")).not.toThrow();
    expect(() => clearCachedMessages(undefined)).not.toThrow();
  });

  it("clearAllCachedMessages wipes every entry", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const map = (chatMessagesStoreHelper as any)._chatMessagesStores as Map<string, unknown>;
    map.set("a", { setMessages: () => {}, destroy: () => {} });
    map.set("b", { setMessages: () => {}, destroy: () => {} });

    clearAllCachedMessages();

    expect(map.size).toBe(0);
  });
});
```

**Step 3: Run**

```bash
cd frontend
npx vitest run tests/features/chat/messageStore.test.ts
```

Expected: all three cases PASS.

**Step 4: Commit**

```bash
cd frontend
git add src/features/chat/utils/messageStore.ts tests/features/chat/messageStore.test.ts
git commit -m "feat(chat): add helper to drop x-sdk cached message stores"
```

---

### Task 3: Replace `defaultMessages` with an explicit load-on-switch effect

**Files:**
- Modify: `frontend/src/features/chat/components/ChatView.tsx:301-324` (the `useXChat` call and surrounding `loadDefaultMessages` callback)

**Why:** `defaultMessages` only fires when the SDK's `ChatMessagesStore` is first constructed. Because the SDK caches stores globally, visiting a session for the second time does NOT re-run `defaultMessages`, so stale messages render. An explicit `useEffect` keyed on `activeConversationKey` runs on every switch, giving us a deterministic "clear → fetch → set" sequence.

**Step 1: Extend the failing test (if not already covered)**

The Task 1 test already asserts "switching back to session A shows A's messages and hides B's". That assertion currently fails because the cached store for A re-renders stale bubbles before any refetch.

**Step 2: Edit `ChatView.tsx`**

Locate the block around line 301–324:

```ts
const loadDefaultMessages = useCallback(
  async (info?: { conversationKey?: string }) => {
    if (!info?.conversationKey) return [];
    const history = await listMessages(info.conversationKey);
    return toXChatDefaultMessages(history);
  },
  [],
);

const {
  messages,
  onRequest,
  isRequesting,
  abort,
  queueRequest,
} = useXChat({
  provider: activeProvider,
  conversationKey: activeConversationKey,
  defaultMessages: loadDefaultMessages,
});
```

Replace it with:

```ts
const {
  messages,
  onRequest,
  isRequesting,
  abort,
  setMessages,
} = useXChat({
  provider: activeProvider,
  conversationKey: activeConversationKey,
  defaultMessages: async () => [], // always start empty; hydration happens in the effect below
});

// Explicit, deterministic message hydration on session switch.
// Runs on every `activeConversationKey` change — including the *second*
// time we visit a session, where the SDK's cached store would otherwise
// re-render stale bubbles until its async defaultMessages resolved.
const [isHydrating, setIsHydrating] = useState(false);
useEffect(() => {
  let cancelled = false;
  if (!activeConversationKey) {
    setMessages([]);
    return;
  }

  // Synchronously empty the visible list so no previous-session bubble
  // can flash while the network call is in flight.
  setMessages([]);
  clearCachedMessages(activeConversationKey);
  setIsHydrating(true);

  listMessages(activeConversationKey)
    .then((history) => {
      if (cancelled) return;
      setMessages(toXChatDefaultMessages(history));
    })
    .catch(() => {
      if (cancelled) return;
      setMessages([]);
    })
    .finally(() => {
      if (!cancelled) setIsHydrating(false);
    });

  return () => {
    cancelled = true;
  };
}, [activeConversationKey, setMessages]);
```

Import the helper at the top of the file:

```ts
import { clearCachedMessages } from "../utils/messageStore";
```

Also add `setMessages` to the destructured return of `useXChat` (shown above).

**Step 3: Run the test**

```bash
cd frontend
npx vitest run tests/features/chat/sessionIsolation.test.tsx
```

Expected: the first test (new session is empty) now PASSES. The second test (switching back shows correct messages) may still fail — we haven't addressed the form / pipeline-state bleed yet.

**Step 4: Run the broader chat suite to catch regressions**

```bash
cd frontend
npx vitest run tests/features/chat
```

Expected: no regressions. If `messageHistory.test.ts` or `messageRequests.test.ts` break, update them — they likely mocked `defaultMessages` directly and now need to mock `listMessages` instead (which they already do in most cases).

**Step 5: Commit**

```bash
cd frontend
git add src/features/chat/components/ChatView.tsx
git commit -m "fix(chat): hydrate messages via explicit effect instead of defaultMessages"
```

---

### Task 4: Move per-session ephemeral UI state into a keyed map

**Files:**
- Modify: `frontend/src/features/chat/components/ChatView.tsx`

**Why:** `activeForm`, `activeFormSlots`, `pipelineStatus`, `dispatchedActions`, and `sessionLabels` are component-level `useState`. They survive session switches, so a pipeline form opened in session A keeps rendering when you switch to B. They need to be keyed by `session_id`.

**Step 1: Add a failing assertion to the isolation test**

Append to `frontend/tests/features/chat/sessionIsolation.test.tsx`:

```ts
it("pipeline form state opened in session A does not render in session B", async () => {
  const user = userEvent.setup();
  render(<ChatView />);

  // Create session A.
  await user.click(await screen.findByRole("button", { name: /new conversation/i }));

  // Trigger the embedded pipeline form by sending the start-pipeline intent.
  // (ChatMarkdown action chips dispatch this; if none are visible, send the
  // suggestion chip whose content maps to the pipeline start intent.)
  const pipelineChip = await screen.findByText(/run the pipeline/i);
  await user.click(pipelineChip);

  // Expect the form to appear.
  expect(await screen.findByRole("form")).toBeInTheDocument();

  // Create session B via the + button.
  await user.click(screen.getByRole("button", { name: /new conversation/i }));

  // Session B must NOT render session A's form.
  await waitFor(() => {
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
  });
});
```

Run:

```bash
npx vitest run tests/features/chat/sessionIsolation.test.tsx -t "pipeline form state"
```

Expected: FAIL — the form persists across the session switch.

**Step 2: Refactor state in `ChatView.tsx`**

Replace the individual `useState` declarations (around lines 327–341):

```ts
const [activeForm, setActiveForm] = useState<ChatActionIntent | null>(null);
const [activeFormSlots, setActiveFormSlots] = useState<ChatAction["slots"] | null>(null);
const [dispatchedActions, setDispatchedActions] = useState<Set<string>>(() => new Set());
const [pipelineStatus, setPipelineStatus] = useState<{
  runId: string;
  status: string;
  phases?: Record<string, { status: string; duration_seconds?: number | null }>;
} | null>(null);
```

With per-session keyed state:

```ts
interface PerSessionUIState {
  activeForm: ChatActionIntent | null;
  activeFormSlots: ChatAction["slots"] | null;
  dispatchedActions: Set<string>;
  pipelineStatus: {
    runId: string;
    status: string;
    phases?: Record<string, { status: string; duration_seconds?: number | null }>;
  } | null;
}

const EMPTY_SESSION_UI: PerSessionUIState = {
  activeForm: null,
  activeFormSlots: null,
  dispatchedActions: new Set<string>(),
  pipelineStatus: null,
};

const [sessionUI, setSessionUI] = useState<Record<string, PerSessionUIState>>({});
const [sessionLabels, setSessionLabels] = useState<Record<string, string>>({});

const activeUI: PerSessionUIState = activeConversationKey
  ? (sessionUI[activeConversationKey] ?? EMPTY_SESSION_UI)
  : EMPTY_SESSION_UI;
const { activeForm, activeFormSlots, dispatchedActions, pipelineStatus } = activeUI;

const updateActiveUI = useCallback(
  (updater: (prev: PerSessionUIState) => PerSessionUIState) => {
    if (!activeConversationKey) return;
    const key = activeConversationKey;
    setSessionUI((prev) => ({
      ...prev,
      [key]: updater(prev[key] ?? EMPTY_SESSION_UI),
    }));
  },
  [activeConversationKey],
);

const setActiveForm = useCallback(
  (intent: ChatActionIntent | null) =>
    updateActiveUI((p) => ({ ...p, activeForm: intent })),
  [updateActiveUI],
);
const setActiveFormSlots = useCallback(
  (slots: ChatAction["slots"] | null) =>
    updateActiveUI((p) => ({ ...p, activeFormSlots: slots })),
  [updateActiveUI],
);
const setPipelineStatus = useCallback(
  (
    status: PerSessionUIState["pipelineStatus"] | ((prev: PerSessionUIState["pipelineStatus"]) => PerSessionUIState["pipelineStatus"]),
  ) =>
    updateActiveUI((p) => ({
      ...p,
      pipelineStatus:
        typeof status === "function" ? status(p.pipelineStatus) : status,
    })),
  [updateActiveUI],
);
const setDispatchedActions = useCallback(
  (
    next: Set<string> | ((prev: Set<string>) => Set<string>),
  ) =>
    updateActiveUI((p) => ({
      ...p,
      dispatchedActions:
        typeof next === "function" ? next(p.dispatchedActions) : next,
    })),
  [updateActiveUI],
);
```

`sessionLabels` is intentionally **kept as a cross-session map** because the sidebar renders labels for every session simultaneously — it cannot be keyed to the active session.

**Step 3: Fix every `setPipelineStatus({...})`, `setActiveForm(null)`, etc. call site**

Grep for the five setters and confirm each one goes through the new `updateActiveUI` wrappers. Most call sites don't need to change shape — the wrappers above accept the same arguments the raw setters did.

Two call sites to watch carefully:
- `setPipelineStatus({ runId, status: response.data.status })` inside `handlePipelineSubmit` — keep as-is, the wrapper handles the object form.
- `setDispatchedActions((prev) => { ... const next = new Set(prev); next.add(key); return next; })` inside `handleDispatchAction` — keep as-is, the updater-function form is supported.

**Step 4: Run the tests**

```bash
npx vitest run tests/features/chat
```

Expected: the new pipeline-form test PASSES; all other chat tests still PASS.

**Step 5: Commit**

```bash
cd frontend
git add src/features/chat/components/ChatView.tsx tests/features/chat/sessionIsolation.test.tsx
git commit -m "fix(chat): key per-session UI state by conversation to prevent bleed"
```

---

### Task 5: Harden the "create new session and immediately send" path

**Files:**
- Modify: `frontend/src/features/chat/components/ChatView.tsx` (the `handleSendMessage` function, around lines 412–447)

**Why:** When `handleSendMessage` creates a new session mid-flight, the current code queues the request against the new `sessionKey` via `queueRequest`. But the SDK's `processMessageQueue` may fire before `activeProvider` has been re-derived from the new `activeConversationKey`, causing the SSE stream to hit the previous session's URL. The fix is to wait for the provider switch to settle before dispatching.

**Step 1: Add a test for the race**

Append to `frontend/tests/features/chat/sessionIsolation.test.tsx`:

```ts
it("sending a message immediately after clicking + targets the new session only", async () => {
  const user = userEvent.setup();
  render(<ChatView />);

  // Create session A and send a message so a provider exists.
  await user.click(await screen.findByRole("button", { name: /new conversation/i }));
  let input = await screen.findByPlaceholderText(/ask the cross evidence/i);
  await user.type(input, "A-message");
  await user.keyboard("{Enter}");
  await waitFor(() => expect(screen.getByText(/reply-from-sess-1/i)).toBeInTheDocument());

  // Click + and IMMEDIATELY type+send in the fresh session.
  await user.click(screen.getByRole("button", { name: /new conversation/i }));
  input = await screen.findByPlaceholderText(/ask the cross evidence/i);
  await user.type(input, "B-message");
  await user.keyboard("{Enter}");

  // The backend stream handler (in our MSW setup) embeds the target
  // session ID in the reply. Verify only the new session's reply appears.
  await waitFor(() => expect(screen.getByText(/reply-from-sess-2/i)).toBeInTheDocument());
  expect(screen.queryByText(/reply-from-sess-1/i)).not.toBeInTheDocument();
  // And the new session's user bubble is the only user bubble visible.
  expect(screen.getByText(/B-message/i)).toBeInTheDocument();
  expect(screen.queryByText(/A-message/i)).not.toBeInTheDocument();
});
```

Run:

```bash
npx vitest run tests/features/chat/sessionIsolation.test.tsx -t "sending a message immediately"
```

Expected: FAIL — the reply from sess-1 leaks into the new session, or the message is lost.

**Step 2: Replace `handleSendMessage`**

Locate lines 412–447 and replace with:

```ts
const handleSendMessage = useCallback(
  async (content: string) => {
    const trimmed = content.trim();
    if (!trimmed) return;

    setActiveForm(null);
    setActiveFormSlots(null);

    try {
      // If we don't have a session yet, create one and WAIT for the
      // activeConversationKey to settle before dispatching.
      let sessionKey = activeConversationKey;
      if (!sessionKey) {
        sessionKey = await createAndActivateSession();
        // createAndActivateSession() calls handleActiveConversationChange
        // which triggers a React state update. The re-render updates
        // `activeProvider`. Defer dispatch to the next microtask so the
        // derived provider is the new session's provider.
        await new Promise<void>((resolve) => {
          // Double-rAF flushes both React state and the SDK's effect.
          requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
        });
      }

      await sendChatMessage(sessionKey, trimmed);
      captureFirstMessageLabel(sessionKey, trimmed);
      onRequest({ messages: [{ role: "user" as const, content: trimmed }] });
    } catch {
      antdMessage.error("Failed to send message");
    }
  },
  [
    activeConversationKey,
    captureFirstMessageLabel,
    createAndActivateSession,
    onRequest,
    setActiveForm,
    setActiveFormSlots,
  ],
);
```

Key differences from the previous implementation:
- **No `ensureActiveSession` + `queueRequest` dance.** We resolve the session synchronously, then defer the dispatch until the provider has caught up.
- **No `if (sessionKey === activeConversationKey)` branch.** After the await, the provider is always correct, so we always call `onRequest` directly.
- **`queueRequest` is no longer imported** — remove it from the `useXChat` destructuring at the top of Task 3's edit if it's still there.

**Step 3: Run the test**

```bash
npx vitest run tests/features/chat/sessionIsolation.test.tsx
```

Expected: all four tests PASS.

**Step 4: Run the entire chat suite**

```bash
npx vitest run tests/features/chat
```

Expected: all tests PASS.

**Step 5: Commit**

```bash
cd frontend
git add src/features/chat/components/ChatView.tsx tests/features/chat/sessionIsolation.test.tsx
git commit -m "fix(chat): wait for provider switch before dispatching queued send"
```

---

### Task 6: Clean up the cached store when a session is deleted

**Files:**
- Modify: `frontend/src/features/chat/components/ChatView.tsx` (the `handleDeleteSession` callback around line 673)

**Why:** When the user clicks Delete in the Conversations menu, the SDK's cached store for that key remains in `chatMessagesStoreHelper`. If the user later navigates directly to `/chat/{id}`, the stale store rehydrates. Not a huge issue in practice (the backend re-fetches on mount), but worth cleaning.

**Step 1: Edit `handleDeleteSession`**

Find the `onOk` branch inside `handleDeleteSession` and add a `clearCachedMessages` call at the top:

```ts
onOk: () => {
  clearCachedMessages(sessionId);
  removeSession(sessionId);
  removeConversation(sessionId);
  // ... existing active-key fallback logic unchanged
},
```

**Step 2: Run the suite**

```bash
npx vitest run tests/features/chat
```

Expected: all PASS.

**Step 3: Commit**

```bash
cd frontend
git add src/features/chat/components/ChatView.tsx
git commit -m "fix(chat): drop cached message store when deleting a session"
```

---

### Task 7: Manual verification in the browser

**Files:** none — verification only.

**Step 1: Start the stack**

```bash
cd frontend && npm run dev
# in another terminal
cd backend && uv run uvicorn app.main:app --reload
```

**Step 2: Walk the scenario the user reported**

1. Open `http://localhost:3000/chat`.
2. Click the `+` (first `<li>` in the Conversations list) to create session A.
3. Send a message; confirm the reply appears.
4. Click `+` again to create session B.
5. **Verify:** session B's bubble area shows only the Welcome block — no messages from A.
6. Send a message in B; confirm its reply appears, and A's messages do NOT appear.
7. Click session A in the sidebar.
8. **Verify:** session A's messages re-appear, and B's messages are hidden.
9. Refresh the page while on session A.
10. **Verify:** session A's messages rehydrate correctly after reload.

**Step 3: Update `progress.txt`**

Append a line:

```
[2026-06-15] [fix chat session message bleed-through across create/switch] [done]
```

**Step 4: Final commit (only if you updated `progress.txt`)**

```bash
cd frontend
git add ../progress.txt
git commit -m "docs: log chat session isolation fix in progress.txt"
```

---

## Out of Scope

- **Backend changes.** `list_messages` already filters by `session_id` correctly (see `chat_service.py:160-176`). If manual testing reveals cross-session messages in the raw JSON response, stop — that's a separate bug and needs its own plan.
- **Refactoring `useXConversations`.** The SDK's conversation list manager is fine; the issue is the message store, not the conversation list.
- **Persisting `sessionUI` to localStorage.** Form state is ephemeral by design.
