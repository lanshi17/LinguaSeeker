import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { apiClient } from "../../src/lib/api/client";
import { useBackendHealth } from "../../src/lib/hooks/useBackendHealth";

vi.mock("../../src/lib/api/client", () => ({
  apiClient: {
    get: vi.fn(async () => ({ data: { status: "ok" } })),
  },
}));

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useBackendHealth", () => {
  it("uses the shared API client for health checks", async () => {
    const { result } = renderHook(() => useBackendHealth(), { wrapper });

    await waitFor(() => expect(result.current.status).toBe("connected"));

    expect(apiClient.get).toHaveBeenCalledWith(
      expect.any(String),
      { timeout: 5_000 },
    );
  });
});
