import { Graph, type GraphData } from "@antv/g6";
import { useEffect, useMemo, useRef } from "react";
import type { KnowledgeGraph } from "../types/graphRag";

interface KnowledgeGraphCanvasProps {
  graph: KnowledgeGraph;
  height?: number;
  onNodeClick?: (nodeId: string) => void;
}

/** Visual style for each entity type: fill and border. */
interface NodeTheme {
  fill: string;
  stroke: string;
  size: number;
}

const NODE_THEMES: Record<string, NodeTheme> = {
  Gene: { fill: "#4763d0", stroke: "#3149a8", size: 46 },
  Variant: { fill: "#4a9d5b", stroke: "#3a7d48", size: 40 },
  Disease: { fill: "#e0a326", stroke: "#b8831a", size: 40 },
  Phenotype: { fill: "#d95555", stroke: "#b23f3f", size: 40 },
  // Evidence documents bridge gene→variant→disease; render them small and
  // muted so the biomedical entities stay visually dominant.
  EvidenceDoc: { fill: "#9aa7bd", stroke: "#75839c", size: 22 },
  Evidence: { fill: "#4aa3c4", stroke: "#3982a0", size: 34 },
  Document: { fill: "#3a9270", stroke: "#2d7359", size: 34 },
  ProcessingRun: { fill: "#e08641", stroke: "#bd6c2e", size: 32 },
};

const UNKNOWN_THEME: NodeTheme = {
  fill: "#8c8c8c",
  stroke: "#6b6b6b",
  size: 36,
};

const FONT_FAMILY =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

/** Truncate long labels so nodes stay legible; full text lives in the tooltip. */
function truncateLabel(text: string, max = 18): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

function resolveTheme(labels: string[]): NodeTheme {
  const key = labels.find((label) => label in NODE_THEMES);
  return key ? NODE_THEMES[key] : UNKNOWN_THEME;
}

function buildG6Data(graph: KnowledgeGraph): GraphData {
  const nodes = graph.nodes.map((node) => {
    const theme = resolveTheme(node.labels);
    const isEvidenceDoc = node.labels.includes("EvidenceDoc");
    // Evidence docs are identified by opaque UUIDs; show a compact marker
    // instead of the raw id so the bridge nodes don't dominate with noise.
    const fullLabel = isEvidenceDoc
      ? "evidence"
      : node.display_name || node.node_id;
    return {
      id: node.node_id,
      data: {
        label: fullLabel,
        type: node.labels.find((label) => label in NODE_THEMES) ?? "Unknown",
        ...node.properties,
      },
      style: {
        size: theme.size,
        fill: theme.fill,
        stroke: theme.stroke,
        lineWidth: 2,
        labelText: isEvidenceDoc ? "" : truncateLabel(fullLabel),
        labelFill: "#1f2733",
        labelFontSize: 12,
        labelFontWeight: 600,
        labelFontFamily: FONT_FAMILY,
        labelPlacement: "bottom" as const,
        labelBackground: true,
        labelBackgroundFill: "rgba(255, 255, 255, 0.92)",
        labelBackgroundStroke: theme.stroke,
        labelBackgroundLineWidth: 1,
        labelBackgroundRadius: 4,
        labelPadding: [2, 6],
        labelMaxWidth: 140,
      },
    };
  });

  // Collapse duplicate / bidirectional edges: the backend often returns both
  // A→B and B→A for the same relationship, which stacks lines and labels and
  // makes the graph look dense. Keep one edge per (unordered pair + rel_type).
  const seenEdges = new Set<string>();
  const edges: GraphData["edges"] = [];
  graph.edges.forEach((edge, index) => {
    const pairKey = [edge.source_id, edge.target_id]
      .sort()
      .concat(edge.rel_type)
      .join("::");
    if (seenEdges.has(pairKey)) return;
    seenEdges.add(pairKey);
    edges.push({
      id: `edge-${index}`,
      source: edge.source_id,
      target: edge.target_id,
      data: {
        label: edge.rel_type,
        ...edge.properties,
      },
      style: {
        stroke: "#d3d8e0",
        lineWidth: 1.5,
        endArrow: true,
        endArrowSize: 7,
        // Relationship labels are hidden by default to reduce clutter and
        // revealed on hover via the edge `active` state below.
        labelText: edge.rel_type.replace(/_/g, " ").toLowerCase(),
        labelOpacity: 0,
        labelFill: "#5a6472",
        labelFontSize: 10,
        labelFontFamily: FONT_FAMILY,
        labelBackground: true,
        labelBackgroundFill: "rgba(249, 250, 251, 0.95)",
        labelBackgroundRadius: 3,
        labelPadding: [1, 4],
        labelAutoRotate: true,
      },
    });
  });

  return { nodes, edges };
}

