import { useParams } from "react-router-dom";
import { PipelineStatusView } from "@/features/pipeline";

export function PipelineRunPage() {
  const { runId } = useParams<{ runId: string }>();
  return (
    <div className="space-y-6">
      <PipelineStatusView runId={runId!} />
    </div>
  );
}
