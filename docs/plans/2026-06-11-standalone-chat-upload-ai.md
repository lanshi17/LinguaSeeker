# Standalone Chat Upload AI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `/chat` so users can create a chat session before any pipeline exists, keep the visible session list in browser local storage, open the Upload PDF prompt directly in local-upload mode, and exchange real streamed AI replies.

**Architecture:** Keep the frontend as the page orchestrator and the chat feature as the vertical UI slice. Backend Phase 4 remains the source of truth for message history and LLM streaming, while browser `localStorage` stores only the standalone session list and active session ID for `/chat`. The backend allows `chat_sessions.processing_run_id` to be nullable so chat is not forced to create a pipeline placeholder.

**Tech Stack:** Next.js App Router, React 18, TypeScript, `@ant-design/x`, `@ant-design/x-sdk`, React Query, FastAPI, Pydantic, SQLAlchemy async, Alembic, pytest, Node `node:test`.

---

**Status:** planned
**Created:** 2026-06-11
**Completed:** N/A
**PR:** N/A

## Progress Recording Rule

Treat each `Task N` below as a project task node. After finishing each task's verification and before its commit, append one line to root `progress.txt`:

```text
[2026-06-11] [Standalone chat upload AI - Task N: <task title>] [done]
```

Include `progress.txt` in that task's commit. The explicit `git add` snippets below show the feature files; add `progress.txt` to each one after writing the task-specific progress line.

## Context And Decisions

- Current blocking warning is in `frontend/src/features/chat/components/ChatView.tsx`: `Start a pipeline first to create a chat session.`
- Current backend `ChatSession.processing_run_id` is non-null and has a foreign key to `processing_runs`, which forces chat creation to depend on a pipeline run.
- The existing chat provider opens `/api/v1/chat/sessions/{sessionId}/stream`, but `transformMessage()` does not accumulate streamed chunks, so the UI can show an empty assistant bubble.
- `POST /api/v1/chat/sessions/{sessionId}/messages` currently generates and persists an assistant reply, then the frontend opens an SSE stream that generates another reply. The implementation must make the POST persist-only by default and use SSE for real AI responses.
- `frontend/src/features/chat/hooks/useChatMessages.ts` is currently unused, but it is exported and calls `appendMessage()`. The implementation must keep that path valid or delete the export. This plan keeps it valid by adding `role` and `auto_reply: false` to the request body.
- Old-version code was checked. It has useful upload validation patterns in `backend/.old_version/src/api/routes/task.py` and prior UI upload flow notes in `backend/.old_version/update_task_new.patch`, but no directly reusable Ant Design X chat session implementation.

## Success Criteria

- Clicking "New session" on `/chat` creates a usable session without a pipeline run.
- Reloading `/chat` restores standalone session cards and active session from `localStorage`.
- Typing a message with no active session creates a session first, persists the user message, and streams a real assistant answer through `REASONING_LLM_MODEL`.
- Refreshing `/chat/[sessionId]` loads persisted backend message history.
- Clicking the Ant Design X prompt with label `Upload PDF` opens the pipeline form with local upload selected by default.
- Uploading a PDF from the prompt starts `/api/v1/pipeline/run`, shows the inline status card, and does not navigate away.
- The targeted prompt area no longer looks cramped in the dashboard shell on desktop or mobile.
- No bare `-> dict` return types are introduced in backend Python.

## Task 1: Backend Standalone Chat Sessions

**Files:**
- Modify: `backend/src/dao/postgresql/models.py:557-583`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py:116-125`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py:44-76`
- Modify: `backend/src/api/v1/chat.py:20-45`
- Create: `database/migrations/versions/2026-06-11_allow_standalone_chat_sessions.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py`
- Test: `backend/tests/api/test_chat_api.py`

**Step 1: Write failing service test**

Add this test inside `TestChatService` in `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py`:

```python
async def test_create_standalone_session(self, db_session: AsyncSession) -> None:
    """Creates a chat session that is not bound to a pipeline run."""
    service = ChatService(db_session)

    session = await service.create_session(processing_run_id=None, user_id=None)

    assert session.processing_run_id is None
    assert session.message_count == 0
```

**Step 2: Write failing API test**

Add this test to `backend/tests/api/test_chat_api.py`:

```python
@pytest.mark.asyncio
async def test_create_standalone_session_api(async_client: AsyncClient):
    """POST /api/v1/chat/sessions accepts an empty body for standalone chat."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatSessionResponse

    session_id = uuid4()
    mock_response = ChatSessionResponse(
        chat_session_id=session_id,
        processing_run_id=None,
        user_id=None,
        created_at="2026-06-11T00:00:00Z",
        message_count=0,
    )

    with patch("src.api.v1.chat.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.create_session = AsyncMock(return_value=mock_response)
        mock_factory.return_value.create_chat_service.return_value = mock_service

        response = await async_client.post("/api/v1/chat/sessions", json={})

    assert response.status_code == 200
    assert response.json()["chat_session_id"] == str(session_id)
    assert response.json()["processing_run_id"] is None
    mock_service.create_session.assert_awaited_once_with(
        processing_run_id=None,
        user_id=None,
    )
```

