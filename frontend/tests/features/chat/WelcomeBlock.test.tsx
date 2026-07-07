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

  it("sends an interactive upload prompt for source upload", () => {
    const onPick = vi.fn();

    render(<WelcomeBlock onPick={onPick} />);
    fireEvent.click(screen.getByRole("button", { name: /upload source paper/i }));

    expect(onPick).toHaveBeenCalledWith({
      kind: "send-message",
      message:
        "I want to upload a PDF source paper for bilingual evidence extraction. Please collect any needed target details and ask for final confirmation before showing the in-chat upload control.",
    });
  });

  it("sends an interactive search prompt for the evidence-base shortcut", () => {
    const onPick = vi.fn();

    render(<WelcomeBlock onPick={onPick} />);
    fireEvent.click(screen.getByRole("button", { name: /search evidence base/i }));

    expect(onPick).toHaveBeenCalledWith({
      kind: "send-message",
      message:
        "Help me search the evidence base by gene, variant, disease, PMID, or DOI.",
    });
  });

  it("sends an interactive review prompt for review and export", () => {
    const onPick = vi.fn();

    render(<WelcomeBlock onPick={onPick} />);
    fireEvent.click(screen.getByRole("button", { name: /review and export/i }));

    expect(onPick).toHaveBeenCalledWith({
      kind: "send-message",
      message:
        "Help me review evidence items that need expert review and prepare an evidence summary report.",
    });
  });
});
