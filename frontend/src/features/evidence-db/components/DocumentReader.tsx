import { Languages, BookOpen } from "lucide-react";
import type { EvidenceDocument } from "@/features/evidence-search/utils/evidenceDocument";
import { HighlightedText } from "./HighlightedText";

/* ── Document Reader Panel ──────────────────────────────── */

export function DocumentReader({
  title,
  track,
  document,
  accentColor,
}: {
  title: string;
  track: "original" | "translated";
  document: EvidenceDocument;
  accentColor: string;
}) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      borderRadius: 12,
      border: "1px solid #e5e7eb",
      backgroundColor: "#fff",
      overflow: "hidden",
    }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 16px",
          borderBottom: "1px solid #f3f4f6",
          backgroundColor: `${accentColor}08`,
        }}
      >
        <Languages style={{ width: 16, height: 16, color: accentColor }} />
        <h3 style={{ fontSize: 14, fontWeight: 600, color: "#1f2937", margin: 0 }}>{title}</h3>
        <span style={{
          marginLeft: "auto",
          fontSize: 11,
          textTransform: "capitalize",
          color: "#6b7280",
        }}>
          {track} track
        </span>
      </div>
      <div className="edb-scroll" style={{ maxHeight: 600, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
        {document.paragraphs.length === 0 ? (
          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "48px 0",
            textAlign: "center",
          }}>
            <BookOpen style={{ width: 32, height: 32, color: "#9ca3af", marginBottom: 8 }} />
            <p style={{ fontSize: 14, color: "#6b7280", margin: 0 }}>
              No {track} text available
            </p>
          </div>
        ) : (
          document.paragraphs.map((para) => (
            <div key={para.id} style={{ position: "relative" }}>
              {para.page && (
                <span style={{
                  position: "absolute",
                  left: -8,
                  top: 0,
                  fontSize: 10,
                  color: "#9ca3af",
                  fontFamily: "var(--font-mono)",
                }}>
                  p.{para.page}
                </span>
              )}
              <HighlightedText paragraph={para} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
