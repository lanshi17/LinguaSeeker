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
    .filter(
      (message) => message.role === "user" || message.role === "assistant",
    )
    .map((message) => ({
      id: message.message_id,
      status: "success" as const,
      message: {
        role: message.role,
        content: message.content,
      },
    }));
}
