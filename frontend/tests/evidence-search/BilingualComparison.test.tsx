import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BilingualComparison } from "../../src/features/evidence-search/components/BilingualComparison";

const baseTrace = {
  canonical_evidence_id: "evidence-1",
  field_id: "A.gene_symbol",
  field_name: "Gene symbol",
  original_value: "BRCA1",
  translated_value: "BRCA1",
  original: {
    text: "BRCA1 was detected.",
    highlight_start: 0,
    highlight_end: 5,
    page: 1,
    source_span: {},
  },
  translated: {
    text: "检测到 BRCA1。",
    highlight_start: 4,
    highlight_end: 9,
    page: 1,
    source_span: {},
  },
  alignment_confidence: 1,
};

describe("BilingualComparison (trace props)", () => {
  it("renders original and translated value anchors", () => {
    render(<BilingualComparison trace={baseTrace} />);

    expect(screen.getByText("Original value")).toBeInTheDocument();
    expect(screen.getByText("Translated value")).toBeInTheDocument();
    expect(screen.getAllByText("BRCA1").length).toBeGreaterThanOrEqual(2);
  });

  it("renders an empty state when no trace is selected", () => {
    render(<BilingualComparison trace={null} />);

    expect(screen.getByText("No evidence selected.")).toBeInTheDocument();
  });
});

describe("BilingualComparison (detail props)", () => {
  const baseDetail = {
    group_id: "group-1",
    source_document_id: "doc-1",
    title: null,
    pmid: null,
    doi: null,
    gene: null,
    variant: null,
    disease: null,
    classification: null,
    item_count: 1,
    avg_confidence: null,
    distribution: {
      by_category: {},
      by_field: {},
      by_status: {},
      by_track: {},
    },
    items: [
      {
        canonical_evidence_id: "evidence-1",
        field_id: "A.gene_symbol",
        field_name: "Gene symbol",
        category: "A",
        value: "BRCA1",
        review_status: "provisional",
        confidence: 1,
        track: "original",
        page: 1,
      },
    ],
    traces: [baseTrace],
  };

  it("renders the value pair banner from the selected trace", () => {
    render(
      <BilingualComparison
        detail={baseDetail}
        groupId="group-1"
        selectedEvidenceId="evidence-1"
        setSelectedEvidenceId={() => undefined}
      />,
    );

    expect(screen.getByText("Original value")).toBeInTheDocument();
    expect(screen.getByText("Translated value")).toBeInTheDocument();
  });

  it("shows an empty state when the detail has no traces", () => {
    render(
      <BilingualComparison
        detail={{ ...baseDetail, items: [], traces: [] }}
        groupId="group-1"
        selectedEvidenceId={null}
        setSelectedEvidenceId={() => undefined}
      />,
    );

    expect(
      screen.getByText("No bilingual traces for this evidence group."),
    ).toBeInTheDocument();
  });
});
