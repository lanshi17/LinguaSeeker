import { ChatView } from "@/features/chat";
import { PageHeader } from "@/components/layout/PageHeader";

export default function ChatPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Chat Sessions" />
      <ChatView />
    </div>
  );
}
