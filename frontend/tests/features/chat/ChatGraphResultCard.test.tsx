import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatGraphResultCard } from "../../../src/features/chat/components/ChatGraphResultCard";

vi.mock("@/lib/i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

vi.mock("@/features/graphrag", () => ({
  KnowledgeGraphCanvas: () => <div data-testid="knowledge-graph" />,
}));

function renderCard(props: Parameters<typeof ChatGraphResultCard>[0]) {
  return render(
    <MemoryRouter>
      <ChatGraphResultCard {...props} />
    </MemoryRouter>,
  );
}

describe("ChatGraphResultCard", () => {
  afterEach(cleanup);

  it("shows a loading state while querying", () => {
    renderCard({ question: "q", status: "loading" });
    expect(screen.getByText("chat.graph.loading")).toBeInTheDocument();
  });

  it("shows an error state on failure", () => {
    renderCard({ question: "q", status: "error", error: "boom" });
    expect(screen.getByText("chat.graph.error")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
  });

  it("renders the grounded answer and graph on success", () => {
    renderCard({
      question: "q",
      status: "done",
      answer: "COL2A1 is associated with Stickler syndrome.",
      subgraph: {
        nodes: [
          {
            node_id: "gene:COL2A1",
            labels: ["Gene"],
            display_name: "COL2A1",
            properties: {},
          },
        ],
        edges: [],
      },
    });
    expect(
      screen.getByText("COL2A1 is associated with Stickler syndrome."),
    ).toBeInTheDocument();
    expect(screen.getByTestId("knowledge-graph")).toBeInTheDocument();
    expect(screen.getByText("chat.graph.viewInGraph")).toBeInTheDocument();
  });

  it("omits the graph when the answer has no subgraph", () => {
    renderCard({ question: "q", status: "done", answer: "No data." });
    expect(screen.getByText("No data.")).toBeInTheDocument();
    expect(screen.queryByTestId("knowledge-graph")).not.toBeInTheDocument();
  });
});
