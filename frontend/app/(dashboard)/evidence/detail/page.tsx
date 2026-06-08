import { redirect } from "next/navigation";
import { EvidenceDetailView } from "@/features/evidence-search";
import { PageHeader } from "@/components/layout/PageHeader";

interface EvidenceDetailPageProps {
  searchParams: Promise<{ groupId?: string }>;
}

export default async function EvidenceDetailPage({ searchParams }: EvidenceDetailPageProps) {
  const { groupId } = await searchParams;

  if (!groupId) {
    redirect("/evidence");
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Evidence Detail"
        description="Review evidence distribution and bilingual traceability for this group."
      />
      <EvidenceDetailView groupId={groupId} />
    </div>
  );
}
