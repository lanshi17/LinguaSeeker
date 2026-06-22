import { Tooltip, Badge } from "antd";
import { useBackendHealth } from "@/lib/hooks/useBackendHealth";

const STATUS_CONFIG = {
  connected: {
    status: "success" as const,
    label: "Backend connected",
    ariaLabel: "Backend is connected",
  },
  disconnected: {
    status: "error" as const,
    label: "Backend disconnected",
    ariaLabel: "Backend is disconnected",
  },
  checking: {
    status: "default" as const,
    label: "Checking connection\u2026",
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
  const config = STATUS_CONFIG[status];

  const timeAgo = lastChecked ? formatTimeAgo(lastChecked) : null;

  const tooltipContent = (
    <div>
      <p style={{ fontWeight: 500, margin: 0 }}>{config.label}</p>
      {latencyMs !== null && (
        <p style={{ color: "rgba(255,255,255,0.65)", margin: "4px 0 0", fontSize: 12 }}>
          Latency: {latencyMs}ms
        </p>
      )}
      {timeAgo && (
        <p style={{ color: "rgba(255,255,255,0.65)", margin: "2px 0 0", fontSize: 12 }}>
          Checked: {timeAgo}
        </p>
      )}
    </div>
  );

  return (
    <Tooltip title={tooltipContent} placement="bottom" arrow>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 32,
          height: 32,
          borderRadius: "50%",
          cursor: "pointer",
        }}
        aria-label={config.ariaLabel}
        aria-live="polite"
      >
        <Badge
          status={config.status}
          style={{ fontSize: 10 }}
        />
      </div>
    </Tooltip>
  );
}

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ago`;
}
