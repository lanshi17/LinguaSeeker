import "@testing-library/jest-dom/vitest";

import { App } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EvidenceReviewDrawer } from "@/features/audit/components/EvidenceReviewDrawer";
import { searchEvidence, getEvidenceGroupDetail } from "@/features/evidence-search/services/evidenceSearch";

vi.mock("@/features/evidence-search/services/evidenceSearch", () => ({
  searchEvidence: vi.fn(async () => ({
    items: [
      {
        group_id: "audit-group-1",
        source_document_id: "source-doc-1",
        gene: "GLA",
        variant: "c.1A>G",
        disease: "Fabry disease",
        classification: "VUS",
        field_count: 2,
        avg_confidence: 0.91,
        review_status: "provisional",
        canonical_evidence_id: "00000000-0000-0000-0000-000000000001",
        created_at: "2026-06-23T00:00:00Z",
      },
    ],
    total: 1,
    page: 1,
    page_size: 50,
  })),
  getEvidenceGroupDetail: vi.fn(async () => ({
    group_id: "audit-group-1",
    source_document_id: "source-doc-1",
    gene: "GLA",
    variant: "c.1A>G",
    disease: "Fabry disease",
    classification: "VUS",
    item_count: 1,
    avg_confidence: 0.91,
    distribution: { by_category: {}, by_field: {}, by_status: {}, by_track: {} },
    items: [
      {
        canonical_evidence_id: "00000000-0000-0000-0000-000000000001",
        field_id: "B.disease_diagnosis",
        field_name: "Disease diagnosis",
        category: "disease",
        value: "Fabry disease",
        review_status: "provisional",
      },
    ],
    traces: [],
  })),
}));

vi.mock("@/features/evidence-search/services/evidenceCorrection", () => ({
  patchEvidence: vi.fn(async () => ({ deltas: 1 })),
}));

function renderWithProviders(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App>{children}</App>
    </QueryClientProvider>,
  );
}

describe("EvidenceReviewDrawer", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("exposes the review status selector by accessible name", async () => {
    renderWithProviders(<EvidenceReviewDrawer open onClose={() => {}} />);

    fireEvent.change(screen.getByPlaceholderText("Gene"), {
      target: { value: "GLA" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply filter" }));

    await screen.findByText("GLA / c.1A>G");
    fireEvent.click(screen.getByText("GLA / c.1A>G"));

    await waitFor(() => expect(getEvidenceGroupDetail).toHaveBeenCalled());
    await screen.findByText("Disease diagnosis");
    expect(
      screen.getByRole("combobox", { name: "New status" }),
    ).toBeInTheDocument();
    expect(searchEvidence).toHaveBeenCalledWith({
      gene: "GLA",
      variant: undefined,
      disease: undefined,
      page_size: 50,
    });
  });
});
