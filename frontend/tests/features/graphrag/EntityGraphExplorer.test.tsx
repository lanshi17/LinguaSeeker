import "@testing-library/jest-dom/vitest";

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MemoryRouter } from "react-router-dom";

import { EntityGraphExplorer } from "../../../src/features/graphrag/components/EntityGraphExplorer";

function renderExplorer() {
  return render(
    <MemoryRouter>
      <EntityGraphExplorer />
    </MemoryRouter>,
  );
}

const useKnowledgeGraph = vi.fn();

vi.mock("@/lib/i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

vi.mock("../../../src/features/graphrag/hooks/useKnowledgeGraph", () => ({
  useKnowledgeGraph: (options: unknown) => useKnowledgeGraph(options),
}));

vi.mock(
  "../../../src/features/graphrag/components/KnowledgeGraphCanvas",
  () => ({
    KnowledgeGraphCanvas: () => <div data-testid="knowledge-graph" />,
  }),
);

describe("EntityGraphExplorer", () => {
  afterEach(() => {
    cleanup();
    useKnowledgeGraph.mockReset();
  });

  it("queries an example gene on first load", () => {
    useKnowledgeGraph.mockReturnValue({
      data: {
        nodes: [
          { node_id: "gene:EGFR", labels: ["Gene"], display_name: "EGFR", properties: {} },
        ],
        edges: [],
      },
      isFetching: false,
      error: null,
    });

    renderExplorer();

    // Default example graph: query is enabled and seeded with the example gene.
    expect(useKnowledgeGraph).toHaveBeenCalledWith(
      expect.objectContaining({
        geneSymbol: "EGFR",
        mode: "full",
        enabled: true,
      }),
    );
    expect(screen.getByTestId("knowledge-graph")).toBeInTheDocument();
    expect(screen.getByText("graphRag.exampleTag")).toBeInTheDocument();
  });

  it("submits entered entities and enables the query", async () => {
    useKnowledgeGraph.mockReturnValue({
      data: undefined,
      isFetching: false,
      error: null,
    });

    renderExplorer();
    fireEvent.change(screen.getByLabelText("graphRag.geneLabel"), {
      target: { value: "COL2A1" },
    });
    fireEvent.click(screen.getByText("graphRag.exploreButton"));

    await waitFor(() => {
      expect(useKnowledgeGraph).toHaveBeenLastCalledWith(
        expect.objectContaining({
          geneSymbol: "COL2A1",
          mode: "full",
          enabled: true,
        }),
      );
    });
  });

  it("renders the graph canvas when nodes are returned", async () => {
    useKnowledgeGraph.mockReturnValue({
      data: {
        nodes: [
          { node_id: "gene:COL2A1", labels: ["Gene"], display_name: "COL2A1", properties: {} },
        ],
        edges: [],
      },
      isFetching: false,
      error: null,
    });

    renderExplorer();
    fireEvent.change(screen.getByLabelText("graphRag.geneLabel"), {
      target: { value: "COL2A1" },
    });
    fireEvent.click(screen.getByText("graphRag.exploreButton"));

    expect(await screen.findByTestId("knowledge-graph")).toBeInTheDocument();
  });
});
