import { useParams } from "react-router-dom";
import { Database } from "lucide-react";
import { VariantIndexView, VariantDetailView, BilingualEvidenceView } from "@/features/evidence-db";

/**
 * Evidence Database page — routes between three levels via URL params:
 *
 * L1 /evidence-db                          — variant index (all variants)
 * L2 /evidence-db/:variantSlug             — single variant detail + references
 * L3 /evidence-db/:variantSlug/:sourceDocId — bilingual evidence comparison
 */
export function EvidenceDbPage() {
  const { variantSlug, sourceDocId } = useParams();

  // L3: bilingual evidence comparison
  if (variantSlug && sourceDocId) {
    return <BilingualEvidenceView variantSlug={variantSlug} sourceDocumentId={sourceDocId} />;
  }

  // L2: variant detail
  if (variantSlug) {
    return <VariantDetailView variantSlug={variantSlug} />;
  }

  // L1: variant index
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

      <VariantIndexView />
    </div>
  );
}
