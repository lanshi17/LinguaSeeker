import { useCallback, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  CheckCircle2,
  FileText,
  Globe,
  MessageSquare,
  Search,
  Tag,
  Upload,
} from "lucide-react";

/** Slot schema mirrors the backend-emitted `action.slots` for
 *  `confirm-pipeline`. Keys are snake_case to avoid a mapping layer. */
export interface PipelineSummarySlots {
  source_type?: string;
  query?: string;
  identifiers?: string;
  gene_symbol?: string;
  disease_name?: string;
  variant_hgvs_p?: string;
  filename?: string;
}

interface PipelineSummaryCardProps {
  slots: PipelineSummarySlots;
  onConfirm: (slots: PipelineSummarySlots) => void;
  onModify?: () => void;
  isSubmitting?: boolean;
}

interface FieldRowProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
}

function FieldRow({ icon, label, value, mono }: FieldRowProps) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "6px 0" }}>
      <span style={{
        marginTop: 2,
        display: "flex",
        width: 20,
        height: 20,
        flexShrink: 0,
        alignItems: "center",
        justifyContent: "center",
        color: "#9ca3af",
      }}>
        {icon}
      </span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <span style={{
          display: "block",
          fontSize: 10,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          color: "#9ca3af",
        }}>
          {label}
        </span>
        <span
          style={{
            display: "block",
            fontSize: 13,
            color: "#111827",
            fontFamily: mono ? "var(--font-mono)" : undefined,
          }}
        >
          {value}
        </span>
      </div>
    </div>
  );
}

/**
 * Renders the final "Ready to start?" summary produced by the chat agent's
 * conversational slot-gathering. The user either confirms (submitting the
 * pipeline) or modifies a slot by continuing the conversation.
 *
 * Replaces the deprecated PipelineConfirmCard that paired with the
 * now-removed inline form flow.
 */
export function PipelineSummaryCard({
  slots,
  onConfirm,
  onModify,
  isSubmitting,
}: PipelineSummaryCardProps) {
  const [submitted, setSubmitted] = useState(false);

  const handleConfirm = useCallback(() => {
    setSubmitted(true);
    onConfirm(slots);
  }, [onConfirm, slots]);

  const isOnline = slots.source_type !== "local";
  const sourceLabel = isOnline ? "Online Search" : "PDF Upload";
  const sourceIcon = isOnline ? (
    <Globe style={{ width: 14, height: 14 }} />
  ) : (
    <Upload style={{ width: 14, height: 14 }} />
  );

  const hasTarget =
    slots.gene_symbol || slots.disease_name || slots.variant_hgvs_p;

  const hasData = isOnline
    ? Boolean(slots.query || slots.identifiers)
    : true; // local upload flow: submission is valid once the user confirms

  return (
    <div style={{
      width: "100%",
      maxWidth: 448,
      overflow: "hidden",
      borderRadius: 12,
      border: "1px solid #e5e7eb",
      backgroundColor: "#fff",
      boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        borderBottom: "1px solid #f3f4f6",
        padding: "10px 16px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <FileText style={{ width: 16, height: 16, color: "var(--color-primary-600)" }} aria-hidden />
          <span style={{ fontSize: 13, fontWeight: 600, color: "#111827" }}>
            Ready to start pipeline
          </span>
        </div>
        <Badge variant="info">
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            {sourceIcon}
            {sourceLabel}
          </span>
        </Badge>
      </div>

      <div style={{ padding: "8px 16px" }}>
        {isOnline && slots.identifiers && (
          <div style={{ borderBottom: "1px solid #fafafa" }}>
            <FieldRow
              icon={<Tag style={{ width: 14, height: 14 }} />}
              label="Identifiers"
              value={slots.identifiers}
              mono
            />
          </div>
        )}
        {isOnline && slots.query && (
          <div style={{ borderBottom: "1px solid #fafafa" }}>
            <FieldRow
              icon={<Search style={{ width: 14, height: 14 }} />}
              label="Search Query"
              value={slots.query}
            />
          </div>
        )}
        {!isOnline && slots.filename && (
          <div style={{ borderBottom: "1px solid #fafafa" }}>
            <FieldRow
              icon={<FileText style={{ width: 14, height: 14 }} />}
              label="Document"
              value={slots.filename}
            />
          </div>
        )}
        {!isOnline && !slots.filename && (
          <div style={{ borderBottom: "1px solid #fafafa" }}>
            <FieldRow
              icon={<Upload style={{ width: 14, height: 14 }} />}
              label="Document"
              value="Upload via /pipeline after confirmation"
            />
          </div>
        )}
        {hasTarget && (
          <div style={{ padding: "6px 0" }}>
            <span style={{
              display: "block",
              marginBottom: 4,
              fontSize: 10,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#9ca3af",
            }}>
              Extraction Target
            </span>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {slots.gene_symbol && (
                <span style={{
                  borderRadius: 9999,
                  backgroundColor: "#ecfeff",
                  padding: "2px 8px",
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  fontWeight: 500,
                  color: "var(--color-primary-700)",
                }}>
                  Gene: {slots.gene_symbol}
                </span>
              )}
              {slots.disease_name && (
                <span style={{
                  borderRadius: 9999,
                  backgroundColor: "#ecfdf5",
                  padding: "2px 8px",
                  fontSize: 11,
                  fontWeight: 500,
                  color: "#047857",
                }}>
                  Disease: {slots.disease_name}
                </span>
              )}
              {slots.variant_hgvs_p && (
                <span style={{
                  borderRadius: 9999,
                  backgroundColor: "#f5f3ff",
                  padding: "2px 8px",
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  fontWeight: 500,
                  color: "#6d28d9",
                }}>
                  {slots.variant_hgvs_p}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        borderTop: "1px solid #f3f4f6",
        padding: "10px 16px",
      }}>
        <Button
          size="sm"
          onClick={handleConfirm}
          disabled={!hasData || submitted}
          loading={isSubmitting || submitted}
          style={{ flex: 1 }}
        >
          <CheckCircle2 style={{ width: 14, height: 14, marginRight: 6 }} />
          Confirm & Start
        </Button>
        {onModify && (
          <button
            type="button"
            onClick={onModify}
            disabled={isSubmitting || submitted}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              borderRadius: 6,
              padding: "6px 10px",
              fontSize: 12,
              color: "#6b7280",
              border: "none",
              background: "none",
              cursor: isSubmitting || submitted ? "not-allowed" : "pointer",
              opacity: isSubmitting || submitted ? 0.5 : 1,
              transition: "background-color 150ms, color 150ms",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = "#f9fafb";
              e.currentTarget.style.color = "#374151";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "transparent";
              e.currentTarget.style.color = "#6b7280";
            }}
          >
            <MessageSquare style={{ width: 12, height: 12 }} />
            Modify via chat
          </button>
        )}
      </div>
    </div>
  );
}
