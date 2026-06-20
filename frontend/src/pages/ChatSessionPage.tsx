import { useParams } from "react-router-dom";
import { ChatView } from "@/features/chat";
import { PageHeader } from "@/components/layout/PageHeader";

export function ChatSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  return (
    <div className="flex min-h-0 flex-col gap-4">
      <PageHeader title="Chat" description={`Session: ${sessionId}`} />
      <ChatView sessionId={sessionId} />
    </div>
  );
}
