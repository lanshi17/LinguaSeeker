import "@testing-library/jest-dom/vitest";

import type React from "react";
import { App } from "antd";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatUploadTaskCard } from "../../../src/features/chat/components/forms";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderWithApp(ui: React.ReactNode) {
  return render(<App>{ui}</App>);
}

describe("ChatUploadTaskCard", () => {
  it("submits the selected PDF and editable extraction target", () => {
    const file = new File(["%PDF-1.4"], "paper.pdf", {
      type: "application/pdf",
    });
    const onSubmit = vi.fn();

    renderWithApp(
      <ChatUploadTaskCard
        slots={{ source_type: "local", gene_symbol: "BRCA1" }}
        initialFile={file}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByLabelText("Disease"), {
      target: { value: "HBOC" },
    });
    fireEvent.click(screen.getByRole("button", { name: /submit task/i }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        source_type: "local",
        filename: "paper.pdf",
        gene_symbol: "BRCA1",
        disease_name: "HBOC",
      }),
      file,
    );
  });

  it("requires a PDF before task submission", () => {
    const onSubmit = vi.fn();

    renderWithApp(
      <ChatUploadTaskCard
        slots={{ source_type: "local" }}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByRole("button", { name: /submit task/i })).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
