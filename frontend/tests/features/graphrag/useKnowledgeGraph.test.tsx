import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useKnowledgeGraph } from "@/features/graphrag/hooks/useKnowledgeGraph";
import {
  fetchKnowledgeGraph,
  readCachedKnowledgeGraph,
} from "@/features/graphrag/services/graphRag";
import { demoKnowledgeGraph } from "@/features/graphrag/services/demoGraph";
import type { KnowledgeGraph } from "@/features/graphrag/types/graphRag";

vi.mock("@/features/auth/hooks/useAuthAccount", () => ({
  useAccountCacheScope: () => ({ isReady: true, scope: "public" }),
}));

vi.mock("@/features/graphrag/services/graphRag", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/graphrag/services/graphRag")>();
  return {
    ...actual,
    fetchKnowledgeGraph: vi.fn(),
    readCachedKnowledgeGraph: vi.fn(),
  };
});

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

    // Cached data is real (has nodes), so isDemo is false.
    expect(result.current.data?.nodes[0]?.display_name).toBe("EGFR-cached");
    expect(result.current.isDemo).toBe(false);
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
    expect(result.current.isDemo).toBe(false);
    expect(result.current.isFetching).toBe(false);
  });

  it("falls back to demo graph when the backend returns an empty graph", async () => {
    mockedReadCachedKnowledgeGraph.mockReturnValue(undefined);
    mockedFetchKnowledgeGraph.mockResolvedValue({ nodes: [], edges: [] });
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

    await waitFor(() => {
      expect(result.current.isFetching).toBe(false);
    });

    expect(result.current.isDemo).toBe(true);
    expect(result.current.data).toBe(demoKnowledgeGraph);
    expect(result.current.data?.nodes.length).toBeGreaterThan(0);
  });

  it("falls back to demo graph on a no-match 400 and does not retry", async () => {
    mockedFetchKnowledgeGraph.mockRejectedValue({
      status: 400,
      backendMessage: "No matching nodes found for the provided entities",
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retryDelay: 50 } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(
      () => useKnowledgeGraph({ geneSymbol: "EGFR" }),
      { wrapper },
    );

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });
    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(mockedFetchKnowledgeGraph).toHaveBeenCalledTimes(1);
    expect(result.current.isDemo).toBe(true);
    expect(result.current.data).toBe(demoKnowledgeGraph);
    expect(result.current.error).toMatchObject({
      status: 400,
      backendMessage: "No matching nodes found for the provided entities",
    });
  });

  it("keeps isDemo false when a real (non-empty) backend graph arrives", async () => {
    mockedFetchKnowledgeGraph.mockResolvedValue(graph("BRCA1"));
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(
      () => useKnowledgeGraph({ geneSymbol: "BRCA1" }),
      { wrapper },
    );

    await waitFor(() => {
      expect(result.current.isFetching).toBe(false);
    });

    expect(result.current.isDemo).toBe(false);
    expect(result.current.data?.nodes[0]?.display_name).toBe("BRCA1");
  });
});
