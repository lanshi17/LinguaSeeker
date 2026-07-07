import type { ChatSessionResponse } from "../types/chat";

export const CHAT_SESSIONS_KEY = "lingua-seeker.chat.sessions.v1";
export const ACTIVE_CHAT_SESSION_KEY = "lingua-seeker.chat.activeSessionId.v1";

const MAX_LOCAL_SESSIONS = 20;

function safeStorage(storage?: Storage): Storage | null {
  if (storage) return storage;
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

function isChatSessionResponse(value: unknown): value is ChatSessionResponse {
  if (typeof value !== "object" || value === null) return false;

  const item = value as Partial<ChatSessionResponse>;

  return (
    typeof item.session_id === "string" &&
    (typeof item.processing_run_id === "string" ||
      item.processing_run_id === null ||
      item.processing_run_id === undefined) &&
    (typeof item.title === "string" ||
      item.title === null ||
      item.title === undefined) &&
    typeof item.created_at === "string" &&
    typeof item.message_count === "number"
  );
}

export function loadLocalChatSessions(
  storage?: Storage,
): ChatSessionResponse[] {
  const target = safeStorage(storage);
  if (!target) return [];

  const raw = target.getItem(CHAT_SESSIONS_KEY);
  if (!raw) return [];

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(isChatSessionResponse).map((item) => ({
      ...item,
      processing_run_id: item.processing_run_id ?? null,
      title: item.title ?? null,
    }));
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

export function removeLocalChatSession(
  storage: Storage | undefined,
  sessionId: string,
): ChatSessionResponse[] {
  const sessions = loadLocalChatSessions(storage).filter(
    (item) => item.session_id !== sessionId,
  );
  saveLocalChatSessions(storage, sessions);
  if (loadActiveChatSession(storage) === sessionId) {
    safeStorage(storage)?.removeItem(ACTIVE_CHAT_SESSION_KEY);
  }
  return sessions;
}
