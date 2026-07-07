import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { XProvider, Bubble, Sender } from "@ant-design/x";
import type { BubbleItemType } from "@ant-design/x";
import type { SenderRef } from "@ant-design/x/es/sender/interface";
import { useXChat } from "@ant-design/x-sdk";
import type { MessageInfo } from "@ant-design/x-sdk/es/x-chat";
import { App, Button, Tooltip, Upload as AntdUpload } from "antd";
import { Upload as UploadIcon } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { extractErrorMessage } from "@/lib/api/error";
import { startPipelineRun } from "@/features/pipeline/services/pipeline";
import {
  createAcmgChatProvider,
  sendChatMessage,
} from "../providers/acmgChatProvider";
import { listMessages } from "../services/chat";
import {
  toUniqueChatMessageKeys,
  toXChatDefaultMessages,
  type ChatBubbleMessage,
} from "../utils/messageHistory";
import { ChatMarkdown } from "../utils/markdown";
import { ThinkingIndicator } from "./ThinkingIndicator";
import { WelcomeBlock, type WelcomeAction } from "./WelcomeBlock";
import { roles } from "./chatConfig";
import {
  ChatUploadTaskCard,
  isPdfFile,
  readFileAsBase64,
  type PipelineSummarySlots,
} from "./forms";

