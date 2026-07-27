import "@testing-library/jest-dom/vitest";

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GraphRagView } from "../../../src/features/graphrag/components/GraphRagView";

const mutateAsync = vi.fn();

vi.mock("@/lib/i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("../../../src/features/graphrag/hooks/useGraphRagQuery", () => ({
  useGraphRagQuery: () => ({
    mutateAsync,
    data: null,
    isPending: false,
    error: null,
  }),
}));

vi.mock(
  "../../../src/features/graphrag/components/KnowledgeGraphCanvas",
  () => ({
    KnowledgeGraphCanvas: () => <div data-testid="knowledge-graph" />,
  }),
);

describe("GraphRagView", () => {
  afterEach(() => {
    cleanup();
    mutateAsync.mockReset();
  });

  it("renders the question form", () => {
    render(<GraphRagView />);
    expect(screen.getByText("graphRag.title")).toBeInTheDocument();
    expect(screen.getByLabelText("graphRag.questionLabel")).toBeInTheDocument();
    expect(screen.getByText("graphRag.askButton")).toBeInTheDocument();
  });

  it("submits the question when the form is valid", async () => {
    mutateAsync.mockResolvedValueOnce({
      question: "What is GLA?",
      answer: "GLA is a gene.",
      subgraph: { nodes: [], edges: [] },
      source_evidence_ids: [],
      citations: [],
    });

    render(<GraphRagView />);
    const textarea = screen.getByLabelText("graphRag.questionLabel");
    fireEvent.change(textarea, { target: { value: "What is GLA?" } });
    fireEvent.click(screen.getByText("graphRag.askButton"));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        question: "What is GLA?",
        hops: 2,
        mode: "full",
      });
    });
  });
});
