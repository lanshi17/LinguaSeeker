"use client";

import { ChatSessionList } from "./ChatSessionList";
import { ChatMessageList } from "./ChatMessageList";
import { ChatComposer } from "./ChatComposer";
import { useChatMessages } from "../hooks/useChatMessages";

interface ChatViewProps {
  processingRunId?: string;
  sessionId?: string;
}

/** Client wrapper for the chat feature. Wired by page shells. */
export function ChatView({ processingRunId, sessionId }: ChatViewProps) {
  if (sessionId) {
    return <ChatSession sessionId={sessionId} />;
  }

  if (processingRunId) {
    return <ChatSessionList processingRunId={processingRunId} />;
  }

  return (
    <p className="py-10 text-center text-sm text-gray-500">
      No processing run selected. Start a pipeline first.
    </p>
  );
}

function ChatSession({ sessionId }: { sessionId: string }) {
  const { messages, sendMessage, isLoading, isSending } =
    useChatMessages(sessionId);

  return (
    <div className="flex h-[calc(100vh-12rem)] flex-col rounded-lg border border-gray-200 bg-white">
      <ChatMessageList messages={messages} isLoading={isLoading} />
      <ChatComposer
        onSend={(content) => sendMessage({ content })}
        isSending={isSending}
      />
    </div>
  );
}
