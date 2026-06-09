import { redirect } from "next/navigation";
import { EvidenceDetailView } from "@/features/evidence-search";
import { PageHeader } from "@/components/layout/PageHeader";

interface EvidenceDetailPageProps {
  searchParams: Promise<{
    evidenceId?: string;
    groupId?: string;
    view?: string;
  }>;
}

export default async function EvidenceDetailPage({ searchParams }: EvidenceDetailPageProps) {
  const { evidenceId, groupId, view } = await searchParams;

  if (!groupId) {
    redirect("/evidence");
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={view === "compare" ? "Bilingual Evidence" : "Literature Detail"}
        description={
          view === "compare"
            ? "Read original and English full-text evidence side by side with category highlight controls."
            : "Review literature metadata, evidence distribution, and extracted fields."
        }
      />
      <EvidenceDetailView
        groupId={groupId}
        initialEvidenceId={evidenceId}
        initialView={view === "compare" ? "compare" : "overview"}
      />
    </div>
  );
}
