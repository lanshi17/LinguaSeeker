"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listSessions, createSession } from "../services/chat";

export function useChatSessions(processingRunId: string) {
  const queryClient = useQueryClient();

  const sessions = useQuery({
    queryKey: ["chat", "sessions", processingRunId],
    queryFn: () => listSessions(processingRunId),
  });

  const create = useMutation({
    mutationFn: () => createSession(processingRunId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["chat", "sessions", processingRunId],
      });
    },
  });

  return {
    sessions: sessions.data ?? [],
    isLoading: sessions.isLoading,
    createSession: create.mutateAsync,
    isCreating: create.isPending,
  };
}
