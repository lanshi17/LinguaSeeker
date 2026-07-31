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
  Gene: { fill: "#4763d0", stroke: "#3149a8", size: 20 },
  Variant: { fill: "#4a9d5b", stroke: "#3a7d48", size: 18 },
  Disease: { fill: "#e0a326", stroke: "#b8831a", size: 18 },
  Phenotype: { fill: "#d95555", stroke: "#b23f3f", size: 18 },
  // Evidence documents bridge gene→variant→disease; render them small and
  // muted so the biomedical entities stay visually dominant.
  EvidenceDoc: { fill: "#9aa7bd", stroke: "#75839c", size: 12 },
  Evidence: { fill: "#4aa3c4", stroke: "#3982a0", size: 14 },
  Document: { fill: "#3a9270", stroke: "#2d7359", size: 14 },
  ProcessingRun: { fill: "#e08641", stroke: "#bd6c2e", size: 14 },
};

const UNKNOWN_THEME: NodeTheme = {
  fill: "#8c8c8c",
  stroke: "#6b6b6b",
  size: 16,
};

/**
 * Scale visual density to the graph size so both tiny triples and large
 * subgraphs stay readable. Small graphs (a handful of nodes) otherwise get
 * blown up by autoFit's zoom-in; large graphs get cramped. Returns a factor in
 * [0.55, 1] applied to node/label/spacing dimensions.
 */
interface GraphScale {
  nodeScale: number;
  labelFontSize: number;
  linkDistance: number;
  nodeSpacing: number;
  nodeStrength: number;
  maxZoom: number;
}

function computeScale(nodeCount: number): GraphScale {
  // Below this threshold the graph is sparse and needs no shrinking.
  const smallThreshold = 8;
  // Beyond this the graph is dense; clamp to the smallest visual footprint.
  const largeThreshold = 80;

  let nodeScale = 1;
  if (nodeCount > smallThreshold) {
    const t = Math.min(
      1,
      (nodeCount - smallThreshold) / (largeThreshold - smallThreshold),
    );
    // Interpolate from full size (1) down to a compact 0.55.
    nodeScale = 1 - 0.45 * t;
  }

  return {
    nodeScale,
    labelFontSize: Math.round(12 * (0.75 + 0.25 * nodeScale)),
    // Wider link distance + node spacing keep entities from clumping together.
    // The repulsive node force is intentionally mild (constant across sizes)
    // so small graphs don't collapse onto themselves.
    linkDistance: Math.round(220 + 220 * nodeScale),
    nodeSpacing: Math.round(120 + 120 * nodeScale),
    nodeStrength: -120,
    // Prevent tiny graphs from being zoomed in until the circles fill the view.
    // A 4-node graph otherwise gets fitView'd to ~3-4x zoom, making 30px
    // nodes look like 100px monsters.
    maxZoom: nodeCount <= smallThreshold ? 0.9 : 1.6,
  };
}

const FONT_FAMILY =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

/** Truncate long labels so nodes stay legible; full text lives in the tooltip. */
function truncateLabel(text: string, max = 18): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

/**
 * Map an edge's `evidence_count` property to a stroke width.
 *
 * Uses a logarithmic scale so a single piece of evidence still reads as a
 * visible line, while edges backed by hundreds of papers stay distinguishable
 * from the rest without dominating the canvas.
 */
const MIN_EDGE_WIDTH = 1;
const MAX_EDGE_WIDTH = 6;

function evidenceToEdgeWidth(evidenceCount: number | null | undefined): number {
  if (!evidenceCount || evidenceCount <= 0) return MIN_EDGE_WIDTH;
  // log10(1) = 0 → MIN; log10(1000) = 3 → MAX. Linear interpolation between.
  const logScale = Math.log10(evidenceCount);
  const ratio = Math.max(0, Math.min(1, logScale / 3));
  return MIN_EDGE_WIDTH + (MAX_EDGE_WIDTH - MIN_EDGE_WIDTH) * ratio;
}

function resolveTheme(labels: string[]): NodeTheme {
  const key = labels.find((label) => label in NODE_THEMES);
  return key ? NODE_THEMES[key] : UNKNOWN_THEME;
}

/**
 * Convert a backend rel_type + edge properties into a human-readable label.
 *
 * The backend now distinguishes ClinGen's `ASSOC_DEFINITIVE`/`ASSOC_LIMITED`
 * from dosage-sensitivity relationships and from the literature bridge's
 * gene→variant→disease edges, so the visualization can show the real
 * relationship instead of collapsing everything to "associated with".
 */
