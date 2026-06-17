import "@testing-library/jest-dom/vitest";

import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { useChatSessions } from "../../../src/features/chat/hooks/useChatSessions";
import * as chatServices from "../../../src/features/chat/services/chat";
import { CHAT_SESSIONS_KEY } from "../../../src/features/chat/utils/localSessions";
import type { ChatSessionResponse } from "../../../src/features/chat/types/chat";

vi.mock("../../../src/features/chat/services/chat", () => ({
  createSession: vi.fn(),
  listSessions: vi.fn(),
}));

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

function session(id: string, runId: string | null = null): ChatSessionResponse {
  return {
    session_id: id,
    processing_run_id: runId,
    created_at: "2026-06-16T00:00:00Z",
    message_count: 0,
  };
}

describe("useChatSessions — standalone (no processingRunId)", () => {
  it("loads sessions from localStorage on initial render", () => {
    const sessions = [session("s1"), session("s2")];
    window.localStorage.setItem(
      CHAT_SESSIONS_KEY,
      JSON.stringify(sessions),
    );

    const { result } = renderHook(() => useChatSessions(), {
      wrapper: makeWrapper(),
    });

    expect(result.current.sessions).toHaveLength(2);
    expect(result.current.sessions[0].session_id).toBe("s1");
    expect(result.current.sessions[1].session_id).toBe("s2");
    expect(result.current.isLoading).toBe(false);
    expect(chatServices.listSessions).not.toHaveBeenCalled();
  });

  it("returns empty array when localStorage has no sessions", () => {
    const { result } = renderHook(() => useChatSessions(), {
      wrapper: makeWrapper(),
    });

    expect(result.current.sessions).toEqual([]);
    expect(result.current.isLoading).toBe(false);
  });

  it("createSession calls backend API and upserts into localStorage", async () => {
    const newSession = session("new-session");
    vi.mocked(chatServices.createSession).mockResolvedValue(newSession);

    const { result } = renderHook(() => useChatSessions(), {
      wrapper: makeWrapper(),
    });

    let created: ChatSessionResponse;
    await act(async () => {
      created = await result.current.createSession();
    });

    expect(chatServices.createSession).toHaveBeenCalledWith(undefined);
    expect(created!.session_id).toBe("new-session");

    // Check localStorage was updated
    const stored = JSON.parse(
      window.localStorage.getItem(CHAT_SESSIONS_KEY) ?? "[]",
    );
    expect(stored).toHaveLength(1);
    expect(stored[0].session_id).toBe("new-session");

    // Check hook state was updated
    expect(result.current.sessions).toHaveLength(1);
    expect(result.current.sessions[0].session_id).toBe("new-session");
  });

  it("isCreating becomes true when createSession is called", async () => {
    let resolveCreate: (value: ChatSessionResponse) => void;
    vi.mocked(chatServices.createSession).mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve;
      }),
    );

    const { result } = renderHook(() => useChatSessions(), {
      wrapper: makeWrapper(),
    });

    expect(result.current.isCreating).toBe(false);

    // Kick off the creation — we don't await the promise because we
    // want to inspect state while it's pending.
    let createPromise: Promise<ChatSessionResponse>;
    act(() => {
      createPromise = result.current.createSession();
    });

    // Wait for React Query to transition to pending state
    await vi.waitFor(() => {
      expect(result.current.isCreating).toBe(true);
    });

    // Clean up: resolve the promise
    act(() => {
      resolveCreate!(session("pending-test"));
    });
    await createPromise!;
  });

  it("removeSession removes from localStorage (client-side hide)", () => {
    const sessions = [session("s1"), session("s2")];
    window.localStorage.setItem(
      CHAT_SESSIONS_KEY,
      JSON.stringify(sessions),
    );

    const { result } = renderHook(() => useChatSessions(), {
      wrapper: makeWrapper(),
    });

    act(() => {
      result.current.removeSession("s1");
    });

    expect(result.current.sessions).toHaveLength(1);
    expect(result.current.sessions[0].session_id).toBe("s2");

    const stored = JSON.parse(
      window.localStorage.getItem(CHAT_SESSIONS_KEY) ?? "[]",
    );
    expect(stored).toHaveLength(1);
    expect(stored[0].session_id).toBe("s2");
  });
});

describe("useChatSessions — run-scoped (with processingRunId)", () => {
  it("fetches sessions from backend via React Query", async () => {
    const sessions = [session("s1", "run-1"), session("s2", "run-1")];
    vi.mocked(chatServices.listSessions).mockResolvedValue(sessions);

    const { result } = renderHook(() => useChatSessions("run-1"), {
      wrapper: makeWrapper(),
    });

    // Initially loading
    expect(result.current.isLoading).toBe(true);

    // Wait for query to resolve
    await vi.waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.sessions).toHaveLength(2);
    expect(result.current.sessions[0].session_id).toBe("s1");
    expect(chatServices.listSessions).toHaveBeenCalledWith("run-1");
  });

  it("createSession calls backend API and invalidates the sessions query", async () => {
    const existingSessions = [session("s1", "run-1")];
    const newSession = session("s2", "run-1");

    let callCount = 0;
    vi.mocked(chatServices.listSessions).mockImplementation(async () => {
      callCount++;
      if (callCount === 1) return existingSessions;
      // After invalidation + refetch, return updated list
      return [...existingSessions, newSession];
    });
    vi.mocked(chatServices.createSession).mockResolvedValue(newSession);

    const { result } = renderHook(() => useChatSessions("run-1"), {
      wrapper: makeWrapper(),
    });

    // Wait for initial load
    await vi.waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.sessions).toHaveLength(1);

    // Create new session
    await act(async () => {
      await result.current.createSession();
    });

    expect(chatServices.createSession).toHaveBeenCalledWith("run-1");

    // After invalidation, the query should refetch and include the new session
    await vi.waitFor(() => {
      expect(result.current.sessions).toHaveLength(2);
    });
  });

  it("isLoading is true while the query is pending", () => {
    vi.mocked(chatServices.listSessions).mockReturnValue(
      new Promise(() => {}), // never resolves
    );

    const { result } = renderHook(() => useChatSessions("run-1"), {
      wrapper: makeWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.sessions).toEqual([]);
  });

  it("removeSession is a no-op in run-scoped mode", () => {
    const sessions = [session("s1", "run-1")];
    vi.mocked(chatServices.listSessions).mockResolvedValue(sessions);

    const { result } = renderHook(() => useChatSessions("run-1"), {
      wrapper: makeWrapper(),
    });

    // Should not throw, and should not affect anything
    act(() => {
      result.current.removeSession("s1");
    });

    // No change - sessions still come from the query
    expect(chatServices.listSessions).toHaveBeenCalled();
  });
});
