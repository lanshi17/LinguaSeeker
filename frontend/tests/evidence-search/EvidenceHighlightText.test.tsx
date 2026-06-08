import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvidenceHighlightText } from "../../src/features/evidence-search/components/EvidenceHighlightText";

describe("EvidenceHighlightText", () => {
  it("keeps the existing empty-state guard", () => {
    render(<EvidenceHighlightText highlight={null} />);

    expect(screen.getByText("No source span available.")).toBeInTheDocument();
  });

  it("renders a mark when the highlight range is non-empty", () => {
    const { container } = render(
      <EvidenceHighlightText
        active
        highlight={{
          text: "BRCA1 was detected.",
          highlight_start: 0,
          highlight_end: 5,
          page: 3,
          source_span: {},
        }}
      />,
    );

    const mark = container.querySelector("mark");
    expect(mark).toHaveTextContent("BRCA1");
    expect(screen.queryByText("highlight unavailable")).not.toBeInTheDocument();
  });

  it("shows highlight-unavailable feedback for zero-length ranges", () => {
    const { container } = render(
      <EvidenceHighlightText
        highlight={{
          text: "The source text is available.",
          highlight_start: 0,
          highlight_end: 0,
          page: null,
          source_span: {},
        }}
      />,
    );

    expect(container.querySelector("mark")).not.toBeInTheDocument();
    expect(screen.getByText("highlight unavailable")).toBeInTheDocument();
    expect(screen.getByText("The source text is available.")).toBeInTheDocument();
  });
});
