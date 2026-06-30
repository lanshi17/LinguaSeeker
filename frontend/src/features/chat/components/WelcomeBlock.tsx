import { useI18n } from "@/lib/i18n";
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

function getSuggestions(t: (key: string) => string): SuggestionChip[] {
  return [
    {
      icon: <FlaskConical style={{ width: 16, height: 16 }} />,
      title: t("chat.welcome.pipeline.title"),
      description: t("chat.welcome.pipeline.desc"),
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
      title: t("chat.welcome.upload.title"),
      description: t("chat.welcome.upload.desc"),
      action: {
        kind: "navigate",
        to: "/pipeline",
        fallbackMessage:
          "Open the pipeline page so I can upload a PDF for bilingual evidence extraction.",
      },
      accentBg: "var(--color-highlight-purple)",
      accentColor: "#7c3aed",
    },
    {
      icon: <Database style={{ width: 16, height: 16 }} />,
      title: t("chat.welcome.search.title"),
      description: t("chat.welcome.search.desc"),
      action: {
        kind: "navigate",
        to: "/evidence",
        fallbackMessage:
          "Open the evidence database so I can search by gene, variant, disease, PMID, or DOI.",
      },
      accentBg: "var(--color-highlight-green)",
      accentColor: "#059669",
    },
    {
      icon: <ClipboardCheck style={{ width: 16, height: 16 }} />,
      title: t("chat.welcome.review.title"),
      description: t("chat.welcome.review.desc"),
      action: {
        kind: "navigate",
        to: "/evidence?review_status=pending",
        fallbackMessage:
          "Show evidence items that need expert review and help prepare an evidence summary report.",
      },
      accentBg: "var(--color-highlight-amber)",
      accentColor: "#d97706",
    },
  ];
}

export interface WelcomeBlockProps {
  onPick?: (action: WelcomeAction) => void;
}

export function WelcomeBlock({ onPick }: WelcomeBlockProps) {
  const { t } = useI18n();
  const suggestions = getSuggestions(t);

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
            <h2 style={{ fontSize: 15, fontWeight: 600, letterSpacing: 0, color: "var(--color-text)" }}>
              {t("chat.welcome.heading")}
            </h2>
            <p style={{ fontSize: 13.5, lineHeight: 1.625, color: "var(--color-text-strong)" }}>
              {t("chat.welcome.description")}
            </p>
          </div>
        </div>

        <div className="cv-suggestions-grid" style={{ display: "grid", gap: 8 }}>
          {suggestions.map((chip) => {
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
                      color: "var(--color-text)",
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
                      color: "var(--color-text-secondary)",
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
            borderTop: "1px solid var(--color-bg-muted)",
            paddingTop: 12,
            fontSize: 11.5,
            lineHeight: 1.625,
            color: "var(--color-text-muted)",
          }}
        >
          {t("chat.welcome.disclaimer")}
        </p>
      </div>
  );
}
