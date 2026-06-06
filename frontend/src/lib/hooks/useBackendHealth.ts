"use client";

import { useQuery } from "@tanstack/react-query";
import axios from "axios";

type HealthStatus = "connected" | "disconnected" | "checking";

interface BackendHealth {
  status: HealthStatus;
  latencyMs: number | null;
  lastChecked: Date | null;
}

/**
 * Poll the backend health endpoint (GET /health) every 30 seconds.
 *
 * Goes through the Next.js proxy (next.config.ts rewrites /health
 * to the backend).  A short 5s timeout ensures a fast "disconnected"
 * flip when the backend goes down.
 */
export function useBackendHealth(): BackendHealth {
  const { data } = useQuery({
    queryKey: ["backend-health"],
    queryFn: async () => {
      const start = Date.now();
      try {
        const response = await axios.get<{ status: string }>(
          "/health",
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
    refetchInterval: 30_000,
    retry: false,
    staleTime: 25_000,
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
