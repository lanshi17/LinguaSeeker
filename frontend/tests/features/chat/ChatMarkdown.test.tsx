import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ChatMarkdown } from "../../../src/features/chat/utils/markdown";

afterEach(() => cleanup());

describe("ChatMarkdown", () => {
  it("renders empty string as empty", () => {
    const { container } = render(<ChatMarkdown source="" />);
    expect(container.querySelector(".chat-markdown")).toBeNull();
  });

  it("renders plain text as a paragraph", () => {
    render(<ChatMarkdown source="Hello world" />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders **bold** as <strong>", () => {
    render(<ChatMarkdown source="This is **bold** text." />);
    const strong = screen.getByText("bold");
    expect(strong.tagName).toBe("STRONG");
  });

  it("renders `inline code` with monospace styling", () => {
    const { container } = render(<ChatMarkdown source="Use `foo()` here." />);
    const code = screen.getByText("foo()");
    expect(code.tagName).toBe("CODE");
    // Also check the monospace class
    const codeEl = container.querySelector("code");
    expect(codeEl?.className).toMatch(/font-mono/);
  });

  it("renders a fenced code block", () => {
    const { container } = render(
      <ChatMarkdown source={"```\nconst x = 1;\n```"} />,
    );
    const pre = container.querySelector("pre");
    expect(pre).toBeInTheDocument();
    expect(pre!.textContent).toContain("const x = 1;");
  });

  it("renders an unordered list", () => {
    render(<ChatMarkdown source={"- first\n- second"} />);
    const items = document.querySelectorAll("li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("first");
    expect(items[1].textContent).toBe("second");
  });

  it("renders *italic* as <em>", () => {
    render(<ChatMarkdown source={"this is *italic* here"} />);
    const em = screen.getByText("italic");
    expect(em.tagName).toBe("EM");
  });

  it("renders mixed inline formatting", () => {
    render(<ChatMarkdown source={"**bold** `code` *italic* end"} />);
    expect(screen.getByText("bold").tagName).toBe("STRONG");
    expect(screen.getByText("code").tagName).toBe("CODE");
    expect(screen.getByText("italic").tagName).toBe("EM");
  });

  it("handles **mentioning without closure as text", () => {
    render(<ChatMarkdown source={"this is **bold text"} />);
    const text = screen.getByText("this is **bold text");
    expect(text).toBeInTheDocument();
  });
});
