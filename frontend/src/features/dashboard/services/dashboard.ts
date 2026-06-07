import { apiClient } from "@/lib/api/client";
import type { DashboardSummary } from "../types/dashboard";

/**
 * Fetch aggregated dashboard summary.
 *
 * GET /api/v1/dashboard/summary
 */
export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await apiClient.get<DashboardSummary>("/dashboard/summary");
  return data;
}
