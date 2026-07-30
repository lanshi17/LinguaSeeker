/**
 * Discriminated union for chat agent actions. The backend's
 * ReasoningLLMProvider emits one alongside the free-text reply,
 * signalling what the agent intends to do and the collected slots.
 *
 * Adding a new intent: add the case to ChatActionIntent, add a
 * matching entry to CHAT_PROMPTS, and add a handler in
 * ChatView.handleAction — the three sites must stay in sync.
 *
 * "graph-qa" is a read-only intent auto-dispatched on arrival: the frontend
 * queries the knowledge graph and renders the grounded answer inline instead
 * of navigating.
 */

export type ChatActionIntent =
  | "confirm-pipeline"
  | "start-pipeline" // deprecated: LLM must no longer emit; kept for back-compat with persisted messages
  | "upload-pdf" // deprecated: LLM must no longer emit; kept for back-compat with persisted messages
  | "search-evidence"
  | "classify-variant"
  | "interpret-evidence"
  | "review-changes"
  | "check-pipeline-status"
  | "graph-qa";

export interface ChatAction {
  intent: ChatActionIntent;
  slots: Record<string, string | undefined>;
}
