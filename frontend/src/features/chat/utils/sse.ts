import type { SSEOutput } from "@ant-design/x-sdk";

import type { ChatAction, ChatActionIntent } from "../types/actions";
import type { ChatBubbleMessage } from "./messageHistory";

interface BackendTextEvent {
  type: "text";
  content: string;
}

interface BackendActionEvent {
  type: "action";
  intent: ChatActionIntent;
  slots: Record<string, string | undefined>;
}

interface BackendDoneEvent {
  type: "done";
}

interface BackendErrorEvent {
  type: "error";
  message: string;
}

type BackendStreamEvent =
  | BackendTextEvent
  | BackendActionEvent
  | BackendDoneEvent
  | BackendErrorEvent;

function parseBackendEvent(chunk: SSEOutput | undefined): BackendStreamEvent | null {
  if (!chunk || typeof chunk.data !== "string") return null;

  try {
    return JSON.parse(chunk.data) as BackendStreamEvent;
  } catch {
    return null;
  }
}

export function appendAssistantChunk(
  originMessage: ChatBubbleMessage | undefined,
  chunk: SSEOutput | undefined,
): ChatBubbleMessage {
  const current = originMessage ?? {
    role: "assistant" as const,
    content: "",
  };
  const event = parseBackendEvent(chunk);

  if (!event) return current;

  if (event.type === "text") {
    return {
      ...current,
      content: `${current.content}${event.content}`,
    };
  }

  if (event.type === "action") {
    const action: ChatAction = {
      intent: event.intent,
      slots: event.slots,
    };
    return {
      ...current,
      action,
    };
  }

  if (event.type === "error") {
    return {
      ...current,
      content: `[Error] ${event.message}`,
    };
  }

  return current;
}
