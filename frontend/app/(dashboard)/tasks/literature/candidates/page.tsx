import { PageHeader } from "@/components/layout/PageHeader";

export default function LiteratureCandidatesPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Literature Candidates"
        description="Select papers from the search results for processing."
      />
      <p className="text-sm text-gray-500">
        LiteratureCandidateList and SelectionToolbar will be rendered here.
      </p>
    </div>
  );
}