**Step 3: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py::TestChatService::test_create_standalone_session tests/api/test_chat_api.py::test_create_standalone_session_api -v
```

Expected: FAIL because `processing_run_id` is required.

**Step 4: Add migration**

Create `database/migrations/versions/2026-06-11_allow_standalone_chat_sessions.py`:

```python
"""Allow standalone chat sessions without a processing run.

Revision ID: 2026_06_11_allow_standalone_chat_sessions
Revises: add_created_at_search_idx
Create Date: 2026-06-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2026_06_11_allow_standalone_chat_sessions"
down_revision = "add_created_at_search_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "chat_sessions",
        "processing_run_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM chat_messages WHERE chat_session_id IN (SELECT chat_session_id FROM chat_sessions WHERE processing_run_id IS NULL)"))
    op.execute(sa.text("DELETE FROM chat_sessions WHERE processing_run_id IS NULL"))
    op.alter_column(
        "chat_sessions",
        "processing_run_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
```

Before implementation, confirm the actual Alembic head with:

```bash
uv run --project backend alembic -c database/alembic.ini heads
```

Expected current output: `add_created_at_search_idx (head)`. If the head changes before implementation, set `down_revision` to the reported revision ID.

**Step 5: Update ORM and contracts**

In `backend/src/dao/postgresql/models.py`, change:

```python
processing_run_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("processing_runs.processing_run_id"),
    nullable=True,
)
```

In `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`, change:

```python
class ChatSessionResponse(BaseModel):
    """API response for a chat session."""

    chat_session_id: UUID
    processing_run_id: UUID | None
    user_id: UUID | None
    created_at: datetime
    message_count: int = 0
```

In `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py`, change the signature:

```python
async def create_session(
    self,
    *,
    processing_run_id: UUID | None,
    user_id: UUID | None = None,
) -> ChatSessionResponse:
    """Create a new chat session, optionally bound to a processing run."""
    session = ChatSession(
        processing_run_id=processing_run_id,
        user_id=user_id,
    )
```

In `backend/src/api/v1/chat.py`, change:

```python
class CreateSessionRequest(BaseModel):
    processing_run_id: UUID | None = None
    user_id: UUID | None = None
```

Keep `GET /sessions/{processing_run_id}` unchanged for existing pipeline-bound session lists.

**Step 6: Run backend focused tests**

Run:

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py::TestChatService::test_create_standalone_session tests/api/test_chat_api.py::test_create_standalone_session_api -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/src/dao/postgresql/models.py backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py backend/src/api/v1/chat.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py backend/tests/api/test_chat_api.py database/migrations/versions/2026-06-11_allow_standalone_chat_sessions.py
git commit -m "feat: allow standalone chat sessions"
```

## Task 2: Backend Persist-Only Chat POST

**Files:**
- Modify: `backend/src/api/v1/chat.py:26-88`
- Test: `backend/tests/api/test_chat_api.py`

**Step 1: Write failing test for default persist-only behavior**

Add this test:

```python
@pytest.mark.asyncio
async def test_append_message_does_not_generate_reply_by_default(async_client: AsyncClient):
    """Message append is persist-only unless auto_reply is explicitly requested."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatMessageResponse

    session_id = uuid4()
    msg_id = uuid4()
    mock_response = ChatMessageResponse(
        message_id=msg_id,
        chat_session_id=session_id,
        role="user",
        content="What is BRCA1?",
        evidence_id=None,
        entity_id=None,
        created_at="2026-06-11T00:00:00Z",
    )

    with patch("src.api.v1.chat.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.append_message = AsyncMock(return_value=mock_response)
        mock_service.generate_reply = AsyncMock(return_value="BRCA1 answer")
        mock_factory.return_value.create_chat_service.return_value = mock_service

        response = await async_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"role": "user", "content": "What is BRCA1?"},
        )

    assert response.status_code == 200
    mock_service.generate_reply.assert_not_called()
