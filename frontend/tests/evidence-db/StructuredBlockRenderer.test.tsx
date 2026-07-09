import "@testing-library/jest-dom/vitest";

import { App as AntdApp } from "antd";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StructuredBlockRenderer } from "../../src/features/evidence-db/components/StructuredBlockRenderer";
import {
  FieldReviewMenu,
} from "../../src/features/evidence-search/components/FieldReviewPopover";
import type { ReviewContextMap } from "../../src/features/evidence-search/components/fieldReviewMenuBus";

describe("StructuredBlockRenderer", () => {
  it("opens the field review menu from structured block highlights", async () => {
    const text = "BRCA1 was detected in the proband.";
    const start = text.indexOf("BRCA1");
    const reviewContexts: ReviewContextMap = new Map([
      [
        "evidence-1",
        {
          evidenceId: "evidence-1",
          fieldId: "A.gene_symbol",
          label: "Gene symbol",
          category: "A",
          currentStatus: "provisional",
          value: "BRCA1",
          groupId: "group-1",
        },
      ],
    ]);

    render(
      <AntdApp>
        <FieldReviewMenu />
        <StructuredBlockRenderer
          blocks={[{ type: "text", text }]}
          highlights={[
            {
              evidenceId: "evidence-1",
              fieldId: "A.gene_symbol",
              label: "Gene symbol",
              tone: "gene",
              category: "A",
              globalStart: start,
              globalEnd: start + "BRCA1".length,
              selected: false,
            },
          ]}
          reviewContexts={reviewContexts}
        />
      </AntdApp>,
    );

    const mark = screen.getByText("BRCA1");
    expect(mark).toHaveAttribute("data-reviewable", "true");

    fireEvent.click(mark);

    expect(screen.getByText("Gene symbol")).toBeInTheDocument();
    expect(screen.getByText("A.gene_symbol")).toBeInTheDocument();
    expect(screen.getByText("provisional")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText("Gene symbol")).toBeInTheDocument());
    await new Promise((resolve) => setTimeout(resolve, 20));
    fireEvent.mouseDown(mark);

    expect(screen.getByText("Gene symbol")).toBeInTheDocument();
  });
});
