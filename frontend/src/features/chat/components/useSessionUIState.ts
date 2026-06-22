import { useCallback, useState } from "react";
import type { ChatAction, ChatActionIntent } from "../types/actions";
import { type PerSessionUIState, createEmptySessionUI } from "./chatConfig";

/**
 * Manages per-session ephemeral UI state (active form, pipeline status,
 * dispatched actions). Each session gets its own isolated state slot.
 */
export function useSessionUIState(activeConversationKey: string | undefined) {
  const [sessionUI, setSessionUI] = useState<Record<string, PerSessionUIState>>(
    {},
  );

  const activeUI: PerSessionUIState = activeConversationKey
    ? (sessionUI[activeConversationKey] ?? createEmptySessionUI())
    : createEmptySessionUI();
  const { activeForm, activeFormSlots, dispatchedActions, pipelineStatus } =
    activeUI;

  const updateActiveUI = useCallback(
    (updater: (prev: PerSessionUIState) => PerSessionUIState) => {
      if (!activeConversationKey) return;
      const key = activeConversationKey;
      setSessionUI((prev) => ({
        ...prev,
        [key]: updater(prev[key] ?? createEmptySessionUI()),
      }));
    },
    [activeConversationKey],
  );

  const setActiveForm = useCallback(
    (intent: ChatActionIntent | null) =>
      updateActiveUI((p) => ({ ...p, activeForm: intent })),
    [updateActiveUI],
  );
  const setActiveFormSlots = useCallback(
    (slots: ChatAction["slots"] | null) =>
      updateActiveUI((p) => ({ ...p, activeFormSlots: slots })),
    [updateActiveUI],
  );
  const setPipelineStatus = useCallback(
    (
      status:
        | PerSessionUIState["pipelineStatus"]
        | ((
            prev: PerSessionUIState["pipelineStatus"],
          ) => PerSessionUIState["pipelineStatus"]),
    ) =>
      updateActiveUI((p) => ({
        ...p,
        pipelineStatus:
          typeof status === "function" ? status(p.pipelineStatus) : status,
      })),
    [updateActiveUI],
  );
  const setDispatchedActions = useCallback(
    (next: Set<string> | ((prev: Set<string>) => Set<string>)) =>
      updateActiveUI((p) => ({
        ...p,
        dispatchedActions:
          typeof next === "function" ? next(p.dispatchedActions) : next,
      })),
    [updateActiveUI],
  );

  const clearSessionUI = useCallback((sessionId: string) => {
    setSessionUI((prev) => {
      const next = { ...prev };
      delete next[sessionId];
      return next;
    });
  }, []);

  return {
    activeForm,
    activeFormSlots,
    dispatchedActions,
    pipelineStatus,
    setActiveForm,
    setActiveFormSlots,
    setPipelineStatus,
    setDispatchedActions,
    clearSessionUI,
  };
}
