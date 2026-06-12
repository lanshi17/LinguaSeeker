/**
 * Minimal, dependency-free Markdown renderer for chat assistant replies.
 *
 * Supports the subset that the backend's ReasoningLLMProvider actually emits
 * (per chat_service.py: **bold**, `inline code`, and prose paragraphs).
 * It also handles fenced code blocks, italic, and unordered lists so common
 * LLM output renders sensibly without pulling in a markdown library.
 *
 * Safety: this renderer NEVER uses dangerouslySetInnerHTML. Output is
 * React elements composed from a fixed allowlist of tags. If a pattern
 * doesn't match, the original text is preserved verbatim.
 *
 * Streaming safety: during a stream, partial tokens may produce half-formed
 * markers (e.g. a trailing `**` with no closer). The renderer treats any
 * unrecognized trailing marker as literal text; once the next chunk arrives
 * the pattern will match.
 */

import type { ReactNode } from "react";
import { Fragment } from "react";

const INLINE_TOKEN_PATTERN =
  /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`)/g;

interface InlineToken {
  type: "text" | "strong" | "em" | "code";
  value: string;
}

function tokenizeInline(line: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let lastIndex = 0;

  for (const match of line.matchAll(INLINE_TOKEN_PATTERN)) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      tokens.push({ type: "text", value: line.slice(lastIndex, start) });
    }

    const raw = match[0];
    if (raw.startsWith("**")) {
      tokens.push({ type: "strong", value: raw.slice(2, -2) });
    } else if (raw.startsWith("`")) {
      tokens.push({ type: "code", value: raw.slice(1, -1) });
    } else {
      tokens.push({ type: "em", value: raw.slice(1, -1) });
    }

    lastIndex = start + raw.length;
  }

  if (lastIndex < line.length) {
    tokens.push({ type: "text", value: line.slice(lastIndex) });
  }

  return tokens;
}

function renderInline(tokens: InlineToken[]): ReactNode[] {
  return tokens.map((token, index) => {
    switch (token.type) {
      case "strong":
        return <strong key={index}>{token.value}</strong>;
      case "em":
        return <em key={index}>{token.value}</em>;
      case "code":
        return (
          <code
            key={index}
            className="rounded bg-gray-100 px-1 py-0.5 font-mono text-[0.9em] text-gray-800"
          >
            {token.value}
          </code>
        );
      default:
        return <Fragment key={index}>{token.value}</Fragment>;
    }
  });
}

interface Block {
  type: "code" | "list" | "paragraph";
  // For "code": the language tag (may be empty).
  // For "list": unused.
  // For "paragraph": unused.
  meta?: string;
  lines: string[];
}

function blockify(source: string): Block[] {
  const blocks: Block[] = [];
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i += 1;
      }
      if (i < lines.length) i += 1;
      blocks.push({ type: "code", meta: lang, lines: codeLines });
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i += 1;
      }
      blocks.push({ type: "list", lines: items });
      continue;
    }

    if (line.trim() === "") {
      i += 1;
      continue;
    }

    // Paragraph: collect contiguous non-blank, non-list, non-fence lines.
    const paragraphLines: string[] = [line];
    i += 1;
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !lines[i].startsWith("```") &&
      !/^\s*[-*]\s+/.test(lines[i])
    ) {
      paragraphLines.push(lines[i]);
      i += 1;
    }
    blocks.push({ type: "paragraph", lines: paragraphLines });
  }

  return blocks;
}

export interface ChatMarkdownProps {
  source: string;
}

export function ChatMarkdown({ source }: ChatMarkdownProps) {
  if (!source) {
    return (
      <span className="italic text-gray-400" data-testid="chat-empty-reply">
        (no response)
      </span>
    );
  }

  const blocks = blockify(source);

  return (
    <div className="chat-markdown space-y-2 leading-relaxed">
      {blocks.map((block, blockIndex) => {
        if (block.type === "code") {
          return (
            <pre
              key={blockIndex}
              className="overflow-x-auto rounded-md bg-gray-900 px-3 py-2 text-sm text-gray-100"
            >
              <code
                className={block.meta ? `language-${block.meta}` : undefined}
              >
                {block.lines.join("\n")}
              </code>
            </pre>
          );
        }

        if (block.type === "list") {
          return (
            <ul
              key={blockIndex}
              className="list-disc space-y-1 pl-6 marker:text-gray-400"
            >
              {block.lines.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(tokenizeInline(item))}</li>
              ))}
            </ul>
          );
        }

        return (
          <p key={blockIndex}>{renderInline(tokenizeInline(block.lines.join(" ")))}</p>
        );
      })}
    </div>
  );
}
