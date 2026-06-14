import { EvidenceSearchView } from "@/features/evidence-search";
import { BookOpen } from "lucide-react";

export default function EvidencePage() {
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-md shadow-primary-200">
          <BookOpen className="h-6 w-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Literature Evidence
          </h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Search and explore literature-level evidence by gene, variant, disease, or PMID.
          </p>
        </div>
      </div>

      <EvidenceSearchView />
    </div>
  );
}