function formatEdgeLabel(relType: string, properties: Record<string, unknown> | undefined): string {
  const props = properties ?? {};
  const sourceDb = String(props.source_db ?? '').trim();
  const evidenceLevel = String(props.evidence_level ?? '').trim();
  const evidenceCount = Number(props.evidence_count ?? 0);
  

  if (relType === 'ASSOCIATED_WITH' || relType.startsWith('ASSOC_')) {
    const level = evidenceLevel || relType.replace(/^ASSOC_/, '').toLowerCase().replace(/_/g, ' ');
    return sourceDb ? `${level} (${sourceDb})` : level || 'associated with';
  }
  if (relType === 'HAS_DOSAGE_SENSITIVITY' || relType.startsWith('DOSAGE_')) {
    const level = evidenceLevel || relType.replace(/^DOSAGE_/, '').toLowerCase().replace(/_/g, ' ');
    return `dosage: ${level}`.trim();
  }
  if (relType === 'HAS_REPORTED_VARIANT') {
    if (evidenceCount > 0) return `reported variant · ${evidenceCount} ${evidenceCount === 1 ? 'paper' : 'papers'}`;
    return 'reported variant';
  }
  if (relType === 'LITERATURE_VARIANT_DISEASE') {
    if (evidenceCount > 0) return `variant → disease · ${evidenceCount} ${evidenceCount === 1 ? 'paper' : 'papers'}`;
    return 'variant in disease';
  }
  if (relType === 'LITERATURE_GENE_DISEASE') {
    if (evidenceCount > 0) return `gene → disease · ${evidenceCount} ${evidenceCount === 1 ? 'paper' : 'papers'}`;
    return 'gene–disease (literature)';
  }
  // Fallback: pretty-print the raw rel_type.
  return relType.toLowerCase().replace(/_/g, ' ');
}

/**
 * Map an edge's rel_type + evidence level to a stroke color so users can read
 * the relationship strength at a glance. ClinGen evidence levels follow the
 * canonical gene–disease validity ladder; dosage levels use a separate scale.
 * Literature edges fall back to a neutral tone scaled by evidence_count.
 */
const EDGE_COLORS = {
  // ClinGen gene–disease association: stronger evidence → warmer color.
  assoc: {
    definitive: "#b8350f", // strong red
    strong: "#d96436",
    moderate: "#e5a142",
    limited: "#d3b850",
    disputed: "#7d8aa1",
    refuted: "#6c6c6c",
    no_known_disease_relationship: "#9aa7bd",
  } as Record<string, string>,
  // ClinGen dosage sensitivity (haploinsufficiency/triplosensitivity ladder).
  dosage: {
    "sufficient_evidence_for_haploinsufficiency": "#b8350f",
    "gene_associated_with_autosomal_recessive_phenotype": "#d96436",
    "emerging_evidence_for_haploinsufficiency": "#e5a142",
    "little_evidence_for_haploinsufficiency": "#d3b850",
    "no_evidence_for_haploinsufficiency": "#7d8aa1",
    "dosage_sensitivity_unlikely_for_haploinsufficiency": "#6c6c6c",
  } as Record<string, string>,
  // Literature-derived edges get a neutral steel-blue that deepens with count.
  literature: {
    low: "#9aa7bd", // < 5 papers
    mid: "#5a7fb0", // 5–49
    high: "#3149a8", // 50+
  } as const,
  fallback: "#a3aab8",
} as const;

function resolveEdgeColor(relType: string, properties: Record<string, unknown> | undefined): string {
  const props = properties ?? {};
  const level = String(props.evidence_level ?? '').toLowerCase().replace(/[\s/-]+/g, '_');
  const count = Number(props.evidence_count ?? 0);
  if (relType.startsWith('ASSOC_')) {
    return EDGE_COLORS.assoc[level] ?? EDGE_COLORS.assoc.limited ?? EDGE_COLORS.fallback;
  }
  if (relType.startsWith('DOSAGE_')) {
    return EDGE_COLORS.dosage[level] ?? EDGE_COLORS.dosage.no_evidence_for_haploinsufficiency ?? EDGE_COLORS.fallback;
  }
  if (
    relType === 'HAS_REPORTED_VARIANT' ||
    relType === 'LITERATURE_VARIANT_DISEASE' ||
    relType === 'LITERATURE_GENE_DISEASE'
  ) {
    if (count >= 50) return EDGE_COLORS.literature.high;
    if (count >= 5) return EDGE_COLORS.literature.mid;
    return EDGE_COLORS.literature.low;
  }
  return EDGE_COLORS.fallback;
}