/** Human-friendly legend labels for entity types. */
const TYPE_LABELS: Record<string, string> = {
  EvidenceDoc: "Evidence",
};

/** Distinct entity types present in the graph, for the legend. */
function usedTypes(graph: KnowledgeGraph): string[] {
  const seen = new Set<string>();
  for (const node of graph.nodes) {
    const key = node.labels.find((label) => label in NODE_THEMES);
    if (key) seen.add(key);
  }
  return Array.from(seen);
}

export function KnowledgeGraphCanvas({
  graph,
  height = 500,
  onNodeClick,
}: KnowledgeGraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const legendTypes = useMemo(() => usedTypes(graph), [graph]);

  useEffect(() => {
    if (!containerRef.current) return;

    let destroyed = false;

    const g6 = new Graph({
      container: containerRef.current,
      data: buildG6Data(graph),
      layout: {
        type: "force",
        linkDistance: 220,
        nodeStrength: -400,
        edgeStrength: 0.4,
        preventOverlap: true,
        nodeSpacing: 60,
        collideStrength: 1,
      },
      node: {
        state: {
          hover: { lineWidth: 4, shadowColor: "rgba(0,0,0,0.2)", shadowBlur: 12 },
          inactive: { fillOpacity: 0.35, labelOpacity: 0.35 },
        },
      },
      edge: {
        state: {
          // Reveal the relationship label and emphasize the line on hover.
          active: {
            stroke: "#8a94a6",
            lineWidth: 2.5,
            labelOpacity: 1,
          },
          inactive: { strokeOpacity: 0.25, labelOpacity: 0 },
        },
      },
      behaviors: [
        "drag-canvas",
        "zoom-canvas",
        "drag-element",
        { type: "hover-activate", degree: 1 },
      ],
      autoFit: "view",
      padding: 32,
    });

    if (onNodeClick) {
      g6.on("node:click", (event: unknown) => {
        const nodeEvent = event as { target: { id: string } };
        onNodeClick(nodeEvent.target.id);
      });
    }

    graphRef.current = g6;
    void g6.render().then(() => {
      // Guard against an unmount that raced ahead of the async render.
      if (destroyed) g6.destroy();
    });

    return () => {
      destroyed = true;
      g6.destroy();
      graphRef.current = null;
    };
  }, [graph, onNodeClick]);

  return (
    <div style={{ position: "relative" }}>
      <div
        ref={containerRef}
        style={{
          width: "100%",
          height,
          border: "1px solid var(--color-border)",
          borderRadius: 8,
          background:
            "radial-gradient(circle at 50% 40%, #ffffff 0%, #f6f8fb 100%)",
        }}
      />
      {legendTypes.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: 12,
            left: 12,
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            padding: "8px 12px",
            background: "rgba(255, 255, 255, 0.9)",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            fontSize: 12,
            fontFamily: FONT_FAMILY,
            color: "var(--color-text-secondary)",
            boxShadow: "0 1px 3px rgba(0, 0, 0, 0.08)",
          }}
        >
          {legendTypes.map((type) => (
            <span
              key={type}
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              <span
                style={{
                  display: "inline-block",
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  background: NODE_THEMES[type].fill,
                  border: `1.5px solid ${NODE_THEMES[type].stroke}`,
                }}
              />
              {TYPE_LABELS[type] ?? type}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
