import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, readCachedApiResponse } from "@/lib/api/client";
import {
  fetchKnowledgeGraph,
  readCachedKnowledgeGraph,
} from "@/features/graphrag/services/graphRag";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
  readCachedApiResponse: vi.fn(),
}));

const mockedClient = vi.mocked(apiClient);
const mockedReadCachedApiResponse = vi.mocked(readCachedApiResponse);

describe("GraphRAG service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("uses a 60-second timeout for knowledge graph traversal", async () => {
    mockedClient.get.mockResolvedValueOnce({
      data: {
        nodes: [],
        edges: [],
      },
    });

    await expect(fetchKnowledgeGraph({ geneSymbol: "EGFR" })).resolves.toEqual({
      nodes: [],
      edges: [],
    });

    expect(mockedClient.get).toHaveBeenCalledWith(
      "/graphrag/graph",
      expect.objectContaining({
        timeout: 60_000,
        params: expect.objectContaining({
          gene_symbol: "EGFR",
          hops: 2,
          mode: "full",
          limit: 200,
        }),
      }),
    );
  });

  it("forces a backend refresh when requested", async () => {
    mockedClient.get.mockResolvedValueOnce({
      data: { nodes: [], edges: [] },
    });

    await fetchKnowledgeGraph({ geneSymbol: "EGFR" }, { refresh: true });

    expect(mockedClient.get).toHaveBeenCalledWith(
      "/graphrag/graph",
      expect.objectContaining({
        headers: { "Cache-Control": "no-cache" },
      }),
    );
  });

  it("reads the matching graph snapshot without starting a request", () => {
    const cached = {
      nodes: [
        {
          node_id: "gene:EGFR",
          labels: ["Gene"],
          display_name: "EGFR",
          properties: {},
        },
      ],
      edges: [],
    };
    mockedReadCachedApiResponse.mockReturnValueOnce(cached);

    expect(readCachedKnowledgeGraph({ geneSymbol: "EGFR" })).toEqual(cached);
    expect(mockedReadCachedApiResponse).toHaveBeenCalledWith(
      "/graphrag/graph",
      expect.objectContaining({
        gene_symbol: "EGFR",
        hops: 2,
        limit: 200,
        mode: "full",
      }),
      undefined,
    );
    expect(mockedClient.get).not.toHaveBeenCalled();
  });
});
