import type { EvidenceGraphEdge } from "../types/graph";

interface GraphEdgeViewProps {
  edges: EvidenceGraphEdge[];
}

export function GraphEdgeView({ edges }: GraphEdgeViewProps) {
  if (edges.length === 0) {
    return <p className="text-sm text-gray-500">No edges found.</p>;
  }

  return (
    <pre className="max-h-64 overflow-auto rounded bg-gray-50 p-3 text-xs text-gray-700">
      {JSON.stringify(edges, null, 2)}
    </pre>
  );
}
