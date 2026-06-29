import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActiveEvidenceCard } from "../../src/features/evidence-db/components/ActiveEvidenceCard";
import type { EvidenceGroupItem } from "../../src/features/evidence-search/types/evidenceSearch";

const baseItem: EvidenceGroupItem = {
  canonical_evidence_id: "evidence-1",
  field_id: "A.gene_symbol",
  field_name: "Gene symbol",
  category: "A",
  value: "FLCN",
  review_status: "approved",
  confidence: 0.91,
  track: "reconciled",
  page: 3,
};

describe("ActiveEvidenceCard", () => {
  it("renders review status and source span availability", () => {
    render(<ActiveEvidenceCard item={baseItem} sourceSpanAvailable />);

    expect(screen.getByText("approved")).toBeInTheDocument();
    expect(screen.getByText("Source span")).toBeInTheDocument();
  });

  it("renders missing source span state", () => {
    render(<ActiveEvidenceCard item={baseItem} />);

    expect(screen.getByText("No source span")).toBeInTheDocument();
  });
});
