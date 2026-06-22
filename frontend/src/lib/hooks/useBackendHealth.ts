
import { useQuery } from "@tanstack/react-query";
import axios from "axios";

const healthEndpoint = import.meta.env.VITE_HEALTH_ENDPOINT || "/health";
const healthPollInterval =
  Number(import.meta.env.VITE_HEALTH_POLL_INTERVAL) || 30_000;

type HealthStatus = "connected" | "disconnected" | "checking";

interface BackendHealth {
  status: HealthStatus;
  latencyMs: number | null;
  lastChecked: Date | null;
}

/**
 * Poll the backend health endpoint at a configurable interval.
 *
 * Endpoint and polling interval come from the layered .env config
 * (VITE_HEALTH_ENDPOINT, VITE_HEALTH_POLL_INTERVAL).
 * Requests go through the Vite dev server proxy.
 */
export function useBackendHealth(): BackendHealth {
  const { data } = useQuery({
    queryKey: ["backend-health"],
    queryFn: async () => {
      const start = Date.now();
      try {
        const response = await axios.get<{ status: string }>(
          healthEndpoint,
          { timeout: 5_000 },
        );
        const latencyMs = Date.now() - start;
        return {
          ok: response.data?.status === "ok",
          latencyMs,
          checkedAt: new Date(),
        };
      } catch {
        return {
          ok: false,
          latencyMs: null,
          checkedAt: new Date(),
        };
      }
    },
    refetchInterval: healthPollInterval,
    retry: false,
    staleTime: Math.max(healthPollInterval - 5_000, 10_000),
  });

  if (!data) {
    return { status: "checking", latencyMs: null, lastChecked: null };
  }

  return {
    status: data.ok ? "connected" : "disconnected",
    latencyMs: data.latencyMs,
    lastChecked: data.checkedAt,
  };
}
