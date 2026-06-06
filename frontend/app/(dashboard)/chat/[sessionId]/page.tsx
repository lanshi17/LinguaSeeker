import { PageHeader } from "@/components/layout/PageHeader";

interface ChatSessionPageProps {
  params: Promise<{ sessionId: string }>;
}

export default async function ChatSessionPage({
  params,
}: ChatSessionPageProps) {
  const { sessionId } = await params;

  return (
    <div className="space-y-6">
      <PageHeader title="Chat" description={`Session: ${sessionId}`} />
      <p className="text-sm text-gray-500">
        ChatMessageList and ChatComposer will be rendered here.
      </p>
    </div>
  );
}
