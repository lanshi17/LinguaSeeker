import { EvidenceSearchView } from "@/features/evidence-search";
import { PageHeader } from "@/components/layout/PageHeader";

export default function EvidencePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Evidence Search"
        description="Search evidence cards by gene, variant, disease, or PMID."
      />
      <EvidenceSearchView />
    </div>
  );
}
