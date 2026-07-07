import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type { ChatSessionResponse } from "../../../src/features/chat/types/chat";
import {
  ACTIVE_CHAT_SESSION_KEY,
  CHAT_SESSIONS_KEY,
  loadLocalChatSessions,
  rememberActiveChatSession,
  upsertLocalChatSession,
} from "../../../src/features/chat/utils/localSessions";

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

    assert.deepEqual(
      saved.map((item) => item.session_id),
      ["a", "b"],
    );
    assert.equal(saved[0].message_count, 2);
  });

  it("preserves generated titles when loading sessions", () => {
    const storage = new MemoryStorage();
    storage.setItem(
      CHAT_SESSIONS_KEY,
      JSON.stringify([{ ...session("titled"), title: "BRCA1 upload plan" }]),
    );

    const saved = loadLocalChatSessions(storage);

    assert.equal(saved[0].title, "BRCA1 upload plan");
  });

  it("remembers the active session id", () => {
    const storage = new MemoryStorage();

    rememberActiveChatSession(storage, "session-1");

    assert.equal(storage.getItem(ACTIVE_CHAT_SESSION_KEY), "session-1");
  });
});
