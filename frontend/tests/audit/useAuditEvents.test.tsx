import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAuditEvents } from "@/features/audit/hooks/useAuditEvents";
import { listAuditEvents } from "@/features/audit/services/audit";

vi.mock("@/features/audit/services/audit", () => ({
  listAuditEvents: vi.fn(async () => []),
}));

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useAuditEvents", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps source-document scoped audit queries in separate cache entries", async () => {
    const { rerender } = renderHook(
      ({ sourceDocumentId }) =>
        useAuditEvents({
          source_document_id: sourceDocumentId,
          limit: 20,
        }),
      {
        initialProps: { sourceDocumentId: "doc-a" },
        wrapper,
      },
    );

    await waitFor(() => expect(listAuditEvents).toHaveBeenCalledTimes(1));

    rerender({ sourceDocumentId: "doc-b" });

    await waitFor(() => expect(listAuditEvents).toHaveBeenCalledTimes(2));
    expect(vi.mocked(listAuditEvents).mock.calls).toEqual([
      [{ source_document_id: "doc-a", limit: 20 }],
      [{ source_document_id: "doc-b", limit: 20 }],
    ]);
  });
});
