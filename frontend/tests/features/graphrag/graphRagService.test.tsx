import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/lib/api/client";
import { fetchKnowledgeGraph } from "@/features/graphrag/services/graphRag";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedClient = vi.mocked(apiClient);

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
});
