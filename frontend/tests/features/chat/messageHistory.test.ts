import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type { ChatMessageResponse } from "../../../src/features/chat/types/chat";
import { toXChatDefaultMessages } from "../../../src/features/chat/utils/messageHistory";

describe("chat message history mapping", () => {
  it("maps backend messages to @ant-design/x default messages", () => {
    const messages: ChatMessageResponse[] = [
      {
        message_id: "m1",
        chat_session_id: "s1",
        role: "user",
        content: "What is BRCA1?",
        created_at: "2026-06-11T00:00:00Z",
      },
      {
        message_id: "m2",
        chat_session_id: "s1",
        role: "assistant",
        content: "BRCA1 is a DNA repair gene.",
        created_at: "2026-06-11T00:00:01Z",
      },
    ];

    const mapped = toXChatDefaultMessages(messages);

    assert.deepEqual(mapped, [
      {
        id: "m1",
        status: "success",
        message: { role: "user", content: "What is BRCA1?" },
      },
      {
        id: "m2",
        status: "success",
        message: {
          role: "assistant",
          content: "BRCA1 is a DNA repair gene.",
        },
      },
    ]);
  });
});
