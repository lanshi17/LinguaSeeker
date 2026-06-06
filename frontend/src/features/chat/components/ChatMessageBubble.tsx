import { cn } from "@/lib/utils/cn";
import type { ChatMessageResponse } from "../types/chat";

interface ChatMessageBubbleProps {
  message: ChatMessageResponse;
}

export function ChatMessageBubble({ message }: ChatMessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-4 py-2 text-sm",
          isUser
            ? "bg-primary-600 text-white"
            : message.role === "system"
              ? "bg-yellow-50 text-yellow-800"
              : "bg-gray-100 text-gray-900",
        )}
      >
        {!isUser && (
          <span className="mb-1 block text-xs font-medium opacity-60">
            {message.role === "assistant" ? "AI Assistant" : "System"}
          </span>
        )}
        <p className="whitespace-pre-wrap">{message.content}</p>
        <span className="mt-1 block text-right text-xs opacity-50">
          {new Date(message.created_at).toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}
