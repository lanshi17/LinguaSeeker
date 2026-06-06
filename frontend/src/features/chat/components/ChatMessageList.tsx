"use client";

import { useEffect, useRef } from "react";
import { ChatMessageBubble } from "./ChatMessageBubble";
import { Spinner } from "@/components/ui/Spinner";
import type { ChatMessageResponse } from "../types/chat";

interface ChatMessageListProps {
  messages: ChatMessageResponse[];
  isLoading?: boolean;
}

export function ChatMessageList({ messages, isLoading }: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-3 overflow-y-auto p-4">
      {messages.length === 0 && (
        <p className="py-10 text-center text-sm text-gray-400">
          No messages yet. Start the conversation.
        </p>
      )}
      {messages.map((msg) => (
        <ChatMessageBubble key={msg.message_id} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
