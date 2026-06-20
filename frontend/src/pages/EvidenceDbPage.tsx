import { Database, Dna } from "lucide-react";
import { VariantIndexView } from "@/features/evidence-db";

export function EvidenceDbPage() {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-md shadow-primary-500/20">
          <Database className="h-6 w-6 text-white" />
        </div>
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-gray-900">
            Evidence Database
          </h1>
          <p className="text-sm text-gray-500">
            Browse variant evidence organized by mutation identifier
          </p>
        </div>
      </div>

      {/* Variant Index */}
      <VariantIndexView />
    </div>
  );
}
