import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { EvidenceGraphNode } from "../types/graph";

interface GraphNodeListProps {
  nodes: EvidenceGraphNode[];
}

export function GraphNodeList({ nodes }: GraphNodeListProps) {
  if (nodes.length === 0) {
    return <p className="text-sm text-gray-500">No nodes found.</p>;
  }

  return (
    <div className="space-y-2">
      {nodes.map((node) => {
        const isDoc = node.node_id.startsWith("doc:");
        const docId = isDoc ? node.node_id.replace("doc:", "") : null;

        return (
          <Card key={node.node_id} className="flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-gray-900">
                {node.label}
              </span>
              <Badge variant="default" className="ml-2">
                {node.node_type}
              </Badge>
            </div>
            {docId && (
              <Link
                href={`/documents/${docId}`}
                className="text-xs text-primary-600 hover:underline"
              >
                Open document
              </Link>
            )}
          </Card>
        );
      })}
    </div>
  );
}
