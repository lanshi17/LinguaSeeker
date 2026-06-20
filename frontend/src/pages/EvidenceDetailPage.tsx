import { useSearchParams, Navigate } from "react-router-dom";
import { EvidenceDetailView } from "@/features/evidence-search";
import { BookOpen, Columns2 } from "lucide-react";

export function EvidenceDetailPage() {
  const [searchParams] = useSearchParams();
  const evidenceId = searchParams.get("evidenceId") ?? undefined;
  const groupId = searchParams.get("groupId");
  const view = searchParams.get("view");

  if (!groupId) {
    return <Navigate to="/evidence" replace />;
  }

  const isCompareView = view === "compare";

  return (
    <div className="space-y-6">
      {/* Page header with icon */}
      <div className="flex items-center gap-4">
        <div
          className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl shadow-md ${
            isCompareView
              ? "bg-gradient-to-br from-purple-500 to-purple-700 shadow-purple-200"
              : "bg-gradient-to-br from-primary-500 to-primary-700 shadow-primary-200"
          }`}
        >
          {isCompareView ? (
            <Columns2 className="h-6 w-6 text-white" />
          ) : (
            <BookOpen className="h-6 w-6 text-white" />
          )}
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            {isCompareView ? "Bilingual Evidence" : "Literature Detail"}
          </h1>
          <p className="mt-0.5 text-sm text-gray-500">
            {isCompareView
              ? "Read original and English full-text evidence side by side with category highlight controls."
              : "Review literature metadata, evidence distribution, and extracted fields."}
          </p>
        </div>
      </div>

      <EvidenceDetailView
        groupId={groupId}
        initialEvidenceId={evidenceId}
        initialView={isCompareView ? "compare" : "overview"}
      />
    </div>
  );
}
