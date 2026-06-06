import { PageHeader } from "@/components/layout/PageHeader";

export default function GraphPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Knowledge Graph Explorer"
        description="Search the evidence knowledge graph by gene, variant, protein change, or disease."
      />
      <p className="text-sm text-gray-500">
        GraphSearchForm, GraphNodeList, GraphEdgeView, and GraphStatsPanel will be rendered here.
      </p>
    </div>
  );
}
