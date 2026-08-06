import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { VariantIndexData } from "@/features/evidence-db/types/variantDb";
import { useVariantIndex } from "@/features/evidence-db/hooks/useVariantIndex";
import {
  fetchVariantIndex,
  readCachedVariantIndex,
} from "@/features/evidence-db/services/variantDb";

vi.mock("@/features/auth/hooks/useAuthAccount", () => ({
  useAccountCacheScope: () => ({ isReady: true, scope: "public" }),
}));

vi.mock("@/features/evidence-db/services/variantDb", () => ({
  fetchVariantIndex: vi.fn(),
  readCachedVariantIndex: vi.fn(),
}));

const mockedFetchVariantIndex = vi.mocked(fetchVariantIndex);
const mockedReadCachedVariantIndex = vi.mocked(readCachedVariantIndex);

function variantIndexData(variant: string): VariantIndexData {
  return {
    items: [
      {
        variantSlug: `MECP2:${variant}`,
        gene: "MECP2",
        variant,
        disease: "Rett syndrome",
        classification: "Pathogenic",
        classificationLevel: "pathogenic",
        evidenceGroupCount: 1,
        literatureCount: 1,
        avgConfidence: 0.9,
        fieldCount: 4,
        categoryDistribution: {},
        reviewStatus: "provisional",
        reviewProgress: {
          total: 1,
          reviewed: 0,
          approved: 0,
          corrected: 0,
          rejected: 0,
          provisional: 1,
          reviewedPercent: 0,
        },
        createdAt: null,
        groupIds: [`gene=MECP2|variant=${variant}`],
        sourceDocumentIds: [`document-${variant}`],
        sourceLanguages: [],
        groupDocumentPairs: [
          { groupId: `gene=MECP2|variant=${variant}`, sourceDocumentId: `document-${variant}` },
        ],
        representative: {
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
      },
    ],
    total: 1,
    page: 1,
    pageSize: 24,
    stats: {
      totalVariants: 1,
      totalEvidenceGroups: 1,
      totalLiterature: 1,
      avgConfidence: 0.9,
      classificationDistribution: {
        pathogenic: 1,
        likely_pathogenic: 0,
        uncertain: 0,
        likely_benign: 0,
        benign: 0,
      },
    },
    candidates: { genes: ["MECP2"], variants: [variant], diseases: ["Rett syndrome"] },
  };
}

describe("useVariantIndex cached view", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.clearAllMocks();
  });

  it("shows cached variants until the backend response replaces them", async () => {
    let resolveBackend: ((value: VariantIndexData) => void) | undefined;
    mockedReadCachedVariantIndex.mockReturnValue(variantIndexData("c.1A>G"));
    mockedFetchVariantIndex.mockReturnValue(
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

    // Cached view is shown immediately while the backend fetch is in flight.
    expect(result.current.items[0]?.variant).toBe("c.1A>G");
    expect(result.current.isFetching).toBe(true);
    expect(mockedFetchVariantIndex).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, pageSize: 24 }),
      { cacheScope: "public" },
    );

    await act(async () => {
      resolveBackend?.(variantIndexData("c.2A>G"));
    });

    await waitFor(() => {
      expect(result.current.items[0]?.variant).toBe("c.2A>G");
    });
    expect(result.current.isFetching).toBe(false);
  });
});