```

**Step 2: Write compatibility test for explicit auto reply**

Add this test:

```python
@pytest.mark.asyncio
async def test_append_message_can_generate_reply_when_requested(async_client: AsyncClient):
    """Legacy non-streaming callers can opt into generated assistant replies."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatMessageResponse

    session_id = uuid4()
    user_msg_id = uuid4()
    assistant_msg_id = uuid4()
    user_response = ChatMessageResponse(
        message_id=user_msg_id,
        chat_session_id=session_id,
        role="user",
        content="What is BRCA1?",
        evidence_id=None,
        entity_id=None,
        created_at="2026-06-11T00:00:00Z",
    )
    assistant_response = ChatMessageResponse(
        message_id=assistant_msg_id,
        chat_session_id=session_id,
        role="assistant",
        content="BRCA1 answer",
        evidence_id=None,
        entity_id=None,
        created_at="2026-06-11T00:00:01Z",
    )

    with patch("src.api.v1.chat.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.append_message = AsyncMock(side_effect=[user_response, assistant_response])
        mock_service.generate_reply = AsyncMock(return_value="BRCA1 answer")
        mock_factory.return_value.create_chat_service.return_value = mock_service

        response = await async_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"role": "user", "content": "What is BRCA1?", "auto_reply": True},
        )

    assert response.status_code == 200
    mock_service.generate_reply.assert_awaited_once()
    assert mock_service.append_message.await_count == 2
```

**Step 3: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/api/test_chat_api.py::test_append_message_does_not_generate_reply_by_default tests/api/test_chat_api.py::test_append_message_can_generate_reply_when_requested -v
```

Expected: first test FAILS because reply generation currently happens by default.

**Step 4: Implement request flag**

In `backend/src/api/v1/chat.py`, update `AppendMessageRequest`:

```python
class AppendMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    evidence_id: UUID | None = None
    entity_id: UUID | None = None
    auto_reply: bool = False
```

Then update the route condition:

```python
if body.role == "user" and body.auto_reply:
    reply = await service.generate_reply(
        session_id=session_id,
        user_message=body.content,
        evidence_id=body.evidence_id,
    )
    if reply:
        await service.append_message(
            session_id=session_id,
            role="assistant",
            content=reply,
            evidence_id=body.evidence_id,
            entity_id=body.entity_id,
        )
```

**Step 5: Run tests**

```bash
cd backend
uv run pytest tests/api/test_chat_api.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/api/v1/chat.py backend/tests/api/test_chat_api.py
git commit -m "fix: make chat message append persist only by default"
```

## Task 3: Frontend Local Session Utilities

**Files:**
- Modify: `frontend/src/features/chat/types/chat.ts`
- Create: `frontend/src/features/chat/utils/localSessions.ts`
- Create: `frontend/src/features/chat/utils/messageHistory.ts`
- Modify: `frontend/tsconfig.test.json`
- Test: `frontend/tests/features/chat/localSessions.test.ts`
- Test: `frontend/tests/features/chat/messageHistory.test.ts`

**Step 1: Write failing tests**

Create `frontend/tests/features/chat/localSessions.test.ts`:

```typescript
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  ACTIVE_CHAT_SESSION_KEY,
  CHAT_SESSIONS_KEY,
  loadLocalChatSessions,
  rememberActiveChatSession,
  upsertLocalChatSession,
} from "../../../src/features/chat/utils/localSessions";
import type { ChatSessionResponse } from "../../../src/features/chat/types/chat";

class MemoryStorage implements Storage {
  private values = new Map<string, string>();
  get length(): number {
    return this.values.size;
  }
  clear(): void {
    this.values.clear();
  }
  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }
  key(index: number): string | null {
    return Array.from(this.values.keys())[index] ?? null;
  }
  removeItem(key: string): void {
    this.values.delete(key);
  }
  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

function session(id: string): ChatSessionResponse {
  return {
    session_id: id,
    processing_run_id: null,
    created_at: "2026-06-11T00:00:00Z",
    message_count: 0,
  };
}

describe("local chat sessions", () => {
  it("loads an empty list when localStorage has invalid JSON", () => {
    const storage = new MemoryStorage();
    storage.setItem(CHAT_SESSIONS_KEY, "{not-json");

    assert.deepEqual(loadLocalChatSessions(storage), []);
  });

  it("upserts newest session first without duplicates", () => {
    const storage = new MemoryStorage();

    upsertLocalChatSession(storage, session("a"));
    upsertLocalChatSession(storage, session("b"));
    upsertLocalChatSession(storage, { ...session("a"), message_count: 2 });

    const saved = loadLocalChatSessions(storage);
    assert.deepEqual(saved.map((item) => item.session_id), ["a", "b"]);
    assert.equal(saved[0].message_count, 2);
  });

  it("remembers the active session id", () => {
    const storage = new MemoryStorage();

    rememberActiveChatSession(storage, "session-1");

    assert.equal(storage.getItem(ACTIVE_CHAT_SESSION_KEY), "session-1");
  });
});
```

Create `frontend/tests/features/chat/messageHistory.test.ts`:

```typescript
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { toXChatDefaultMessages } from "../../../src/features/chat/utils/messageHistory";
import type { ChatMessageResponse } from "../../../src/features/chat/types/chat";

describe("chat message history mapping", () => {
  it("maps backend messages to @ant-design/x default messages", () => {
    const messages: ChatMessageResponse[] = [
      {
        message_id: "m1",
        chat_session_id: "s1",
        role: "user",
        content: "What is BRCA1?",
        created_at: "2026-06-11T00:00:00Z",
      },
      {
        message_id: "m2",
        chat_session_id: "s1",
        role: "assistant",
        content: "BRCA1 is a DNA repair gene.",
        created_at: "2026-06-11T00:00:01Z",
      },
    ];

    const mapped = toXChatDefaultMessages(messages);

    assert.deepEqual(mapped, [
      {
        id: "m1",
        status: "success",
        message: { role: "user", content: "What is BRCA1?" },
      },
      {
        id: "m2",
        status: "success",
        message: { role: "assistant", content: "BRCA1 is a DNA repair gene." },
      },
    ]);
  });
});
```

**Step 2: Update frontend chat types before running the new tests**

In `frontend/src/features/chat/types/chat.ts`, allow standalone sessions and include `chat_session_id` on messages. This must happen in Task 3 before `npm test`, because `localSessions.test.ts` intentionally constructs `processing_run_id: null`.

```typescript
export interface ChatSessionResponse {
  session_id: string;
  processing_run_id: string | null;
  created_at: string;
  message_count: number;
}

export interface BackendChatSessionResponse {
  chat_session_id: string;
  processing_run_id: string | null;
  created_at: string;
  message_count: number;
}

export interface ChatMessageResponse {
  message_id: string;
  chat_session_id: string;
  role: ChatRole;
  content: string;
  evidence_id?: string | null;
  entity_id?: string | null;
  created_at: string;
}
```

**Step 3: Include chat utility tests in TypeScript test build**

In `frontend/tsconfig.test.json`, add these include entries:

```json
"src/features/chat/types/**/*.ts",
"src/features/chat/utils/**/*.ts"
```

**Step 4: Run tests to verify they fail**

```bash
cd frontend
nvm use
npm test
```

Expected: FAIL because utility files do not exist.

**Step 5: Implement local session utility**

Create `frontend/src/features/chat/utils/localSessions.ts`:

```typescript
import type { ChatSessionResponse } from "../types/chat";

export const CHAT_SESSIONS_KEY = "cross-evidence.chat.sessions.v1";
export const ACTIVE_CHAT_SESSION_KEY = "cross-evidence.chat.activeSessionId.v1";
const MAX_LOCAL_SESSIONS = 20;

function safeStorage(storage?: Storage): Storage | null {
  if (storage) return storage;
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

export function loadLocalChatSessions(storage?: Storage): ChatSessionResponse[] {
  const target = safeStorage(storage);
  if (!target) return [];

  const raw = target.getItem(CHAT_SESSIONS_KEY);
  if (!raw) return [];

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is ChatSessionResponse => {
      return (
        typeof item === "object" &&
        item !== null &&
        typeof item.session_id === "string" &&
        typeof item.created_at === "string" &&
        typeof item.message_count === "number"
      );
    });
  } catch {
    return [];
  }
}

export function saveLocalChatSessions(
  storage: Storage | undefined,
  sessions: ChatSessionResponse[],
): void {
  const target = safeStorage(storage);
  if (!target) return;
  target.setItem(
    CHAT_SESSIONS_KEY,
    JSON.stringify(sessions.slice(0, MAX_LOCAL_SESSIONS)),
  );
}

export function upsertLocalChatSession(
  storage: Storage | undefined,
  session: ChatSessionResponse,
): ChatSessionResponse[] {
  const sessions = loadLocalChatSessions(storage);
  const next = [
    session,
    ...sessions.filter((item) => item.session_id !== session.session_id),
  ].slice(0, MAX_LOCAL_SESSIONS);
  saveLocalChatSessions(storage, next);
  return next;
}

export function rememberActiveChatSession(
  storage: Storage | undefined,
  sessionId: string,
): void {
  const target = safeStorage(storage);
  if (!target) return;
  target.setItem(ACTIVE_CHAT_SESSION_KEY, sessionId);
}

export function loadActiveChatSession(storage?: Storage): string | null {
  const target = safeStorage(storage);
  if (!target) return null;
  return target.getItem(ACTIVE_CHAT_SESSION_KEY);
}
```

**Step 6: Implement message history utility**

Create `frontend/src/features/chat/utils/messageHistory.ts`:

```typescript
import type { DefaultMessageInfo } from "@ant-design/x-sdk/es/x-chat";
import type { ChatMessageResponse } from "../types/chat";

export interface ChatBubbleMessage {
  role: "user" | "assistant";
  content: string;
}

export function toXChatDefaultMessages(
  messages: ChatMessageResponse[],
): DefaultMessageInfo<ChatBubbleMessage>[] {
  return messages
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({
      id: message.message_id,
      status: "success" as const,
      message: {
        role: message.role,
        content: message.content,
      },
    }));
}
```

**Step 7: Run tests**

```bash
cd frontend
nvm use
npm test
```

Expected: PASS.

**Step 8: Commit**

```bash
git add frontend/src/features/chat/types/chat.ts frontend/src/features/chat/utils/localSessions.ts frontend/src/features/chat/utils/messageHistory.ts frontend/tests/features/chat/localSessions.test.ts frontend/tests/features/chat/messageHistory.test.ts frontend/tsconfig.test.json
git commit -m "feat: add local chat session utilities"
```

## Task 4: Frontend Standalone Session Services And Hook

**Files:**
- Modify: `frontend/src/features/chat/services/chat.ts`
- Modify: `frontend/src/features/chat/hooks/useChatSessions.ts`
- Create: `frontend/src/features/chat/utils/messageRequests.ts`
- Test: `frontend/tests/features/chat/messageRequests.test.ts`

**Step 1: Write request-body test for the preserved appendMessage path**

Create `frontend/tests/features/chat/messageRequests.test.ts`:

```typescript
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildAppendMessageBody } from "../../../src/features/chat/utils/messageRequests";

describe("chat message request bodies", () => {
  it("builds persist-only user message body with role", () => {
    assert.deepEqual(buildAppendMessageBody("What is BRCA1?"), {
      role: "user",
      content: "What is BRCA1?",
      auto_reply: false,
    });
  });

  it("includes evidence_id only when provided", () => {
    assert.deepEqual(buildAppendMessageBody("Review this", "ev-1"), {
      role: "user",
      content: "Review this",
      evidence_id: "ev-1",
      auto_reply: false,
    });
  });
});
```

**Step 2: Implement request-body helper**

Create `frontend/src/features/chat/utils/messageRequests.ts`:

```typescript
export interface AppendMessageBody {
  role: "user";
  content: string;
  evidence_id?: string;
  auto_reply: false;
}

export function buildAppendMessageBody(
  content: string,
  evidenceId?: string,
): AppendMessageBody {
  return {
    role: "user",
    content,
    ...(evidenceId ? { evidence_id: evidenceId } : {}),
    auto_reply: false,
  };
}
```

**Step 3: Update service functions**

In `frontend/src/features/chat/services/chat.ts`, update session creation:

```typescript
export async function createSession(
  processingRunId?: string | null,
): Promise<ChatSessionResponse> {
  const body = processingRunId ? { processing_run_id: processingRunId } : {};
  const { data } = await apiClient.post<BackendChatSessionResponse>(
    "/chat/sessions",
    body,
  );
  return normalizeSession(data);
}
```

Keep `listSessions(processingRunId: string)` pipeline-bound for now.

Also update `appendMessage()` so the exported `useChatMessages()` path remains valid:

```typescript
import { buildAppendMessageBody } from "../utils/messageRequests";

export async function appendMessage(
  sessionId: string,
  content: string,
  evidenceId?: string,
): Promise<ChatMessageResponse> {
  const { data } = await apiClient.post<ChatMessageResponse>(
    `/chat/sessions/${sessionId}/messages`,
    buildAppendMessageBody(content, evidenceId),
  );
  return data;
}
```

Do not delete `useChatMessages()` in this task. It is exported by `frontend/src/features/chat/index.ts`, so preserving a working `appendMessage()` is the lower-risk change.

**Step 4: Update hook to use localStorage when no processing run exists**

Replace `frontend/src/features/chat/hooks/useChatSessions.ts` with this shape:

```typescript
"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listSessions, createSession as createBackendSession } from "../services/chat";
import {
  loadLocalChatSessions,
  upsertLocalChatSession,
  rememberActiveChatSession,
} from "../utils/localSessions";
import type { ChatSessionResponse } from "../types/chat";

export function useChatSessions(processingRunId?: string | null) {
  const queryClient = useQueryClient();
  const standalone = !processingRunId;
  const [localSessions, setLocalSessions] = useState<ChatSessionResponse[]>([]);

  useEffect(() => {
    if (standalone) {
      setLocalSessions(loadLocalChatSessions());
    }
  }, [standalone]);

  const sessionsQuery = useQuery({
    queryKey: ["chat", "sessions", processingRunId],
    queryFn: () => listSessions(processingRunId!),
    enabled: !standalone,
  });

  const create = useMutation({
    mutationFn: () => createBackendSession(processingRunId),
    onSuccess: (session) => {
      if (standalone) {
        const next = upsertLocalChatSession(undefined, session);
        rememberActiveChatSession(undefined, session.session_id);
        setLocalSessions(next);
        return;
      }
      queryClient.invalidateQueries({
        queryKey: ["chat", "sessions", processingRunId],
      });
    },
  });

  const sessions = useMemo(
    () => (standalone ? localSessions : sessionsQuery.data ?? []),
    [standalone, localSessions, sessionsQuery.data],
  );

  return {
    sessions,
    isLoading: standalone ? false : sessionsQuery.isLoading,
    createSession: create.mutateAsync,
    isCreating: create.isPending,
  };
}
```

**Step 5: Run frontend tests and type check**

```bash
cd frontend
nvm use
npm test
npm run type-check
```

Expected: PASS after the rest of the ChatView call sites are updated in Task 6. If this fails now only because of ChatView call sites, continue to Task 6 before rerunning.

**Step 6: Commit**

```bash
git add frontend/src/features/chat/services/chat.ts frontend/src/features/chat/hooks/useChatSessions.ts frontend/src/features/chat/utils/messageRequests.ts frontend/tests/features/chat/messageRequests.test.ts
git commit -m "feat: support standalone chat sessions on frontend"
```

## Task 5: Real SSE Chat Provider

**Files:**
- Modify: `frontend/src/features/chat/providers/acmgChatProvider.ts`
- Modify: `frontend/src/features/chat/services/chat.ts`
- Create: `frontend/src/features/chat/utils/sse.ts`
- Test: `frontend/tests/features/chat/sse.test.ts`

**Step 1: Write failing SSE utility test**

Create `frontend/tests/features/chat/sse.test.ts`:

```typescript
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { appendAssistantChunk } from "../../../src/features/chat/utils/sse";

describe("chat SSE utilities", () => {
  it("appends text chunks from backend JSON SSE data", () => {
    const first = appendAssistantChunk(undefined, {
      data: JSON.stringify({ type: "text", content: "Hello " }),
    });
    const second = appendAssistantChunk(first, {
      data: JSON.stringify({ type: "text", content: "world" }),
    });

    assert.deepEqual(second, { role: "assistant", content: "Hello world" });
  });

  it("converts backend errors into assistant-visible text", () => {
    const message = appendAssistantChunk(undefined, {
      data: JSON.stringify({ type: "error", message: "LLM timeout" }),
    });

    assert.deepEqual(message, {
      role: "assistant",
      content: "[Error] LLM timeout",
    });
  });
});
```

**Step 2: Run test to verify it fails**

```bash
cd frontend
nvm use
npm test
```

Expected: FAIL because `utils/sse.ts` does not exist.

**Step 3: Implement SSE utility**

Create `frontend/src/features/chat/utils/sse.ts`:

```typescript
import type { SSEOutput } from "@ant-design/x-sdk";
import type { ChatBubbleMessage } from "./messageHistory";

interface BackendTextEvent {
  type: "text";
  content: string;
}

interface BackendDoneEvent {
  type: "done";
}

interface BackendErrorEvent {
  type: "error";
  message: string;
}

type BackendStreamEvent = BackendTextEvent | BackendDoneEvent | BackendErrorEvent;

function parseBackendEvent(chunk: SSEOutput | undefined): BackendStreamEvent | null {
  if (!chunk || typeof chunk.data !== "string") return null;
  try {
    return JSON.parse(chunk.data) as BackendStreamEvent;
  } catch {
    return null;
  }
}

export function appendAssistantChunk(
  originMessage: ChatBubbleMessage | undefined,
  chunk: SSEOutput | undefined,
): ChatBubbleMessage {
  const current = originMessage ?? { role: "assistant" as const, content: "" };
  const event = parseBackendEvent(chunk);
  if (!event) return current;

  if (event.type === "text") {
    return { ...current, content: `${current.content}${event.content}` };
  }

  if (event.type === "error") {
    return { ...current, content: `[Error] ${event.message}` };
  }

  return current;
}
```

**Step 4: Update provider transform and persist-only POST**

In `frontend/src/features/chat/providers/acmgChatProvider.ts`:

- Import `appendAssistantChunk` and `ChatBubbleMessage`.
- Change `AcmgChatProvider` generic from local `ChatMessage` to `ChatBubbleMessage`.
- Replace `transformMessage()`:

```typescript
transformMessage(
  info: TransformMessage<ChatBubbleMessage, SSEOutput>,
): ChatBubbleMessage {
  return appendAssistantChunk(info.originMessage, info.chunk);
}
```

Update `sendChatMessage()` to reuse the same persist-only request body helper as `appendMessage()`:

```typescript
import { buildAppendMessageBody } from "../utils/messageRequests";

await apiClient.post(`/chat/sessions/${sessionId}/messages`, {
  ...buildAppendMessageBody(content, evidenceId),
});
```

**Step 5: Run tests and type check**

```bash
cd frontend
nvm use
npm test
npm run type-check
```

Expected: PASS after Task 6 updates any ChatView types.

**Step 6: Commit**

```bash
git add frontend/src/features/chat/providers/acmgChatProvider.ts frontend/src/features/chat/services/chat.ts frontend/src/features/chat/utils/sse.ts frontend/tests/features/chat/sse.test.ts
git commit -m "fix: stream real chat chunks in frontend provider"
```

## Task 6: ChatView Session Flow, Upload Prompt, History, And Layout

**Files:**
- Modify: `frontend/src/features/chat/components/ChatView.tsx`
- Modify: `frontend/src/features/chat/components/forms/PipelineStartForm.tsx`
- Modify: `frontend/app/(dashboard)/chat/page.tsx`
- Modify: `frontend/app/(dashboard)/chat/[sessionId]/page.tsx`

**Step 1: Add default upload mode to the pipeline form**

In `PipelineStartForm.tsx`, change props and state:

```typescript
interface PipelineStartFormProps {
  onSubmit: (data: PipelineFormData) => void;
  isSubmitting?: boolean;
  defaultSourceType?: "online" | "local";
}
```

Import `useEffect`, then initialize and sync:

```typescript
export function PipelineStartForm({
  onSubmit,
  isSubmitting,
  defaultSourceType = "online",
}: PipelineStartFormProps) {
  const [sourceType, setSourceType] = useState<"online" | "local">(
    defaultSourceType,
  );
  const [query, setQuery] = useState("");
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    setSourceType(defaultSourceType);
  }, [defaultSourceType]);
```

**Step 2: Load backend history into `useXChat`**

In `ChatView.tsx`, import:

```typescript
import { listMessages } from "../services/chat";
import { loadActiveChatSession, rememberActiveChatSession, upsertLocalChatSession } from "../utils/localSessions";
import { toXChatDefaultMessages } from "../utils/messageHistory";
```

Add a reusable default-message loader:

```typescript
const loadDefaultMessages = useCallback(
  async (info?: { conversationKey?: string }) => {
    if (!info?.conversationKey) return [];
    const history = await listMessages(info.conversationKey);
    return toXChatDefaultMessages(history);
  },
  [],
);
```

Pass it to both `useXChat()` calls:

```typescript
const { messages, onRequest, isRequesting, abort, queueRequest } = useXChat({
  provider: activeProvider,
  conversationKey: activeConversationKey,
  defaultMessages: loadDefaultMessages,
});
```

For `SingleSessionChat`, use:

```typescript
defaultMessages: async () => toXChatDefaultMessages(await listMessages(sessionId)),
```

Remove the existing JSON `parser` from `useXChat()` because `transformMessage()` now stores plain assistant content.

**Step 3: Sync asynchronously loaded conversation list**

Destructure `setConversations` from `useXConversations()`:

```typescript
const {
  conversations,
  activeConversationKey,
  setActiveConversationKey,
  addConversation,
  setConversations,
} = useXConversations({
  defaultConversations: conversationItems,
  defaultActiveConversationKey: sessions[0]?.session_id,
});
```

Add:

```typescript
useEffect(() => {
  setConversations(conversationItems);
  const remembered = loadActiveChatSession();
  const rememberedExists = conversationItems.some((item) => item.key === remembered);
  if (remembered && rememberedExists) {
    setActiveConversationKey(remembered);
    return;
  }
  if (!activeConversationKey && conversationItems[0]) {
    setActiveConversationKey(conversationItems[0].key);
  }
}, [
  activeConversationKey,
  conversationItems,
  setActiveConversationKey,
  setConversations,
]);
```

**Step 4: Implement `ensureActiveSession()`**

Replace `handleCreateSession()` and use this helper:

```typescript
const ensureActiveSession = useCallback(async (): Promise<string> => {
  if (activeConversationKey) return activeConversationKey;

  const session = await createSession();
  const item = {
    key: session.session_id,
    label: `Session ${session.session_id.slice(0, 8)}`,
  };
  addConversation(item, "prepend");
  setActiveConversationKey(session.session_id);
  upsertLocalChatSession(undefined, session);
  rememberActiveChatSession(undefined, session.session_id);
  return session.session_id;
}, [activeConversationKey, addConversation, createSession, setActiveConversationKey]);

async function handleCreateSession() {
  try {
    await ensureActiveSession();
  } catch {
    antdMessage.error("Failed to create session");
  }
}
```

**Step 5: Send messages through a newly created session when needed**

Update `handleSendMessage()`:

```typescript
const handleSendMessage = useCallback(
  async (content: string) => {
    const trimmed = content.trim();
    if (!trimmed) return;
    setActiveForm(null);

    try {
      const sessionKey = await ensureActiveSession();
      await sendChatMessage(sessionKey, trimmed);
      const request = { messages: [{ role: "user" as const, content: trimmed }] };

      if (sessionKey === activeConversationKey) {
        onRequest(request);
        return;
      }
      queueRequest(sessionKey, request);
    } catch {
      antdMessage.error("Failed to send message");
    }
  },
  [
    activeConversationKey,
    ensureActiveSession,
    onRequest,
    queueRequest,
    setActiveForm,
  ],
);
```

**Step 6: Make Upload PDF prompt open local upload mode**

Change `handlePromptClick()` to avoid sending a fake user message:

```typescript
async function handlePromptClick(key: string) {
  if (key === "start-pipeline" || key === "upload-pdf") {
    try {
      await ensureActiveSession();
      setActiveForm(key);
    } catch {
      antdMessage.error("Failed to create session");
    }
    return;
  }

  if (key === "search-evidence") {
    window.location.href = "/evidence";
    return;
  }

  const prompt = PROMPT_ITEMS.find((p) => p.key === key);
  if (prompt) {
    handleSendMessage(prompt.description);
  }
}
```

When rendering `PipelineStartForm`, pass:

```tsx
<PipelineStartForm
  defaultSourceType={activeForm === "upload-pdf" ? "local" : "online"}
  onSubmit={handlePipelineSubmit}
  isSubmitting={isRequesting}
/>
```

**Step 7: Tighten the chat layout**

Replace the top-level FullChatView shell classes with:

```tsx
<div className="flex min-h-[620px] overflow-hidden rounded-md border border-gray-200 bg-white shadow-sm md:h-[calc(100vh-8.5rem)]">
```

Replace the empty-state wrapper with:

```tsx
<div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-8 text-center md:px-10">
```

Give `Prompts` a constrained width:

```tsx
<Prompts
  className="w-full max-w-3xl"
  items={PROMPT_ITEMS}
  wrap
  onItemClick={(info) => handlePromptClick(info.data.key as string)}
/>
```

Use the same shell height for `SingleSessionChat`:

```tsx
<div className="flex min-h-[620px] flex-col overflow-hidden rounded-md border border-gray-200 bg-white shadow-sm md:h-[calc(100vh-8.5rem)]">
```

In `frontend/app/(dashboard)/chat/page.tsx`, reduce page spacing:

```tsx
return (
  <div className="flex min-h-0 flex-col gap-4">
    <PageHeader title="Chat Sessions" />
    <ChatView />
  </div>
);
```

In `frontend/app/(dashboard)/chat/[sessionId]/page.tsx`, do the same wrapper.

**Step 8: Run frontend checks**

```bash
cd frontend
nvm use
npm test
npm run type-check
npm run lint
```

Expected: PASS.

**Step 9: Manual browser verification**

Run:

```bash
cd frontend
nvm use
npm run dev
```

Verify:

- Open `http://localhost:3000/chat`.
- Click New session. No warning appears; a session appears in the left rail.
- Reload. The same session remains selected.
- Click the `Upload PDF` prompt. The form opens with local upload selected.
- Select a PDF and submit. A pipeline status card appears.
- Send `What can you help me do with ACMG evidence?`. The assistant streams text.

**Step 10: Commit**

```bash
git add frontend/src/features/chat/components/ChatView.tsx frontend/src/features/chat/components/forms/PipelineStartForm.tsx 'frontend/app/(dashboard)/chat/page.tsx' 'frontend/app/(dashboard)/chat/[sessionId]/page.tsx'
git commit -m "feat: enable standalone chat upload flow"
```

## Task 7: Backend Chat Prompt For Standalone AI Use

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py:220-365`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_sse.py`

**Step 1: Write failing provider-call tests**

Add a test that asks a question without `evidence_id` and asserts the provider receives a general CrossEvidence prompt, not a context-only prompt:

```python
async def test_generate_reply_without_evidence_uses_general_chat_prompt(
    self, db_session: AsyncSession
) -> None:
    """Standalone chat uses a general assistant prompt when no evidence card is selected."""
    run_id = await self._create_test_run(db_session)
    service = ChatService(db_session)
    session = await service.create_session(processing_run_id=run_id, user_id=None)

    with patch(
        "src.core.visualize_evidence_with_expert_in_loop.providers.ReasoningLLMProvider.generate",
        new_callable=AsyncMock,
    ) as mock_llm:
        mock_llm.return_value = "I can help start a pipeline."
        reply = await service.generate_reply(
            session_id=session.chat_session_id,
            user_message="What can you do?",
            evidence_id=None,
        )

    assert reply == "I can help start a pipeline."
    kwargs = mock_llm.await_args.kwargs
    assert "CrossEvidence" in kwargs["system_prompt"]
    assert "pipeline" in kwargs["system_prompt"].lower()
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py::TestChatAI::test_generate_reply_without_evidence_uses_general_chat_prompt -v
```

Expected: FAIL because the prompt is evidence-card-specific.

**Step 3: Implement prompt helper**

In `ChatService`, add:

```python
def _system_prompt(self, *, has_evidence_context: bool) -> str:
    """Build the chat system prompt for evidence-bound or standalone chat."""
    if has_evidence_context:
        return (
            "You are a clinical genetics assistant inside CrossEvidence. Answer "
            "questions about evidence cards using the provided context. Be "
            "precise and cite specific fields from the evidence card."
        )

    return (
        "You are the CrossEvidence assistant. Help users start literature "
        "evidence extraction pipelines, upload biomedical PDFs, search "
        "existing evidence, and understand ACMG evidence extraction results. "
        "Do not provide a clinical diagnosis. When evidence is unavailable, "
        "state what information is needed."
    )
```

Use it in both `generate_reply()` and `stream_reply()`:

```python
system_prompt = self._system_prompt(has_evidence_context=bool(context))
```

**Step 4: Run focused backend tests**

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py tests/core/visualize_evidence_with_expert_in_loop/test_chat_sse.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py
git commit -m "fix: support standalone chat assistant prompt"
```

## Task 8: Final Verification And Documentation

**Files:**
- Modify: `frontend/src/features/chat/README.md`
- Modify: `docs/active/APP_FLOW.md`
- Modify: `docs/active/FRONTEND_GUIDELINES.md`
- Modify: `progress.txt`

**Step 1: Run backend verification**

```bash
cd backend
uv run ruff check
uv run pytest tests/api/test_chat_api.py tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py tests/core/visualize_evidence_with_expert_in_loop/test_chat_sse.py -v
```

Expected: Ruff clean and all focused tests PASS.

**Step 2: Run frontend verification**

```bash
cd frontend
nvm use
npm test
npm run type-check
npm run lint
```

Expected: all PASS.

**Step 3: Update docs**

In `frontend/src/features/chat/README.md`, update:

- `useChatSessions(runId)` to `useChatSessions(runId?)`.
- Explain that `/chat` stores standalone session metadata in `localStorage`.
- Correct the SSE protocol description to the current backend format:

```markdown
Backend streams standard SSE `data:` lines where each data payload is JSON:
`{"type":"text","content":"..."}`, `{"type":"done"}`, or
`{"type":"error","message":"..."}`.
```

In `docs/active/APP_FLOW.md`, update Chat Flow:

- `/chat` creates standalone sessions without a processing run.
- Browser `localStorage` stores only visible session metadata and active session ID.
- Backend persists message history and assistant responses.
- Upload PDF prompt opens local mode by default.

In `docs/active/FRONTEND_GUIDELINES.md`, update the Chat Feature section with the same runtime behavior.

**Step 4: Record progress**

Append to root `progress.txt`:

```text
[2026-06-11] [Standalone chat session, local upload prompt, and real AI streaming chat] [done]
```

**Step 5: Use doc-organize**

Because `docs/` changed, use `skill:doc-organize` after implementation. Keep this plan in `docs/plans/` while it is pending execution; move it to `docs/archive/plans/` only after implementation and review are complete.

After running `doc-organize`, inspect all generated document changes:

```bash
git status --short docs
```

Stage every documentation change produced by the skill, including `docs/README.md` updates or any moves:

```bash
git add -A docs
```

**Step 6: Final status**

```bash
git status --short
```

Expected: only intended files are modified.

**Step 7: Commit**

```bash
git add -A docs progress.txt
git commit -m "docs: update chat session flow documentation"
```

## Execution Notes

- Use `uv` for backend commands. Do not use system `pip`.
- Use `nvm use` before frontend `npm` commands.
- Do not introduce Ansible, deployment, or unrelated config changes.
- Do not delete old-version code.
- Do not move this plan to archive until the implementation is complete and reviewed.
