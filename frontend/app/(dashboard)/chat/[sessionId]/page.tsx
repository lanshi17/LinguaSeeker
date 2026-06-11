import { ChatView } from "@/features/chat";
import { PageHeader } from "@/components/layout/PageHeader";

interface ChatSessionPageProps {
  params: Promise<{ sessionId: string }>;
}

export default async function ChatSessionPage({
  params,
}: ChatSessionPageProps) {
  const { sessionId } = await params;

  return (
    <div className="flex min-h-0 flex-col gap-4">
      <PageHeader title="Chat" description={`Session: ${sessionId}`} />
      <ChatView sessionId={sessionId} />
    </div>
  );
}