export function SingleSessionChat({ sessionId }: { sessionId: string }) {
  const { t } = useI18n();
  const { message } = App.useApp();
  const provider = useMemo(
    () => createAcmgChatProvider(sessionId),
    [sessionId],
  );

  const xChat = useXChat({
    provider,
    conversationKey: sessionId,
    defaultMessages: async () => [], // Start empty, load in useEffect
  });

  // Guard against undefined returns from useXChat
  const messages = useMemo(() => xChat?.messages ?? [], [xChat?.messages]);
  const onRequest = xChat?.onRequest;
  const isRequesting = xChat?.isRequesting ?? false;
  const abort = xChat?.abort;
  const setMessages = xChat?.setMessages;
  const onRequestRef = useRef(onRequest);
  const setMessagesRef = useRef(setMessages);
  onRequestRef.current = onRequest;
  setMessagesRef.current = setMessages;
  const [uploadSlots, setUploadSlots] = useState<PipelineSummarySlots | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadSubmitting, setUploadSubmitting] = useState(false);
  const [isPreparingResponse, setIsPreparingResponse] = useState(false);

  // Explicit message hydration on mount (same pattern as FullChatView).
  // Also aborts any in-flight stream when sessionId changes or on unmount.
  // `provider` is stable (memoized on sessionId) so the cleanup closure
  // captures the correct instance for each session.
  useEffect(() => {
    let cancelled = false;

    setMessagesRef.current?.([]);

    listMessages(sessionId)
      .then((history) => {
        if (cancelled) return;
        setMessagesRef.current?.(
          toXChatDefaultMessages(history) as MessageInfo<ChatBubbleMessage>[],
        );
      })
      .catch(() => {
        if (cancelled) return;
        setMessagesRef.current?.([]);
      });

    return () => {
      cancelled = true;
      // Abort the SSE stream when the single-session view unmounts
      // (e.g. user navigates away, or sessionId changes).
      try {
        provider.abort();
      } catch {
        // No-op on unmount — best-effort cleanup.
      }
    };
  }, [sessionId, provider]);

  const handleQuickAction = useCallback(
    (action: WelcomeAction) => {
      const task = (async () => {
        try {
          setIsPreparingResponse(true);
          await sendChatMessage(sessionId, action.message);
          // Use onRequest to properly manage useXChat state
          if (onRequestRef.current) {
            onRequestRef.current({
              messages: [{ role: "user" as const, content: action.message }],
            });
          }
        } catch (err) {
          message.error(extractErrorMessage(err, "Failed to send message"));
        } finally {
          setIsPreparingResponse(false);
        }
      })();
      void task;
    },
    [message, sessionId],
  );

  const openUploadTask = useCallback((file: File | null) => {
    setUploadSlots({
      source_type: "local",
      ...(file ? { filename: file.name } : {}),
    });
    setUploadFile(file);
  }, []);

  const handleSenderPdfUpload = useCallback(
    (file: File) => {
      if (!isPdfFile(file)) {
        void message.error(t("pipeline.error.pdfOnly"));
        return AntdUpload.LIST_IGNORE;
      }
      openUploadTask(file);
      return false;
    },
    [message, openUploadTask, t],
  );

  const handlePasteFile = useCallback(
    (files: FileList) => {
      const file = Array.from(files).find(isPdfFile);
      if (!file) {
        void message.error(t("pipeline.error.pdfOnly"));
        return;
      }
      openUploadTask(file);
    },
    [message, openUploadTask, t],
  );

  const handleUploadSubmit = useCallback(
    async (slots: PipelineSummarySlots, file: File) => {
      try {
        setUploadSubmitting(true);
        const response = await startPipelineRun({
          source_type: "local",
          mode: "full",
          filename: file.name,
          content_base64: await readFileAsBase64(file),
          ...(slots.gene_symbol || slots.disease_name || slots.variant_hgvs_p
            ? {
                target: {
                  gene_symbol: slots.gene_symbol || undefined,
                  disease_name: slots.disease_name || undefined,
                  variant_hgvs_p: slots.variant_hgvs_p || undefined,
                },
              }
            : {}),
        });
        setUploadSlots(null);
        setUploadFile(null);
        message.success(
          `"${file.name}" — pipeline started (${response.processing_run_id.slice(0, 8)}...)`,
        );
      } catch (err) {
        message.error(
          `Failed to start pipeline: ${extractErrorMessage(err)}`,
        );
      } finally {
        setUploadSubmitting(false);
      }
    },
    [message],
  );

  const bubbleItems = useMemo(() => {
    const messageKeys = toUniqueChatMessageKeys(messages);
    const items: BubbleItemType[] = messages.map(({ message, status }, index) => {
      const isLoadingEmpty =
        (status === "loading" || status === "updating") && !message.content;
      const isStreaming =
        !isLoadingEmpty &&
        (status === "loading" || status === "updating") &&
        Boolean(message.content);

      return {
        key: messageKeys[index],
        role: message.role,
        content: message.content,
        streaming: false,
        loading: false,
        ...(message.role === "assistant"
          ? {
              contentRender: (content: string) => {
                if (isLoadingEmpty) {
                  return <ThinkingIndicator />;
                }
                return (
                  <div className={isStreaming ? "chat-streaming-cursor" : ""}>
                    <ChatMarkdown source={content} />
                  </div>
                );
              },
            }
          : {}),
      };
    });

    if (uploadSlots) {
      items.push({
        key: "__upload__",
        role: "assistant",
        content: "",
        streaming: false,
        loading: false,
        variant: "borderless",
        contentRender: () => (
          <ChatUploadTaskCard
            slots={uploadSlots}
            initialFile={uploadFile}
            onSubmit={handleUploadSubmit}
            onCancel={() => {
              setUploadSlots(null);
              setUploadFile(null);
            }}
            isSubmitting={uploadSubmitting}
          />
        ),
      });
    }

    if (isPreparingResponse && !isRequesting) {
      items.push({
        key: "__preparing_response__",
        role: "assistant",
        content: "",
        streaming: false,
        loading: false,
        contentRender: () => (
          <ThinkingIndicator
            label={t("chat.thinking.connectingLabel")}
            hints={[
              t("chat.thinking.saving"),
              t("chat.thinking.openingStream"),
            ]}
          />
        ),
      });
    }

    if (items.length === 0) {
      items.unshift({
        key: "__welcome__",
        role: "assistant",
        content: "",
        streaming: false,
        loading: false,
        variant: "borderless",
        contentRender: () => <WelcomeBlock onPick={handleQuickAction} />,
      });
    }

    return items;
  }, [
    handleQuickAction,
    handleUploadSubmit,
    isPreparingResponse,
    isRequesting,
    messages,
    t,
    uploadFile,
    uploadSlots,
    uploadSubmitting,
  ]);

  const senderRef = useRef<SenderRef>(null);
  const handleSingleSessionSubmit = useCallback(
    (val: string) => {
      const trimmed = val.trim();
      if (!trimmed) return;
      const task = (async () => {
        try {
          setIsPreparingResponse(true);
          await sendChatMessage(sessionId, trimmed);
          if (onRequestRef.current) {
            onRequestRef.current({
              messages: [{ role: "user" as const, content: trimmed }],
            });
          } else {
            // onRequest should always be defined in the current architecture
          }
      } catch (err) {
        message.error(extractErrorMessage(err, "Failed to send message"));
      } finally {
        setIsPreparingResponse(false);
      }
      })();
      void task.finally(() => senderRef.current?.clear());
    },
    [message, sessionId],
  );


  return (
    <XProvider>
      <div style={{ display: "flex", height: "100%", flexDirection: "column", overflow: "hidden", backgroundColor: "var(--color-surface)" }}>
        <Bubble.List
          style={{ flex: 1, overflow: "auto", padding: 16 }}
          items={bubbleItems}
          role={roles}
          autoScroll
        />

        <Sender
          ref={senderRef}
          style={{ borderTop: "1px solid var(--color-bg-muted)", padding: 16 }}
          loading={isRequesting || isPreparingResponse}
          onCancel={() => {
            // Cancel via the provider's own AbortController for
            // reliable fetch termination. Also try the SDK's abort
            // as a secondary cleanup for internal state.
            try {
              provider.abort();
            } catch {
                // noop
            }
            try {
              abort?.();
            } catch {
                // noop
            }
          }}
          onSubmit={handleSingleSessionSubmit}
          onPasteFile={handlePasteFile}
          placeholder={t("chat.agentPlaceholder")}
          prefix={
            <Tooltip title={t("chat.upload.open")}>
              <AntdUpload
                accept="application/pdf,.pdf"
                maxCount={1}
                showUploadList={false}
                beforeUpload={handleSenderPdfUpload}
                disabled={isRequesting || isPreparingResponse || uploadSubmitting}
              >
                <Button
                  type="text"
                  size="small"
                  icon={<UploadIcon size={16} />}
                  aria-label={t("chat.upload.open")}
                  disabled={isRequesting || isPreparingResponse || uploadSubmitting}
                />
              </AntdUpload>
            </Tooltip>
          }
        />
      </div>
    </XProvider>
  );
}
