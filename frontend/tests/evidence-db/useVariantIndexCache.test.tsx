import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { EvidenceSearchResponse } from "@/features/evidence-search/types/evidenceSearch";
import { useVariantIndex } from "@/features/evidence-db/hooks/useVariantIndex";
import {
  fetchAllEvidence,
  readCachedAllEvidence,
} from "@/features/evidence-db/services/variantDb";

vi.mock("@/features/auth/hooks/useAuthAccount", () => ({
  useAccountCacheScope: () => ({ isReady: true, scope: "public" }),
}));

vi.mock("@/features/evidence-db/services/variantDb", () => ({
  fetchAllEvidence: vi.fn(),
  readCachedAllEvidence: vi.fn(),
}));

const mockedFetchAllEvidence = vi.mocked(fetchAllEvidence);
const mockedReadCachedAllEvidence = vi.mocked(readCachedAllEvidence);

function evidenceResponse(variant: string): EvidenceSearchResponse {
  return {
    items: [
      {
        group_id: `gene=MECP2|variant=${variant}`,
        source_document_id: `document-${variant}`,
        gene: "MECP2",
        variant,
        disease: "Rett syndrome",
        classification: "Pathogenic",
        field_count: 4,
        avg_confidence: 0.9,
        review_status: "provisional",
      },
    ],
    total: 1,
    page: 1,
    page_size: 1,
  };
}

describe("useVariantIndex cached view", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.clearAllMocks();
  });

  it("shows cached variants until the backend response replaces them", async () => {
    let resolveBackend: ((value: EvidenceSearchResponse) => void) | undefined;
    mockedReadCachedAllEvidence.mockReturnValue(evidenceResponse("c.1A>G"));
    mockedFetchAllEvidence.mockReturnValue(
      new Promise((resolve) => {
        resolveBackend = resolve;
      }),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useVariantIndex(), { wrapper });

    expect(result.current.items[0]?.variant).toBe("c.1A>G");
    expect(result.current.isFetching).toBe(true);
    expect(mockedFetchAllEvidence).toHaveBeenCalledWith(
      {},
      { cacheScope: "public", refresh: true },
    );

    await act(async () => {
      resolveBackend?.(evidenceResponse("c.2A>G"));
    });

    await waitFor(() => {
      expect(result.current.items[0]?.variant).toBe("c.2A>G");
    });
    expect(result.current.isFetching).toBe(false);
  });
});
