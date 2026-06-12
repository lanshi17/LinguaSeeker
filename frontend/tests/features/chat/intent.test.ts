import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  detectChatActionIntent,
  type ChatActionIntent,
} from "../../../src/features/chat/utils/intent";

describe("chat action intent detection", () => {
  it("opens the literature extraction form for Chinese extraction requests", () => {
    const intent: ChatActionIntent = detectChatActionIntent(
      "我想做文献的证据提取",
    );

    assert.equal(intent, "start-pipeline");
  });

  it("opens the PDF upload form for upload requests", () => {
    assert.equal(detectChatActionIntent("上传 PDF 做文献提取"), "upload-pdf");
  });

  it("routes database lookup requests to evidence search", () => {
    assert.equal(detectChatActionIntent("我想查询数据库里的已有证据"), "search-evidence");
  });

  it("keeps unrelated conversational messages in chat", () => {
    assert.equal(detectChatActionIntent("hi"), "chat");
  });
});
