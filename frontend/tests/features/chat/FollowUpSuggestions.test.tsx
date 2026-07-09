import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FollowUpSuggestions } from "../../../src/features/chat/components/FollowUpSuggestions";
import { buildFollowUpQuestions } from "../../../src/features/chat/utils/followUpSuggestions";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("FollowUpSuggestions", () => {
  it("builds evidence-focused questions for evidence replies", () => {
    const t = (key: string) =>
      ({
        "chat.followUps.evidenceGaps": "Which evidence gaps should I resolve next?",
        "chat.followUps.nextStep": "What should I do next?",
        "chat.followUps.pipelineStatus": "Check the task status for me",
        "chat.followUps.summarize": "Summarize the key points in 3 bullets",
        "chat.followUps.verifyEvidence": "Which evidence should I verify manually?",
      })[key] ?? key;

    expect(buildFollowUpQuestions("The BRCA1 evidence is mixed.", t)[0]).toBe(
      "Which evidence gaps should I resolve next?",
    );
  });

  it("sends the selected question through the chat action callback", () => {
    const onPick = vi.fn();

    render(
      <FollowUpSuggestions
        content="The evidence summary is ready."
        onPick={onPick}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: "Which evidence gaps should I resolve next?",
      }),
    );

    expect(onPick).toHaveBeenCalledWith({
      kind: "send-message",
      message: "Which evidence gaps should I resolve next?",
    });
  });
});
