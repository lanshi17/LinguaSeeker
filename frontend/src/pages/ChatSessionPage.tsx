import { useParams } from "react-router-dom";
import { ChatView } from "@/features/chat";
import { PageHeader } from "@/components/layout/PageHeader";
import { useI18n } from "@/lib/i18n";

export function ChatSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { t } = useI18n();
  return (
    <div style={{ display: "flex", minHeight: 0, flexDirection: "column", gap: 16 }}>
      <PageHeader title={t("chat.title")} description={`${t("chat.sessionLabel")}: ${sessionId}`} />
      <ChatView sessionId={sessionId} />
    </div>
  );
}
