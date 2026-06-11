import { ChatView } from "@/features/chat";
import { PageHeader } from "@/components/layout/PageHeader";

export default function ChatPage() {
  return (
    <div className="flex min-h-0 flex-col gap-4">
      <PageHeader title="Chat Sessions" />
      <ChatView />
    </div>
  );
}
