import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HighlightedText } from "../../src/features/evidence-db/components/HighlightedText";

describe("HighlightedText alignment spans", () => {
  it("renders alignment spans and emits hover/click events", () => {
    const onHover = vi.fn();
    const onLeave = vi.fn();
    const onToggle = vi.fn();
    const text = "A pathogenic c.194delC mutation was found in MECP2.";
    const start = text.indexOf("c.194delC");

    render(
      <HighlightedText
        paragraph={{
          id: "translated-full-text",
          text,
          highlights: [],
        }}
        alignmentHighlights={[
          {
            pairId: "c_0001-p_0001",
            start,
            end: start + "c.194delC".length,
            active: false,
            pinned: false,
            confidence: 0.96,
            method: "semantic_llm",
          },
        ]}
        onAlignmentHover={onHover}
        onAlignmentLeave={onLeave}
        onAlignmentToggle={onToggle}
      />,
    );

    const span = screen.getByText("c.194delC");
    expect(span).toHaveAttribute("data-alignment-pair-id", "c_0001-p_0001");

    fireEvent.mouseEnter(span);
    fireEvent.mouseLeave(span);
    fireEvent.click(span);

    expect(onHover).toHaveBeenCalledWith("c_0001-p_0001");
    expect(onLeave).toHaveBeenCalledTimes(1);
    expect(onToggle).toHaveBeenCalledWith("c_0001-p_0001");
  });

  it("marks linked active spans", () => {
    const text = "MECP2基因存在c.194delC致病性突变。";
    const start = text.indexOf("c.194delC");

    const { container } = render(
      <HighlightedText
        paragraph={{
          id: "original-full-text",
          text,
          highlights: [],
        }}
        alignmentHighlights={[
          {
            pairId: "c_0001-p_0001",
            start,
            end: start + "c.194delC".length,
            active: true,
            pinned: true,
            confidence: 0.96,
            method: "semantic_llm",
          },
        ]}
      />,
    );

    expect(container.querySelector("[data-alignment-active='true']")).toHaveTextContent("c.194delC");
  });
});
