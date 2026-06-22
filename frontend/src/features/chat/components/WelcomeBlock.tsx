import {
  BookOpen,
  FlaskConical,
  Search,
  Sparkles,
  Upload,
} from "lucide-react";

interface SuggestionChip {
  icon: React.ReactNode;
  title: string;
  description: string;
  /** Message content sent when the chip is clicked. */
  message: string;
  accentBg: string;
  accentColor: string;
}

const SUGGESTIONS: SuggestionChip[] = [
  {
    icon: <FlaskConical style={{ width: 16, height: 16 }} />,
    title: "Run the pipeline",
    description: "Ingest a paper via PMID, DOI, or keyword",
    message: "Run the four-phase pipeline on PMID 34521984",
    accentBg: "#ecfeff",
    accentColor: "var(--color-primary-600, #0891b2)",
  },
  {
    icon: <Upload style={{ width: 16, height: 16 }} />,
    title: "Upload a PDF",
    description: "Parse, translate, and extract evidence",
    message: "I want to upload a PDF",
    accentBg: "#f5f3ff",
    accentColor: "#7c3aed",
  },
  {
    icon: <Search style={{ width: 16, height: 16 }} />,
    title: "Search evidence",
    description: "Query extracted evidence by gene or variant",
    message: "Search the evidence database",
    accentBg: "#ecfdf5",
    accentColor: "#059669",
  },
  {
    icon: <BookOpen style={{ width: 16, height: 16 }} />,
    title: "Classify a variant",
    description: "Walk through ACMG/AMP 2015 criteria",
    message: "Help me classify a variant with ACMG criteria",
    accentBg: "#fffbeb",
    accentColor: "#d97706",
  },
];

export interface WelcomeBlockProps {
  onPick?: (message: string) => void;
}

export function WelcomeBlock({ onPick }: WelcomeBlockProps) {
  return (
    <>
      <style>{`
        @media (min-width: 640px) {
          .cv-suggestions-grid { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
        }
        .cv-suggestion-chip {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          border-radius: 12px;
          border: 1px solid #f3f4f6;
          background-color: #fff;
          padding: 12px;
          text-align: left;
          transition: all 150ms;
          cursor: pointer;
        }
        .cv-suggestion-chip:hover {
          transform: translateY(-2px);
          border-color: #e5e7eb;
          box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05);
        }
        .cv-suggestion-chip:disabled {
          cursor: default;
          transform: none;
          border-color: #f3f4f6;
          box-shadow: none;
        }
      `}</style>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
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
              background: "linear-gradient(to bottom right, var(--color-primary-500, #06b6d4), #2563eb)",
              color: "#fff",
              boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
            }}
          >
            <Sparkles style={{ width: 16, height: 16 }} aria-hidden="true" />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <h2 style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.025em", color: "#111827" }}>
              Welcome to <span style={{ color: "var(--color-primary-600, #0891b2)" }}>Lingua Seeker</span>
            </h2>
            <p style={{ fontSize: 13.5, lineHeight: 1.625, color: "#4b5563" }}>
              A literature-grounded assistant for variant and evidence
              classification. I run a four-phase extraction pipeline and ground
              every claim in source coordinates.
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
                onClick={() => onPick?.(chip.message)}
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
          The agent does not provide clinical diagnoses. Outputs are research-grade
          evidence for review by qualified professionals.
        </p>
      </div>
    </>
  );
}
