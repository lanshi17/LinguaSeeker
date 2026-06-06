import { PipelineSubmitForm } from "@/features/pipeline";
import { PageHeader } from "@/components/layout/PageHeader";

export default function PipelinePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="New Pipeline Run"
        description="Submit a document or search query to start the evidence extraction pipeline."
      />
      <PipelineSubmitForm />
    </div>
  );
}
