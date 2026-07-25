import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GraphRagPage } from "../../src/pages/GraphRagPage";

vi.mock("@/features/graphrag/components/GraphRagView", () => ({
  GraphRagView: () => <div data-testid="graph-rag-view">GraphRagView</div>,
}));

describe("GraphRagPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the GraphRagView", () => {
    render(<GraphRagPage />);
    expect(screen.getByTestId("graph-rag-view")).toBeInTheDocument();
  });
});
