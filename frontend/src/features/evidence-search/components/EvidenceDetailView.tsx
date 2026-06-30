import { useMemo, useState } from "react";
import { ArrowLeft, AlertCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { useEvidenceGroupDetail } from "../hooks/useEvidenceGroupDetail";
import { useI18n } from "@/lib/i18n";
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
  const { t } = useI18n();
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
              {t("evidence.detail.loadError")}
            </p>
            <p style={{ marginTop: 4, fontSize: 14, color: "#dc2626" }}>
              {error?.message ?? t("evidence.detail.notFound")}
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
              {t("evidence.detail.back")}
            </Link>
          </div>
        </div>
    );
  }

  return (
      initialView === "compare" ? (
        <BilingualCompareView
          detail={detail!}
          groupId={groupId}
          selectedEvidenceId={selectedEvidenceId}
          setSelectedEvidenceId={setSelectedOverrideId}
        />
      ) : (
        <LiteratureOverview detail={detail!} groupId={groupId} />
      )
  );
}
