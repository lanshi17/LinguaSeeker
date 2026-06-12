import { cn } from "@/lib/utils/cn";

type PulseTone = "primary" | "success" | "warning" | "error" | "neutral";

interface LivePulseProps {
  tone?: PulseTone;
  className?: string;
  /** Optional aria-label override. */
  label?: string;
}

const toneStyles: Record<PulseTone, { dot: string; ring: string }> = {
  primary: {
    dot: "bg-primary-500",
    ring: "bg-primary-500/40",
  },
  success: {
    dot: "bg-success-500",
    ring: "bg-success-500/40",
  },
  warning: {
    dot: "bg-amber-500",
    ring: "bg-amber-500/40",
  },
  error: {
    dot: "bg-red-500",
    ring: "bg-red-500/40",
  },
  neutral: {
    dot: "bg-gray-400",
    ring: "bg-gray-400/40",
  },
};

/**
 * A small live indicator: solid core + expanding ring. Communicates "in progress"
 * without the noise of a full spinner.
 */
export function LivePulse({ tone = "primary", className, label }: LivePulseProps) {
  const { dot, ring } = toneStyles[tone];
  return (
    <span
      className={cn("relative inline-flex h-2.5 w-2.5", className)}
      role="status"
      aria-label={label ?? "In progress"}
    >
      <span
        className={cn(
          "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
          ring,
        )}
      />
      <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", dot)} />
    </span>
  );
}
