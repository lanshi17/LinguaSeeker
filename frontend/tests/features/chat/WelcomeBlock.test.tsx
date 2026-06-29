import "@testing-library/jest-dom/vitest";

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { WelcomeBlock } from "../../../src/features/chat/components/WelcomeBlock";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("WelcomeBlock", () => {
  it("sends a structured pipeline prompt for the pipeline quick action", () => {
    const onPick = vi.fn();

    render(<WelcomeBlock onPick={onPick} />);
    fireEvent.click(screen.getByRole("button", { name: /run evidence pipeline/i }));

    expect(onPick).toHaveBeenCalledWith({
      kind: "send-message",
      message:
        "Start an online evidence pipeline. Identifier: PMID 28499369. Use bilingual extraction and source-grounded evidence review.",
    });
  });

  it("navigates directly to the pipeline page for source upload", () => {
    const onPick = vi.fn();

    render(<WelcomeBlock onPick={onPick} />);
    fireEvent.click(screen.getByRole("button", { name: /upload source paper/i }));

    expect(onPick).toHaveBeenCalledWith({
      kind: "navigate",
      to: "/pipeline",
      fallbackMessage:
        "Open the pipeline page so I can upload a PDF for bilingual evidence extraction.",
    });
  });

  it("navigates directly to evidence search for the evidence-base shortcut", () => {
    const onPick = vi.fn();

    render(<WelcomeBlock onPick={onPick} />);
    fireEvent.click(screen.getByRole("button", { name: /search evidence base/i }));

    expect(onPick).toHaveBeenCalledWith({
      kind: "navigate",
      to: "/evidence",
      fallbackMessage:
        "Open the evidence database so I can search by gene, variant, disease, PMID, or DOI.",
    });
  });

  it("opens the pending review queue for review and export", () => {
    const onPick = vi.fn();

    render(<WelcomeBlock onPick={onPick} />);
    fireEvent.click(screen.getByRole("button", { name: /review and export/i }));

    expect(onPick).toHaveBeenCalledWith({
      kind: "navigate",
      to: "/evidence?review_status=pending",
      fallbackMessage:
        "Show evidence items that need expert review and help prepare an evidence summary report.",
    });
  });
});
