
import { useState } from "react";
import { useBackendHealth } from "@/lib/hooks/useBackendHealth";
import { cn } from "@/lib/utils/cn";

const STATUS_CONFIG = {
  connected: {
    dot: "bg-green-500",
    pulse: "animate-pulse",
    label: "Backend connected",
    ariaLabel: "Backend is connected",
  },
  disconnected: {
    dot: "bg-red-500",
    pulse: "animate-pulse",
    label: "Backend disconnected",
    ariaLabel: "Backend is disconnected",
  },
  checking: {
    dot: "bg-gray-400",
    pulse: "",
    label: "Checking connection…",
    ariaLabel: "Checking backend connection",
  },
} as const;

/**
 * Backend connectivity status indicator.
 *
 * Renders a small colored dot with a tooltip showing connection state
 * and latency. Polls GET /health every 30 seconds via useBackendHealth.
 *
 * - Green pulse = connected
 * - Red pulse   = disconnected
 * - Gray        = initial check in progress
 */
export function ConnectionStatus() {
  const { status, latencyMs, lastChecked } = useBackendHealth();
  const [showTooltip, setShowTooltip] = useState(false);
  const config = STATUS_CONFIG[status];

  const timeAgo = lastChecked
    ? formatTimeAgo(lastChecked)
    : null;

  return (
    <div
      className="relative flex items-center gap-2"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {/* Status dot */}
      <button
        className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full transition-colors hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-1"
        aria-label={config.ariaLabel}
        aria-live="polite"
        aria-expanded={showTooltip}
        onClick={() => setShowTooltip((o) => !o)}
        onBlur={() => setShowTooltip(false)}
      >
        <span className="relative flex h-2.5 w-2.5">
          {status !== "checking" && (
            <span
              className={cn(
                "absolute inline-flex h-full w-full rounded-full opacity-75",
                config.dot,
                config.pulse,
              )}
            />
          )}
          <span
            className={cn(
              "relative inline-flex h-2.5 w-2.5 rounded-full",
              config.dot,
            )}
          />
        </span>
      </button>

      {/* Tooltip */}
      {showTooltip && (
        <div
          role="tooltip"
          className="absolute top-full left-1/2 z-50 mt-2 -translate-x-1/2 whitespace-nowrap rounded-md bg-gray-900 px-3 py-2 text-xs text-white shadow-lg"
        >
          <p className="font-medium">{config.label}</p>
          {latencyMs !== null && (
            <p className="text-gray-400">Latency: {latencyMs}ms</p>
          )}
          {timeAgo && <p className="text-gray-400">Checked: {timeAgo}</p>}
          {/* Arrow */}
          <div className="absolute -top-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 bg-gray-900" />
        </div>
      )}
    </div>
  );
}

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ago`;
}
