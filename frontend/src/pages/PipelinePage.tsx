import { PipelineSubmitForm } from "@/features/pipeline";
import { RunHistory } from "@/features/pipeline";
import { PageHeader } from "@/components/layout/PageHeader";

export function PipelinePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="New Pipeline Run"
        description="Submit a document or search query to start the evidence extraction pipeline."
      />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <PipelineSubmitForm />
        <RunHistory />
      </div>
    </div>
  );
}
