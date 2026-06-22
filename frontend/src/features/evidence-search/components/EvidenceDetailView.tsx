import { useMemo, useState } from "react";
import { ArrowLeft, AlertCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { useEvidenceGroupDetail } from "../hooks/useEvidenceGroupDetail";
import { EvidenceDetailSkeleton } from "./EvidenceDetailSkeleton";
import { findInitialEvidenceId } from "../utils/literatureRows";
import { BilingualCompareView } from "./BilingualCompareView";
import { LiteratureOverview } from "./LiteratureOverview";

type DetailViewMode = "overview" | "compare";

interface EvidenceDetailViewProps {
  groupId: string;
  initialEvidenceId?: string;
  initialView?: DetailViewMode;
}

export function EvidenceDetailView({
  groupId,
  initialEvidenceId,
  initialView = "overview",
}: EvidenceDetailViewProps) {
  const { detail, isLoading, error } = useEvidenceGroupDetail(groupId);
  const [selectedOverrideId, setSelectedOverrideId] = useState<string | null>(
    null,
  );

  const selectedEvidenceId = useMemo(() => {
    if (!detail) {
      return null;
    }
    if (
      selectedOverrideId &&
      detail.items.some(
        (item) => item.canonical_evidence_id === selectedOverrideId,
      )
    ) {
      return selectedOverrideId;
    }
    return findInitialEvidenceId(detail, initialEvidenceId);
  }, [detail, initialEvidenceId, selectedOverrideId]);

  if (isLoading) {
    return <EvidenceDetailSkeleton />;
  }

  if (error || !detail) {
    return (
      <>
        <style>{`
          .edb-detail-error {
            position: relative;
            overflow: hidden;
            border-radius: 12px;
            border: 1px solid #fecaca;
            background: linear-gradient(to bottom right, #fef2f2, #fff);
            padding: 56px 24px;
            text-align: center;
          }
        `}</style>
        <div className="edb-detail-error">
          <div style={{ position: "relative" }}>
            <div
              style={{
                margin: "0 auto",
                display: "flex",
                height: 56,
                width: 56,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 16,
                backgroundColor: "#fee2e2",
              }}
            >
              <AlertCircle style={{ width: 28, height: 28, color: "#ef4444" }} />
            </div>
            <p style={{ marginTop: 16, fontSize: 14, fontWeight: 600, color: "#991b1b" }}>
              Failed to load evidence detail
            </p>
            <p style={{ marginTop: 4, fontSize: 14, color: "#dc2626" }}>
              {error?.message ?? "The requested evidence group could not be found."}
            </p>
            <Link
              to="/evidence"
              style={{
                marginTop: 20,
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                borderRadius: 6,
                backgroundColor: "#dc2626",
                padding: "8px 16px",
                fontSize: 14,
                fontWeight: 500,
                color: "#fff",
                textDecoration: "none",
                transition: "background-color 0.15s",
              }}
            >
              <ArrowLeft style={{ width: 16, height: 16 }} />
              Back to literature
            </Link>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <style>{`
        /* Responsive grids */
        .edb-overview-meta-grid {
          display: grid;
          gap: 0;
        }
        @media (min-width: 768px) {
          .edb-overview-meta-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
          }
        }
        .edb-overview-meta-cell {
          border-bottom: 1px solid #f3f4f6;
          padding: 16px 20px;
        }
        @media (min-width: 768px) {
          .edb-overview-meta-cell {
            border-bottom: none;
            border-right: 1px solid #f3f4f6;
          }
          .edb-overview-meta-cell:last-child {
            border-right: none;
          }
        }
        .edb-overview-layout {
          display: grid;
          gap: 20px;
        }
        @media (min-width: 1024px) {
          .edb-overview-layout {
            grid-template-columns: 300px minmax(0, 1fr);
          }
        }
        /* Coverage stats 2-col grid borders */
        .edb-coverage-stat-cell {
          padding: 16px;
        }
        .edb-coverage-stat-cell:nth-child(odd) {
          border-right: 1px solid #f3f4f6;
        }
        .edb-coverage-stat-cell:nth-child(-n+2) {
          border-bottom: 1px solid #f3f4f6;
        }

        /* Line clamp */
        .edb-line-clamp-3 {
          display: -webkit-box;
          -webkit-line-clamp: 3;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }

        /* Card hover */
        .edb-evidence-card {
          position: relative;
          overflow: hidden;
          border-radius: 12px;
          border: 1px solid #e5e7eb;
          background: #fff;
          box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05);
          transition: all 0.15s;
        }
        .edb-evidence-card:hover {
          border-color: var(--color-primary-200, #a5f3fc);
          box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }
        .edb-evidence-card:hover .edb-evidence-card-accent {
          opacity: 1;
        }

        /* Back link hover */
        .edb-back-link:hover {
          color: var(--color-primary-600, #0891b2) !important;
        }

        /* Focus visible */
        .edb-focusable-link:focus-visible {
          outline: 2px solid var(--color-primary-500, #06b6d4);
          outline-offset: 0;
        }
        .edb-focusable-btn:focus-visible {
          outline: 2px solid var(--color-primary-500, #06b6d4);
          outline-offset: 0;
        }

      `}</style>
      {initialView === "compare" ? (
        <BilingualCompareView
          detail={detail!}
          groupId={groupId}
          selectedEvidenceId={selectedEvidenceId}
          setSelectedEvidenceId={setSelectedOverrideId}
        />
      ) : (
        <LiteratureOverview detail={detail!} groupId={groupId} />
      )}
    </>
  );
}
