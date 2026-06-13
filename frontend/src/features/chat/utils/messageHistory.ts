import type { DefaultMessageInfo } from "@ant-design/x-sdk/es/x-chat";

import type { ChatAction } from "../types/actions";
import type { ChatMessageResponse } from "../types/chat";

export interface ChatBubbleMessage {
  role: "user" | "assistant";
  content: string;
  action?: ChatAction;
}

interface ChatMessageKeySource {
  id: string | number;
}

function isChatBubbleMessage(
  message: ChatMessageResponse,
): message is ChatMessageResponse & { role: ChatBubbleMessage["role"] } {
  return message.role === "user" || message.role === "assistant";
}

export function toXChatDefaultMessages(
  messages: ChatMessageResponse[],
): DefaultMessageInfo<ChatBubbleMessage>[] {
  return messages
    .filter(isChatBubbleMessage)
    .map((message) => ({
      id: message.message_id,
      status: "success" as const,
      message: {
        role: message.role,
        content: message.content,
      },
    }));
}

export function toUniqueChatMessageKeys(
  messages: readonly ChatMessageKeySource[],
): string[] {
  const seen = new Map<string, number>();

  return messages.map(({ id }) => {
    const key = String(id);
    const count = (seen.get(key) ?? 0) + 1;
    seen.set(key, count);

    return count === 1 ? key : `${key}__${count}`;
  });
}
