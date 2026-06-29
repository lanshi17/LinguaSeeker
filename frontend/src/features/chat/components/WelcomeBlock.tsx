import {
  ClipboardCheck,
  Database,
  FlaskConical,
  Sparkles,
  Upload,
} from "lucide-react";

interface SuggestionChip {
  icon: React.ReactNode;
  title: string;
  description: string;
  /** Action dispatched when the chip is clicked. */
  action: WelcomeAction;
  accentBg: string;
  accentColor: string;
}

export type WelcomeAction =
  | {
      kind: "send-message";
      message: string;
    }
  | {
      kind: "navigate";
      to: string;
      fallbackMessage: string;
    };

const SUGGESTIONS: SuggestionChip[] = [
  {
    icon: <FlaskConical style={{ width: 16, height: 16 }} />,
    title: "Run evidence pipeline",
    description: "Start from PMID, DOI, title, or keyword",
    action: {
      kind: "send-message",
      message:
        "Start an online evidence pipeline. Identifier: PMID 28499369. Use bilingual extraction and source-grounded evidence review.",
    },
    accentBg: "var(--color-primary-50, #ecfeff)",
    accentColor: "var(--color-primary-600, #0891b2)",
  },
  {
    icon: <Upload style={{ width: 16, height: 16 }} />,
    title: "Upload source paper",
    description: "Parse full text, tables, and source spans",
    action: {
      kind: "navigate",
      to: "/pipeline",
      fallbackMessage:
        "Open the pipeline page so I can upload a PDF for bilingual evidence extraction.",
    },
    accentBg: "#f5f3ff",
    accentColor: "#7c3aed",
  },
  {
    icon: <Database style={{ width: 16, height: 16 }} />,
    title: "Search evidence base",
    description: "Find records by gene, variant, disease, PMID",
    action: {
      kind: "navigate",
      to: "/evidence",
      fallbackMessage:
        "Open the evidence database so I can search by gene, variant, disease, PMID, or DOI.",
    },
    accentBg: "#ecfdf5",
    accentColor: "#059669",
  },
  {
    icon: <ClipboardCheck style={{ width: 16, height: 16 }} />,
    title: "Review and export",
    description: "Check bilingual evidence before reporting",
    action: {
      kind: "navigate",
      to: "/evidence?review_status=pending",
      fallbackMessage:
        "Show evidence items that need expert review and help prepare an evidence summary report.",
    },
    accentBg: "#fffbeb",
    accentColor: "#d97706",
  },
];

export interface WelcomeBlockProps {
  onPick?: (action: WelcomeAction) => void;
}

export function WelcomeBlock({ onPick }: WelcomeBlockProps) {
  return (
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          <div
            style={{
              display: "flex",
              height: 36,
              width: 36,
              flex: "none",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 12,
              background: "var(--color-primary-600, #0891b2)",
              color: "#fff",
              boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
            }}
          >
            <Sparkles style={{ width: 16, height: 16 }} aria-hidden="true" />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <h2 style={{ fontSize: 15, fontWeight: 600, letterSpacing: 0, color: "#111827" }}>
              Start a traceable evidence workflow in{" "}
              <span style={{ color: "var(--color-primary-600, #0891b2)" }}>Lingua Seeker</span>
            </h2>
            <p style={{ fontSize: 13.5, lineHeight: 1.625, color: "#4b5563" }}>
              I can help acquire literature, extract bilingual evidence, compare
              original and translated spans, queue expert review, and prepare
              source-linked evidence reports.
            </p>
          </div>
        </div>

        <div className="cv-suggestions-grid" style={{ display: "grid", gap: 8 }}>
          {SUGGESTIONS.map((chip) => {
            const isInteractive = Boolean(onPick);
            return (
              <button
                key={chip.title}
                type="button"
                onClick={() => onPick?.(chip.action)}
                disabled={!isInteractive}
                className="cv-suggestion-chip"
              >
                <span
                  style={{
                    display: "flex",
                    height: 32,
                    width: 32,
                    flex: "none",
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 8,
                    backgroundColor: chip.accentBg,
                    color: chip.accentColor,
                  }}
                >
                  {chip.icon}
                </span>
                <span style={{ minWidth: 0, flex: 1 }}>
                  <span
                    style={{
                      display: "block",
                      fontSize: 13,
                      fontWeight: 500,
                      color: "#111827",
                    }}
                  >
                    {chip.title}
                  </span>
                  <span
                    style={{
                      marginTop: 2,
                      display: "block",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      fontSize: 12,
                      color: "#6b7280",
                    }}
                  >
                    {chip.description}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        <p
          style={{
            borderTop: "1px solid #f3f4f6",
            paddingTop: 12,
            fontSize: 11.5,
            lineHeight: 1.625,
            color: "#9ca3af",
          }}
        >
          Research support only. The assistant prepares traceable evidence for
          qualified professional review and does not provide clinical diagnoses.
        </p>
      </div>
  );
}
