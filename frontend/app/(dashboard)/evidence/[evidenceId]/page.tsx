import { PageHeader } from "@/components/layout/PageHeader";

interface EvidencePageProps {
  params: Promise<{ evidenceId: string }>;
}

export default async function EvidencePage({ params }: EvidencePageProps) {
  const { evidenceId } = await params;

  return (
    <div className="space-y-6">
      <PageHeader title="Evidence Review" description={evidenceId} />
      <p className="text-sm text-gray-500">
        EvidenceCard, EvidencePatchForm, and BilingualSpanView will be rendered here.
      </p>
    </div>
  );
}
