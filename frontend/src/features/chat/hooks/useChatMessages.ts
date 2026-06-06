"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listMessages, appendMessage } from "../services/chat";

export function useChatMessages(sessionId: string) {
  const queryClient = useQueryClient();

  const messages = useQuery({
    queryKey: ["chat", "messages", sessionId],
    queryFn: () => listMessages(sessionId),
  });

  const send = useMutation({
    mutationFn: ({ content, evidenceId }: { content: string; evidenceId?: string }) =>
      appendMessage(sessionId, content, evidenceId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["chat", "messages", sessionId],
      });
    },
  });

  return {
    messages: messages.data ?? [],
    isLoading: messages.isLoading,
    sendMessage: send.mutateAsync,
    isSending: send.isPending,
  };
}
