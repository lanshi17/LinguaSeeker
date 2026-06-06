import { LiteratureSelectorView } from "@/features/literature";
import { PageHeader } from "@/components/layout/PageHeader";

export default function LiteratureCandidatesPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Literature Candidates"
        description="Search and select papers for evidence extraction."
      />
      <LiteratureSelectorView />
    </div>
  );
}
