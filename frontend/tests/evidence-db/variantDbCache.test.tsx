import { beforeEach, describe, expect, it, vi } from "vitest";

import type { EvidenceSearchResponse } from "@/features/evidence-search/types/evidenceSearch";
import {
  fetchAllEvidence,
  readCachedAllEvidence,
} from "@/features/evidence-db/services/variantDb";
import {
  readCachedEvidenceSearch,
  searchEvidence,
} from "@/features/evidence-search/services/evidenceSearch";

vi.mock("@/features/evidence-search/services/evidenceSearch", () => ({
  getEvidenceGroupDetail: vi.fn(),
  readCachedEvidenceSearch: vi.fn(),
  searchEvidence: vi.fn(),
}));

const mockedSearchEvidence = vi.mocked(searchEvidence);
const mockedReadCachedEvidenceSearch = vi.mocked(readCachedEvidenceSearch);

function response(
  id: string,
  total: number,
  page: number,
): EvidenceSearchResponse {
  return {
    items: [
      {
        group_id: `group-${id}`,
        source_document_id: `document-${id}`,
        field_count: 1,
        review_status: "provisional",
      },
    ],
    total,
    page,
    page_size: 1,
  };
}

describe("variant database cache", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("forces every backend page to refresh and uses real page numbers", async () => {
    mockedSearchEvidence
      .mockResolvedValueOnce(response("old", 1_001, 1))
      .mockResolvedValueOnce(response("new", 1_001, 2));

    await expect(
      fetchAllEvidence(
        { gene: "MECP2", page: 9, page_size: 25 },
        { refresh: true },
      ),
    ).resolves.toMatchObject({
      items: [
        expect.objectContaining({ group_id: "group-old" }),
        expect.objectContaining({ group_id: "group-new" }),
      ],
      page_size: 2,
    });

    expect(mockedSearchEvidence).toHaveBeenNthCalledWith(
      1,
      { gene: "MECP2", page: 1, page_size: 1_000 },
      undefined,
      { refresh: true },
    );
    expect(mockedSearchEvidence).toHaveBeenNthCalledWith(
      2,
      { gene: "MECP2", page: 2, page_size: 1_000 },
      undefined,
      { refresh: true },
    );
  });

  it("rebuilds a complete cached view from all cached pages", () => {
    mockedReadCachedEvidenceSearch
      .mockReturnValueOnce(response("cached-1", 1_001, 1))
      .mockReturnValueOnce(response("cached-2", 1_001, 2));

    expect(readCachedAllEvidence({ gene: "MECP2" })).toMatchObject({
      items: [
        expect.objectContaining({ group_id: "group-cached-1" }),
        expect.objectContaining({ group_id: "group-cached-2" }),
      ],
      page_size: 2,
    });
  });

  it("does not expose a partial cached view when a page is missing", () => {
    mockedReadCachedEvidenceSearch
      .mockReturnValueOnce(response("cached-1", 1_001, 1))
      .mockReturnValueOnce(undefined);

    expect(readCachedAllEvidence({ gene: "MECP2" })).toBeUndefined();
  });
});
