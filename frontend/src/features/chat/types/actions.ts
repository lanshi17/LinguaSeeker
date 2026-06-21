/**
 * Discriminated union for chat agent actions. The backend's
 * ReasoningLLMProvider emits one alongside the free-text reply,
 * signalling what the agent intends to do and the collected slots.
 *
 * Adding a new intent: add the case to ChatActionIntent, add a
 * matching entry to CHAT_PROMPTS, and add a handler in
 * ChatView.handleAction — the three sites must stay in sync.
 */

export type ChatActionIntent =
  | "start-pipeline"
  | "upload-pdf"
  | "search-evidence"
  | "classify-variant"
  | "interpret-evidence"
  | "review-changes"
  | "check-pipeline-status";

export interface ChatAction {
  intent: ChatActionIntent;
  slots: Record<string, string | undefined>;
}

export interface ChatActionBubbleSlots {
  startPipeline?: { sourceType?: "online" | "local"; query?: string };
  uploadPdf?: { sourceType?: "local" };
  searchEvidence?: {
    gene?: string;
    variant?: string;
    disease?: string;
    pmid?: string;
    doi?: string;
  };
  classifyVariant?: { variant?: string };
  interpretEvidence?: { evidenceId?: string };
  reviewChanges?: { filter?: "awaiting_review" | "all" };
}
