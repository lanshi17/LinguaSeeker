import { useCallback } from "react";
import { App } from "antd";
import { extractErrorMessage } from "@/lib/api/error";
import { getPipelineStatus, startPipelineRun } from "@/features/pipeline/services/pipeline";
import type { PipelineRunRequest } from "@/features/pipeline/types/pipeline";
import type { createAcmgChatProvider } from "../providers/acmgChatProvider";
import type { PipelineSummarySlots } from "./forms";
import type { PerSessionUIState } from "./chatConfig";
import type { ChatActionIntent } from "../types/actions";

interface UsePipelineActionsParams {
  activeProvider: ReturnType<typeof createAcmgChatProvider> | undefined;
  onRequest:
    | ((params: {
        messages: { role: "user" | "assistant"; content: string }[];
      }) => void)
    | undefined;
  setActiveForm: (intent: ChatActionIntent | null) => void;
  setPipelineStatus: (
    status:
      | PerSessionUIState["pipelineStatus"]
      | ((
          prev: PerSessionUIState["pipelineStatus"],
        ) => PerSessionUIState["pipelineStatus"]),
  ) => void;
}

/**
 * Pipeline-specific actions: polling run status from the backend
 * and submitting the pipeline confirm form to start a new run.
 */
export function usePipelineActions({
  activeProvider,
  onRequest,
  setActiveForm,
  setPipelineStatus,
}: UsePipelineActionsParams) {
  const { message } = App.useApp();
  const pollPipelineStatus = useCallback(
    async (runId: string) => {
      const TERMINAL = new Set(["completed", "failed", "cancelled"]);
      const MAX_POLL_MS = 30 * 60 * 1000; // 30 min safety cap
      const startedAt = Date.now();
      let consecutiveErrors = 0;

      const poll = async () => {
        try {
          const data = await getPipelineStatus(runId);
          consecutiveErrors = 0;
          setPipelineStatus({
            runId,
            status: data.pipeline_status,
            phases: data.phases,
          });
          if (
            !TERMINAL.has(data.pipeline_status) &&
            Date.now() - startedAt < MAX_POLL_MS
          ) {
            setTimeout(poll, 2000);
          }
        } catch {
          consecutiveErrors++;
          if (consecutiveErrors < 10 && Date.now() - startedAt < MAX_POLL_MS) {
            setTimeout(poll, 2000);
          }
        }
      };
      setTimeout(poll, 1000);
    },
    [setPipelineStatus],
  );

  const handlePipelineConfirm = useCallback(
    async (slots: PipelineSummarySlots) => {
      setActiveForm(null);
      try {
        const body: PipelineRunRequest = {
          source_type: (slots.source_type ?? "online") as "online" | "local",
          mode: "full",
          ...(slots.source_type !== "local" && slots.query ? { query: slots.query } : {}),
          ...(slots.source_type !== "local" && slots.identifiers
            ? { identifiers: slots.identifiers.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean) }
            : {}),
          ...(slots.gene_symbol || slots.disease_name || slots.variant_hgvs_p
            ? {
                target: {
                  gene_symbol: slots.gene_symbol || undefined,
                  disease_name: slots.disease_name || undefined,
                  variant_hgvs_p: slots.variant_hgvs_p || undefined,
                },
              }
            : {}),
        };
        const response = await startPipelineRun(body);
        const runId = response.processing_run_id;
        setPipelineStatus({ runId, status: response.status });
        if (activeProvider) {
          onRequest?.({
            messages: [
              {
                role: "assistant" as const,
                content: `Pipeline started. Run ID: ${runId.slice(0, 8)}...`,
              },
            ],
          });
        }
        pollPipelineStatus(runId);
      } catch (err: unknown) {
        message.error(
          `Failed to start pipeline: ${extractErrorMessage(err)}`,
        );
      }
    },
    [
      activeProvider,
      message,
      onRequest,
      pollPipelineStatus,
      setActiveForm,
      setPipelineStatus,
    ],
  );

  return { pollPipelineStatus, handlePipelineConfirm };
}
