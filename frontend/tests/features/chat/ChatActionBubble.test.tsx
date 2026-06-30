import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChatAction } from "../../../src/features/chat/types/actions";
import { ChatActionBubble } from "../../../src/features/chat/components/ChatActionBubble";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const sampleAction: ChatAction = {
  intent: "search-evidence",
  slots: { gene: "BRCA1", variant: "c.5266dupC" },
};

describe("ChatActionBubble", () => {
  // ── Render branches: dispatched / loading / default ────────────

  it("renders default state with 'Click to open' label", () => {
    render(
      <ChatActionBubble action={sampleAction} onDispatch={() => {}} />,
    );
    expect(screen.getByText("Click to open")).toBeInTheDocument();
    expect(screen.getByTestId("chat-action-bubble")).toHaveAttribute(
      "aria-disabled",
      "false",
    );
  });

  it("renders dispatched state with 'Dispatched' label and disabled", () => {
    render(
      <ChatActionBubble
        action={sampleAction}
        dispatched
        onDispatch={() => {}}
      />,
    );
    expect(screen.getByText("Dispatched")).toBeInTheDocument();
    const bubble = screen.getByTestId("chat-action-bubble");
    expect(bubble).toHaveAttribute("aria-disabled", "true");
    expect(bubble).toHaveAttribute("tabindex", "-1");
  });

  it("renders loading state with 'Processing...' label and spinner", () => {
    render(
      <ChatActionBubble action={sampleAction} loading onDispatch={() => {}} />,
    );
    expect(screen.getByText("Processing\u2026")).toBeInTheDocument();
    const bubble = screen.getByTestId("chat-action-bubble");
    expect(bubble).toHaveAttribute("aria-disabled", "true");
    expect(bubble).toHaveAttribute("aria-busy", "true");
    // Loading spinner is a lucide-react Loader2 with the .spin class
    expect(bubble.querySelector(".spin")).toBeInTheDocument();
  });

  it("dispatched state takes precedence over loading (no spinner)", () => {
    render(
      <ChatActionBubble
        action={sampleAction}
        dispatched
        loading
        onDispatch={() => {}}
      />,
    );
    expect(screen.getByText("Dispatched")).toBeInTheDocument();
    // No loading spinner when dispatched
    const bubble = screen.getByTestId("chat-action-bubble");
    expect(bubble.querySelector(".spin")).not.toBeInTheDocument();
  });

  it("renders disabled state via disabled prop", () => {
    render(
      <ChatActionBubble action={sampleAction} disabled onDispatch={() => {}} />,
    );
    const bubble = screen.getByTestId("chat-action-bubble");
    expect(bubble).toHaveAttribute("aria-disabled", "true");
    expect(bubble).toHaveAttribute("tabindex", "-1");
  });

  // ── Click / debounce behaviour ─────────────────────────────────

  it("calls onDispatch exactly once per click even with rapid double-click", () => {
    const onDispatch = vi.fn();
    render(
      <ChatActionBubble action={sampleAction} onDispatch={onDispatch} />,
    );

    const bubble = screen.getByTestId("chat-action-bubble");
    fireEvent.click(bubble);
    fireEvent.click(bubble);
    fireEvent.click(bubble);

    expect(onDispatch).toHaveBeenCalledTimes(1);
    expect(onDispatch).toHaveBeenCalledWith(sampleAction);
  });

  it("does not call onDispatch when dispatched is true", () => {
    const onDispatch = vi.fn();
    render(
      <ChatActionBubble
        action={sampleAction}
        dispatched
        onDispatch={onDispatch}
      />,
    );

    fireEvent.click(screen.getByTestId("chat-action-bubble"));
    expect(onDispatch).not.toHaveBeenCalled();
  });

  it("does not call onDispatch when loading is true", () => {
    const onDispatch = vi.fn();
    render(
      <ChatActionBubble
        action={sampleAction}
        loading
        onDispatch={onDispatch}
      />,
    );

    fireEvent.click(screen.getByTestId("chat-action-bubble"));
    expect(onDispatch).not.toHaveBeenCalled();
  });

  it("does not call onDispatch when disabled is true", () => {
    const onDispatch = vi.fn();
    render(
      <ChatActionBubble
        action={sampleAction}
        disabled
        onDispatch={onDispatch}
      />,
    );

    fireEvent.click(screen.getByTestId("chat-action-bubble"));
    expect(onDispatch).not.toHaveBeenCalled();
  });

  // ── Keyboard accessibility ─────────────────────────────────────

  it('triggers onDispatch on Enter key', () => {
    const onDispatch = vi.fn();
    render(
      <ChatActionBubble action={sampleAction} onDispatch={onDispatch} />,
    );

    const bubble = screen.getByTestId("chat-action-bubble");
    fireEvent.keyDown(bubble, { key: "Enter" });

    expect(onDispatch).toHaveBeenCalledTimes(1);
    expect(onDispatch).toHaveBeenCalledWith(sampleAction);
  });

  it('triggers onDispatch on Space key', () => {
    const onDispatch = vi.fn();
    render(
      <ChatActionBubble action={sampleAction} onDispatch={onDispatch} />,
    );

    const bubble = screen.getByTestId("chat-action-bubble");
    fireEvent.keyDown(bubble, { key: " " });

    expect(onDispatch).toHaveBeenCalledTimes(1);
  });

  it("does not trigger onDispatch on Enter when disabled", () => {
    const onDispatch = vi.fn();
    render(
      <ChatActionBubble
        action={sampleAction}
        dispatched
        onDispatch={onDispatch}
      />,
    );

    fireEvent.keyDown(screen.getByTestId("chat-action-bubble"), {
      key: "Enter",
    });
    expect(onDispatch).not.toHaveBeenCalled();
  });

  it("does not trigger onDispatch on Space when dispatched", () => {
    const onDispatch = vi.fn();
    render(
      <ChatActionBubble
        action={sampleAction}
        dispatched
        onDispatch={onDispatch}
      />,
    );

    fireEvent.keyDown(screen.getByTestId("chat-action-bubble"), { key: " " });
    expect(onDispatch).not.toHaveBeenCalled();
  });

  // ── ARIA attributes ────────────────────────────────────────────

  it('has role="button" for accessibility', () => {
    render(
      <ChatActionBubble action={sampleAction} onDispatch={() => {}} />,
    );
    expect(screen.getByTestId("chat-action-bubble")).toHaveAttribute(
      "role",
      "button",
    );
  });

  it('has tabIndex=0 when interactive (keyboard reachable)', () => {
    render(
      <ChatActionBubble action={sampleAction} onDispatch={() => {}} />,
    );
    expect(screen.getByTestId("chat-action-bubble")).toHaveAttribute(
      "tabindex",
      "0",
    );
  });

  // ── Slot rendering ─────────────────────────────────────────────

  it("renders slot entries as key-value pairs", () => {
    render(
      <ChatActionBubble action={sampleAction} onDispatch={() => {}} />,
    );
    expect(screen.getByText("gene")).toBeInTheDocument();
    expect(screen.getByText("BRCA1")).toBeInTheDocument();
    expect(screen.getByText("variant")).toBeInTheDocument();
    expect(screen.getByText("c.5266dupC")).toBeInTheDocument();
  });

  it("does not render slot section when slots are empty", () => {
    const action: ChatAction = { intent: "classify-variant", slots: {} };
    const { container } = render(
      <ChatActionBubble action={action} onDispatch={() => {}} />,
    );
    // Only one child element (the tag row), no slot grid
    const body = container.querySelector(".ant-card-body");
    expect(body?.children.length).toBe(1);
  });

  it("filters out undefined, null, and empty string slot values", () => {
    const action: ChatAction = {
      intent: "search-evidence",
      slots: { gene: "BRCA1", variant: undefined, disease: "", pmid: null as unknown as string },
    };
    render(<ChatActionBubble action={action} onDispatch={() => {}} />);
    expect(screen.getByText("gene")).toBeInTheDocument();
    expect(screen.getByText("BRCA1")).toBeInTheDocument();
    // variant, disease, pmid should not appear as keys
    expect(screen.queryByText("variant")).not.toBeInTheDocument();
    expect(screen.queryByText("disease")).not.toBeInTheDocument();
    expect(screen.queryByText("pmid")).not.toBeInTheDocument();
  });
});
