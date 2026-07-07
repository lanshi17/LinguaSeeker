
import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ChatSessionResponse } from "../types/chat";
import {
  createSession as createBackendSession,
  getSession,
  listSessions,
} from "../services/chat";
import {
  loadLocalChatSessions,
  rememberActiveChatSession,
  removeLocalChatSession,
  upsertLocalChatSession,
} from "../utils/localSessions";

export function useChatSessions(processingRunId?: string | null) {
  const queryClient = useQueryClient();
  const standalone = !processingRunId;
  const [localSessions, setLocalSessions] = useState<ChatSessionResponse[]>(() =>
    standalone ? loadLocalChatSessions() : [],
  );

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

  // Client-side hide: the backend has no DELETE endpoint, so removing from
  // the sidebar is purely local. Direct navigation to /chat/{id} still
  // re-hydrates the session from the backend, so this is "hide from list"
  // not "destroy evidence".
  const remove = useCallback((sessionId: string) => {
    if (standalone) {
      setLocalSessions(removeLocalChatSession(undefined, sessionId));
    }
  }, [standalone]);

  const refreshSession = useCallback(
    async (sessionId: string): Promise<ChatSessionResponse> => {
      const session = await getSession(sessionId);

      if (standalone) {
        const next = upsertLocalChatSession(undefined, session);
        setLocalSessions(next);
        return session;
      }

      queryClient.setQueryData<ChatSessionResponse[]>(
        ["chat", "sessions", processingRunId],
        (previous) => {
          if (!previous) return previous;
          if (!previous.some((item) => item.session_id === sessionId)) {
            return previous;
          }
          return previous.map((item) =>
            item.session_id === sessionId ? session : item,
          );
        },
      );
      return session;
    },
    [processingRunId, queryClient, standalone],
  );

  const sessions = useMemo(
    () => (standalone ? localSessions : sessionsQuery.data ?? []),
    [localSessions, sessionsQuery.data, standalone],
  );

  return {
    sessions,
    isLoading: standalone ? false : sessionsQuery.isLoading,
    createSession: create.mutateAsync,
    isCreating: create.isPending,
    removeSession: remove,
    refreshSession,
  };
}
