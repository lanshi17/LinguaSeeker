import { GraphExplorerView } from "@/features/graph";
import { PageHeader } from "@/components/layout/PageHeader";

export default function GraphPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Knowledge Graph Explorer"
        description="Search the evidence knowledge graph by gene, variant, protein change, or disease."
      />
      <GraphExplorerView />
    </div>
  );
}
