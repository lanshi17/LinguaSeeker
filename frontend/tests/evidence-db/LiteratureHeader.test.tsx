import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LiteratureHeader } from "../../src/features/evidence-db/components/LiteratureHeader";
import type { EvidenceGroupDetailResponse } from "../../src/features/evidence-search/types/evidenceSearch";

const baseDetail: EvidenceGroupDetailResponse = {
  group_id: "group-1",
  source_document_id: "doc-1",
  title: "Untitled Document",
  pmid: null,
  doi: null,
  gene: null,
  variant: null,
  disease: null,
  classification: null,
  item_count: 8,
  avg_confidence: 0.84,
  distribution: {
    by_category: {},
    by_field: {},
    by_status: {},
    by_track: {},
  },
  items: [],
  traces: [],
};

describe("LiteratureHeader", () => {
  it("renders an export report button when an export handler is provided", () => {
    const onExportReport = vi.fn();

    render(
      <LiteratureHeader
        groupDetail={baseDetail}
        onExportReport={onExportReport}
      />,
    );

    const exportButton = screen.getByRole("button", { name: /export report/i });
    expect(exportButton).toBeInTheDocument();

    fireEvent.click(exportButton);

    expect(onExportReport).toHaveBeenCalledTimes(1);
  });
});
