import { useParams } from "react-router-dom";
import { PipelineStatusView } from "@/features/pipeline";

export function PipelineRunPage() {
  const { runId } = useParams<{ runId: string }>();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <PipelineStatusView runId={runId!} />
    </div>
  );
}
