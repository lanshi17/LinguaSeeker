import { useParams } from "react-router-dom";
import { Database } from "lucide-react";
import { VariantIndexView } from "@/features/evidence-db";
import { VariantDetailView } from "@/features/evidence-db";
import { BilingualEvidenceView } from "@/features/evidence-db";

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
    return (
      <div className="edb-root p-5 md:p-7">
        <BilingualEvidenceView variantSlug={variantSlug} sourceDocumentId={sourceDocId} />
      </div>
    );
  }

  // L2: variant detail
  if (variantSlug) {
    return (
      <div className="edb-root p-5 md:p-7">
        <VariantDetailView variantSlug={variantSlug} />
      </div>
    );
  }

  // L1: variant index
  return (
    <div className="edb-root p-5 md:p-7">
      {/* Page Header */}
      <div className="mb-6 flex items-center gap-4">
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-cyan-400/20"
          style={{
            background: "linear-gradient(135deg, rgba(34,211,238,0.15), rgba(139,92,246,0.1))",
          }}
        >
          <Database className="h-6 w-6 text-cyan-400" />
        </div>
        <div>
          <h1 className="font-display text-2xl font-medium tracking-tight text-slate-100">
            Evidence Database
          </h1>
          <p className="text-sm text-slate-400">
            Browse variant evidence organized by mutation identifier
          </p>
        </div>
      </div>

      <VariantIndexView />
    </div>
  );
}
