import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { appendAssistantChunk } from "../../../src/features/chat/utils/sse";

describe("chat SSE utilities", () => {
  it("appends text chunks from backend JSON SSE data", () => {
    const first = appendAssistantChunk(undefined, {
      data: JSON.stringify({ type: "text", content: "Hello " }),
    });
    const second = appendAssistantChunk(first, {
      data: JSON.stringify({ type: "text", content: "world" }),
    });

    assert.deepEqual(second, {
      role: "assistant",
      content: "Hello world",
    });
  });

  it("converts backend errors into assistant-visible text", () => {
    const message = appendAssistantChunk(undefined, {
      data: JSON.stringify({ type: "error", message: "LLM timeout" }),
    });

    assert.deepEqual(message, {
      role: "assistant",
      content: "[Error] LLM timeout",
    });
  });
});
