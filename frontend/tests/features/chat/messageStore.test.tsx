import { describe, expect, it, afterEach } from "vitest";
import { chatMessagesStoreHelper } from "@ant-design/x-sdk/es/x-chat/store";
import { clearCachedMessageStore } from "../../../src/features/chat/utils/messageStore";

// Access the internal map for test setup/verification.
function getInternalMap(): Map<string, Record<string, unknown>> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (chatMessagesStoreHelper as any)._chatMessagesStores;
}

afterEach(() => {
  const map = getInternalMap();
  map.clear();
});

describe("clearCachedMessageStore", () => {
  it("empties and removes a specific store", () => {
    const store = {
      destroyed: false,
      messages: [{ id: "1" }, { id: "2" }],
      setMessages(m: unknown[]) {
        this.messages = m as typeof this.messages;
      },
      destroy() {
        this.destroyed = true;
      },
    };
    getInternalMap().set("k1", store);

    clearCachedMessageStore("k1");

    expect(store.destroyed).toBe(true);
    expect(store.messages).toEqual([]);
    expect(chatMessagesStoreHelper.get("k1")).toBeUndefined();
  });

  it("is a no-op for unknown keys", () => {
    expect(() => clearCachedMessageStore("nope")).not.toThrow();
    expect(() => clearCachedMessageStore(undefined)).not.toThrow();
  });
});
