import { PipelineStatusView } from "@/features/pipeline";
import { PageHeader } from "@/components/layout/PageHeader";

interface RequestMonitorPageProps {
  params: Promise<{ requestId: string }>;
}

export default async function RequestMonitorPage({
  params,
}: RequestMonitorPageProps) {
  const { requestId } = await params;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Request Monitor"
        description={`Request ID: ${requestId}`}
      />
      <PipelineStatusView runId={requestId} />
    </div>
  );
}
