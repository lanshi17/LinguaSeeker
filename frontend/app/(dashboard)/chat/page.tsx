import { PageHeader } from "@/components/layout/PageHeader";

export default function ChatPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Chat Sessions" />
      <p className="text-sm text-gray-500">
        ChatSessionList will be rendered here with a processingRunId from context.
      </p>
    </div>
  );
}
