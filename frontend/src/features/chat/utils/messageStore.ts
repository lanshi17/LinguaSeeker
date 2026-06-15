import { chatMessagesStoreHelper } from "@ant-design/x-sdk/es/x-chat/store";

/**
 * Drop the cached ChatMessagesStore for a single conversation key.
 *
 * The x-sdk keeps every conversation's messages in a module-level Map
 * for the lifetime of the tab. When we delete a session we must also
 * drop the cached store, otherwise a stale entry lingers in memory.
 *
 * NOTE: Do NOT call this on normal session switches — the SDK reuses
 * the active store and destroying it mid-flight breaks hydration.
 * Only call on session deletion.
 */
export function clearCachedMessageStore(
  conversationKey: string | undefined,
): void {
  if (!conversationKey) return;
  const store = chatMessagesStoreHelper.get(conversationKey);
  if (!store) return;
  if (typeof store.setMessages === "function") {
    store.setMessages([]);
  }
  if (typeof store.destroy === "function") {
    store.destroy();
  }
  chatMessagesStoreHelper.delete(conversationKey);
}
