import { useMemo, useState } from "react";
import { Tooltip } from "antd";
import type { ClassificationLevel } from "../types/variantDb";
import { classificationColor, classificationLabel, classificationShortLabel } from "../utils/pathogenicity";
import { useI18n } from "@/lib/i18n";

interface Props {
  distribution: Record<ClassificationLevel, number>;
  /** When set, highlights this level and dims others */
  activeLevel?: ClassificationLevel | null;
  /** Fired when a segment is clicked */
  onSegmentClick?: (level: ClassificationLevel) => void;
}

const LEVELS: ClassificationLevel[] = [
  "pathogenic",
  "likely_pathogenic",
  "uncertain",
  "likely_benign",
  "benign",
];

/**
 * A proportional bar showing the pathogenicity distribution across all
 * variants. Each segment is sized by count and colored per classification.
 * The signature visual element for the Evidence Database landing.
 */
export function ClassificationDistributionBar({ distribution, activeLevel, onSegmentClick }: Props) {
  const { t } = useI18n();
  const [hovered, setHovered] = useState<ClassificationLevel | null>(null);

  const total = useMemo(
    () => LEVELS.reduce((s, l) => s + (distribution[l] ?? 0), 0),
    [distribution],
  );

  if (total === 0) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
      {/* The bar */}
      <div
        style={{
          display: "flex",
          width: "100%",
          height: 10,
          borderRadius: 5,
          overflow: "hidden",
          backgroundColor: "var(--color-border)",
        }}
      >
        {LEVELS.map((level) => {
          const count = distribution[level] ?? 0;
          if (count === 0) return null;
          const pct = (count / total) * 100;
          const isActive = !activeLevel || activeLevel === level;
          const isHovered = hovered === level;
          return (
            <Tooltip
              key={level}
              title={`${classificationLabel(level, t)}: ${count} (${pct.toFixed(1)}%)`}
              mouseEnterDelay={0}
            >
              <div
                role="button"
                tabIndex={0}
                aria-label={classificationLabel(level, t)}
                style={{
                  width: `${pct}%`,
                  height: "100%",
                  backgroundColor: classificationColor(level),
                  opacity: isActive ? (isHovered ? 1 : 0.85) : 0.25,
                  transition: "opacity 0.15s, transform 0.1s",
                  transform: isHovered ? "scaleY(1.3)" : "scaleY(1)",
                  cursor: onSegmentClick ? "pointer" : "default",
                }}
                onMouseEnter={() => setHovered(level)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => onSegmentClick?.(level)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") onSegmentClick?.(level);
                }}
              />
            </Tooltip>
          );
        })}
      </div>

      {/* Legend chips */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {LEVELS.map((level) => {
          const count = distribution[level] ?? 0;
          const isActive = !activeLevel || activeLevel === level;
          const shortLabel = classificationShortLabel(level);
          return (
            <button
              key={level}
              type="button"
              onClick={() => onSegmentClick?.(level)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "3px 8px",
                borderRadius: 6,
                border: `1.5px solid ${isActive ? classificationColor(level) : "var(--color-border)"}`,
                backgroundColor: isActive ? `${classificationColor(level)}10` : "transparent",
                color: isActive ? classificationColor(level) : "var(--color-text-muted)",
                fontSize: 11,
                fontWeight: 600,
                fontFamily: "var(--font-mono)",
                cursor: onSegmentClick ? "pointer" : "default",
                transition: "all 0.15s",
                letterSpacing: "0.02em",
                lineHeight: 1,
              }}
              title={classificationLabel(level, t)}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  backgroundColor: classificationColor(level),
                  opacity: isActive ? 1 : 0.3,
                  flexShrink: 0,
                }}
              />
              {shortLabel}
              <span style={{ fontWeight: 400, opacity: 0.7 }}>{count}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
