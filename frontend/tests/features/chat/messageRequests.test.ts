import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildAppendMessageBody } from "../../../src/features/chat/utils/messageRequests";

describe("chat message request bodies", () => {
  it("builds persist-only user message body with role", () => {
    assert.deepEqual(buildAppendMessageBody("What is BRCA1?"), {
      role: "user",
      content: "What is BRCA1?",
      auto_reply: false,
    });
  });

  it("includes evidence_id only when provided", () => {
    assert.deepEqual(buildAppendMessageBody("Review this", "ev-1"), {
      role: "user",
      content: "Review this",
      evidence_id: "ev-1",
      auto_reply: false,
    });
  });
});