function buildG6Data(graph: KnowledgeGraph, scale: GraphScale): GraphData {
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
        size: Math.round(theme.size * scale.nodeScale),
        fill: theme.fill,
        stroke: theme.stroke,
        lineWidth: 2,
        labelText: isEvidenceDoc ? "" : truncateLabel(fullLabel),
        labelFill: "#1f2733",
        labelFontSize: scale.labelFontSize,
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
        // Color encodes the relationship's evidence strength so a ClinGen
        // "definitive" association reads as a warm red, while a literature
        // edge with one citation stays a neutral gray-blue.
        stroke: resolveEdgeColor(edge.rel_type, edge.properties as Record<string, unknown> | undefined),
        // Stroke width grows with `evidence_count` so a triple backed by
        // 100+ papers visibly outranks one backed by a single citation.
        lineWidth: evidenceToEdgeWidth(
          (edge.properties as Record<string, unknown> | undefined)?.evidence_count as number | undefined,
        ),
        endArrow: true,
        endArrowSize: 7,
        // Relationship labels are hidden by default to reduce clutter and
        // revealed on hover via the edge `active` state below.
        labelText: formatEdgeLabel(edge.rel_type, edge.properties as Record<string, unknown> | undefined),
        labelOpacity: 0.85,
        labelFontSize: 10,
        labelFill: "#5a6472",
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
  const scale = useMemo(() => computeScale(graph.nodes.length), [graph.nodes.length]);
  const legendEdges = useMemo(() => {
    const seen = new Map<string, { relType: string; color: string; label: string }>();
    for (const edge of graph.edges) {
      if (seen.has(edge.rel_type)) continue;
      const props = edge.properties as Record<string, unknown> | undefined;
      seen.set(edge.rel_type, {
        relType: edge.rel_type,
        color: resolveEdgeColor(edge.rel_type, props),
        label: formatEdgeLabel(edge.rel_type, props),
      });
    }
    return Array.from(seen.values());
  }, [graph]);

  useEffect(() => {
    if (!containerRef.current) return;

    let destroyed = false;

    const g6 = new Graph({
      container: containerRef.current,
      data: buildG6Data(graph, scale),
      layout: {
        type: "force",
        linkDistance: scale.linkDistance,
        nodeStrength: scale.nodeStrength,
        edgeStrength: 0.25,
        preventOverlap: true,
        nodeSpacing: scale.nodeSpacing,
        collideStrength: 2,
        alpha: 0.8,
        alphaDecay: 0.028,
      },
      node: {
        type: "circle",
        // Per-node style.size still wins, but this catches nodes without one
        // (and the G6 default 32 is what was making everything huge).
        style: { size: 18 },
        state: {
          hover: { lineWidth: 4, shadowColor: "rgba(0,0,0,0.2)", shadowBlur: 12 },
          inactive: { fillOpacity: 0.35, labelOpacity: 0.35 },
        },
      },
      edge: {
        state: {
          // Reveal the relationship label and emphasize the line on hover.
          active: {
            stroke: "#5a6472",
            lineWidth: 4,
            labelOpacity: 1,
            labelFontSize: 12,
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
      // Disable autoFit — the camera zoom was multiplying our 20px nodes to
      // 150px+ after fitView calculated a tiny bounding box. fitCenter alone
      // still scales up via the camera, so we keep zoom at 1 and let the
      // force layout's linkDistance do the spacing.
      autoFit: "center",
      zoom: 1,
      zoomRange: [0.2, scale.maxZoom],
      padding: 48,
    });

    if (onNodeClick) {
      g6.on("node:click", (event: unknown) => {
        const nodeEvent = event as { target: { id: string } };
        onNodeClick(nodeEvent.target.id);
      });
    }

    graphRef.current = g6;
    void g6.render().then(() => {
      // Debug: log actual element size attributes.

      if (destroyed && graphRef.current === g6) {
        graphRef.current = null;
        g6.destroy();
      }
    });

    return () => {
      destroyed = true;
      const ref = graphRef.current;
      graphRef.current = null;
      ref?.destroy();
    };
  }, [graph, scale, onNodeClick]);

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
      {legendEdges.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            display: "flex",
            flexDirection: "column",
            gap: 6,
            padding: "8px 12px",
            background: "rgba(255, 255, 255, 0.9)",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            fontSize: 12,
            fontFamily: FONT_FAMILY,
            color: "var(--color-text-secondary)",
            boxShadow: "0 1px 3px rgba(0, 0, 0, 0.08)",
            maxWidth: 320,
          }}
        >
          <span style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>
            Edge meaning
          </span>
          {legendEdges.map((edge) => (
            <span
              key={edge.relType}
              style={{ display: "flex", alignItems: "center", gap: 8 }}
              title={edge.relType}
            >
              <span
                style={{
                  display: "inline-block",
                  width: 22,
                  height: 3,
                  borderRadius: 2,
                  background: edge.color,
                  flexShrink: 0,
                }}
              />
              <span style={{ flex: 1 }}>{edge.label}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
