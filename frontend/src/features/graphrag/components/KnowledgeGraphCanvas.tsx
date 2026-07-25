import { Graph, type GraphData } from "@antv/g6";
import { useEffect, useRef } from "react";
import type { KnowledgeGraph } from "../types/graphRag";

interface KnowledgeGraphCanvasProps {
  graph: KnowledgeGraph;
  height?: number;
  onNodeClick?: (nodeId: string) => void;
}

const COLOR_MAP: Record<string, string> = {
  Gene: "#5470c6",
  Variant: "#91cc75",
  Disease: "#fac858",
  Phenotype: "#ee6666",
  Evidence: "#73c0de",
  Document: "#3ba272",
  ProcessingRun: "#fc8452",
};

function buildG6Data(graph: KnowledgeGraph): GraphData {
  const nodes = graph.nodes.map((node) => {
    const type = node.labels.find((label) => label in COLOR_MAP) ?? "Unknown";
    return {
      id: node.node_id,
      data: {
        label: node.display_name || node.node_id,
        type,
        ...node.properties,
      },
      style: {
        fill: COLOR_MAP[type] ?? "#999",
        labelText: node.display_name || node.node_id,
        labelFill: "#fff",
        labelBackground: true,
      },
    };
  });

  const edges = graph.edges.map((edge, index) => ({
    id: `edge-${index}`,
    source: edge.source_id,
    target: edge.target_id,
    data: {
      label: edge.rel_type,
      ...edge.properties,
    },
    style: {
      labelText: edge.rel_type,
      labelBackground: true,
      endArrow: true,
    },
  }));

  return { nodes, edges };
}

export function KnowledgeGraphCanvas({
  graph,
  height = 500,
  onNodeClick,
}: KnowledgeGraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const g6 = new Graph({
      container: containerRef.current,
      data: buildG6Data(graph),
      layout: {
        type: "force",
        linkDistance: 120,
        nodeStrength: -100,
        edgeStrength: 0.5,
        preventOverlap: true,
      },
      behaviors: ["drag-canvas", "zoom-canvas", "drag-element"],
      autoFit: "view",
    });

    if (onNodeClick) {
      g6.on("node:click", (event: unknown) => {
        const nodeEvent = event as { target: { id: string } };
        onNodeClick(nodeEvent.target.id);
      });
    }

    graphRef.current = g6;

    return () => {
      g6.destroy();
      graphRef.current = null;
    };
  }, [graph, onNodeClick]);

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height,
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        background: "var(--color-surface)",
      }}
    />
  );
}
