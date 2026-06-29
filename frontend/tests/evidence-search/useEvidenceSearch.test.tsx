import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { useEvidenceSearch } from "../../src/features/evidence-search/hooks/useEvidenceSearch";

vi.mock("../../src/features/evidence-search/services/evidenceSearch", () => ({
  searchEvidence: vi.fn(async () => ({
    items: [],
    total: 0,
    page: 1,
    page_size: 50,
  })),
}));

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useEvidenceSearch", () => {
  it("keeps applyFilters stable across rerenders", () => {
    const { result, rerender } = renderHook(() => useEvidenceSearch(), { wrapper });
    const firstApplyFilters = result.current.applyFilters;

    rerender();

    expect(result.current.applyFilters).toBe(firstApplyFilters);
  });
});
