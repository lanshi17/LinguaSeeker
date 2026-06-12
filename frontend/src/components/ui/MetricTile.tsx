import type { ReactNode } from "react";
import { cn } from "@/lib/utils/cn";

interface MetricTileProps {
  label: string;
  value: ReactNode;
  unit?: string;
  /** Tone for the value (e.g. success for positive counts). */
  tone?: "default" | "primary" | "success" | "warning" | "error";
  /** Optional icon at top-left. */
  icon?: ReactNode;
  className?: string;
}

const toneStyles: Record<NonNullable<MetricTileProps["tone"]>, string> = {
  default: "text-gray-900",
  primary: "text-primary-700",
  success: "text-success-700",
  warning: "text-amber-700",
  error: "text-red-700",
};

/**
 * Compact label / value tile used to surface a single quantitative fact.
 * Optimised for tabular display inside phase cards.
 */
export function MetricTile({
  label,
  value,
  unit,
  tone = "default",
  icon,
  className,
}: MetricTileProps) {
  return (
    <div
      className={cn(
        "rounded-md border border-gray-100 bg-gray-50/60 px-3 py-2",
        className,
      )}
    >
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-gray-500">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-0.5 flex items-baseline gap-1">
        <span className={cn("font-mono text-lg font-semibold tabular-nums", toneStyles[tone])}>
          {value}
        </span>
        {unit && <span className="text-xs text-gray-500">{unit}</span>}
      </div>
    </div>
  );
}
