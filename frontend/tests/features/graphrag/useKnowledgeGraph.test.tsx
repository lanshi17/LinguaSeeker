import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useKnowledgeGraph } from "@/features/graphrag/hooks/useKnowledgeGraph";
import {
  fetchKnowledgeGraph,
  readCachedKnowledgeGraph,
} from "@/features/graphrag/services/graphRag";
import type { KnowledgeGraph } from "@/features/graphrag/types/graphRag";

vi.mock("@/features/auth/hooks/useAuthAccount", () => ({
  useAccountCacheScope: () => ({ isReady: true, scope: "public" }),
}));

vi.mock("@/features/graphrag/services/graphRag", () => ({
  fetchKnowledgeGraph: vi.fn(),
  readCachedKnowledgeGraph: vi.fn(),
}));

const mockedFetchKnowledgeGraph = vi.mocked(fetchKnowledgeGraph);
const mockedReadCachedKnowledgeGraph = vi.mocked(readCachedKnowledgeGraph);

function graph(name: string): KnowledgeGraph {
  return {
    nodes: [
      {
        node_id: `gene:${name}`,
        labels: ["Gene"],
        display_name: name,
        properties: {},
      },
    ],
    edges: [],
  };
}

describe("useKnowledgeGraph", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a cached graph until the backend response replaces it", async () => {
    let resolveBackend: ((value: KnowledgeGraph) => void) | undefined;
    mockedReadCachedKnowledgeGraph.mockReturnValue(graph("EGFR-cached"));
    mockedFetchKnowledgeGraph.mockReturnValue(
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

    const { result } = renderHook(
      () => useKnowledgeGraph({ geneSymbol: "EGFR" }),
      { wrapper },
    );

    expect(result.current.data?.nodes[0]?.display_name).toBe("EGFR-cached");
    expect(result.current.isFetching).toBe(true);
    expect(mockedFetchKnowledgeGraph).toHaveBeenCalledWith(
      expect.objectContaining({ geneSymbol: "EGFR" }),
      { cacheScope: "public", refresh: true },
    );

    await act(async () => {
      resolveBackend?.(graph("EGFR-fresh"));
    });

    await waitFor(() => {
      expect(result.current.data?.nodes[0]?.display_name).toBe("EGFR-fresh");
    });
    expect(result.current.isFetching).toBe(false);
  });
});
