import { EvidenceReviewView } from "@/features/evidence";
import { PageHeader } from "@/components/layout/PageHeader";

interface EvidencePageProps {
  params: Promise<{ evidenceId: string }>;
}

export default async function EvidencePage({ params }: EvidencePageProps) {
  const { evidenceId } = await params;

  return (
    <div className="space-y-6">
      <PageHeader title="Evidence Review" description={evidenceId} />
      <EvidenceReviewView evidenceId={evidenceId} />
    </div>
  );
}
