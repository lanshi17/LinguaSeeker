import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GraphRagView } from "../../../src/features/graphrag/components/GraphRagView";

vi.mock(
  "../../../src/features/graphrag/components/EntityGraphExplorer",
  () => ({
    EntityGraphExplorer: () => <div data-testid="entity-explorer" />,
  }),
);

describe("GraphRagView", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the entity explorer workspace", () => {
    render(<GraphRagView />);
    expect(screen.getByTestId("entity-explorer")).toBeInTheDocument();
  });
});
