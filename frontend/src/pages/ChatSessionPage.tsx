import { useParams } from "react-router-dom";
import { ChatView } from "@/features/chat";
import { PageHeader } from "@/components/layout/PageHeader";

export function ChatSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  return (
    <div style={{ display: "flex", minHeight: 0, flexDirection: "column", gap: 16 }}>
      <PageHeader title="Chat" description={`Session: ${sessionId}`} />
      <ChatView sessionId={sessionId} />
    </div>
  );
}
