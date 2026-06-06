import { PipelineStatusView } from "@/features/pipeline";

interface PipelineRunPageProps {
  params: Promise<{ runId: string }>;
}

export default async function PipelineRunPage({ params }: PipelineRunPageProps) {
  const { runId } = await params;

  return (
    <div className="space-y-6">
      <PipelineStatusView runId={runId} />
    </div>
  );
}
