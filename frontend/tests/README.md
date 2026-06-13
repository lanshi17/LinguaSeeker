# Tests

> Frontend test suite for CrossEvidence. Uses **Vitest** with React Testing Library. Test organization mirrors the `src/` source structure.

## Quick Start

```bash
cd frontend

# Run all tests
npm run test

# Run in watch mode
npm run test -- --watch

# Run a specific test file
npm run test -- tests/features/chat/sse.test.ts

# Run tests by path pattern
npm run test -- --testPathPattern=features/chat

# Run with coverage
npm run test -- --coverage
```

## Directory Map

```
tests/
├── config/
│   └── layeredConfig.test.ts           Layered configuration loading
├── evidence-search/
│   ├── BilingualComparison.test.tsx     Bilingual comparison component
│   ├── literatureRows.test.ts           Literature row rendering
│   └── EvidenceHighlightText.test.tsx   Evidence text highlighting
├── features/
│   ├── auth/                            (placeholder)
│   ├── chat/
│   │   ├── ChatMarkdown.test.tsx        Chat markdown rendering
│   │   ├── intent.test.ts               Chat intent detection
│   │   ├── localSessions.test.ts        Local session persistence
│   │   ├── messageHistory.test.ts       Message history management
│   │   ├── messageRequests.test.ts      Message request handling
│   │   └── sse.test.ts                  SSE streaming
│   ├── delta-audit/                     (placeholder)
│   ├── document-viewer/                 (placeholder)
│   ├── evidence/                        (placeholder)
│   ├── graph/                           (placeholder)
│   ├── literature/                      (placeholder)
│   ├── pipeline/                        (placeholder)
│   ├── source-link/                     (placeholder)
│   └── task-flow/                       (placeholder)
├── components/
│   └── ui/                              (placeholder)
└── lib/
    └── api/                             (placeholder)
```

## Test Coverage by Area

| Area | File(s) | What is tested |
|------|---------|----------------|
| **Config** | `layeredConfig.test.ts` | Layered config loading, env override, defaults |
| **Evidence Search** | `BilingualComparison.test.tsx` | Side-by-side bilingual evidence display |
| | `literatureRows.test.ts` | Literature row rendering and formatting |
| | `EvidenceHighlightText.test.tsx` | Evidence text highlight markup |
| **Chat** | `ChatMarkdown.test.tsx` | Markdown rendering in chat messages |
| | `intent.test.ts` | Chat intent classification logic |
| | `localSessions.test.ts` | Session persistence in localStorage |
| | `messageHistory.test.ts` | Message history state management |
| | `messageRequests.test.ts` | Message request construction and dispatch |
| | `sse.test.ts` | SSE connection, reconnection, and event parsing |

## Writing Tests

### Component Tests

Use React Testing Library for component rendering and interaction:

```tsx
import { render, screen } from "@testing-library/react";
import { ChatMarkdown } from "@/features/chat/components/ChatMarkdown";

it("renders markdown content", () => {
  render(<ChatMarkdown content="**bold** text" />);
  expect(screen.getByText("bold")).toBeInTheDocument();
});
```

### Unit Tests

Plain TypeScript tests for hooks, utilities, and services:

```ts
import { detectIntent } from "@/features/chat/utils/intent";

it("detects question intent", () => {
  expect(detectIntent("What is the ACMG classification?")).toBe("question");
});
```

### Naming Convention

- Test files: `<ModuleName>.test.ts` or `<ModuleName>.test.tsx`
- Test functions: `it("<behavior description>")` or `test("<behavior description>")`
- Directory structure mirrors `src/` (e.g., `tests/features/chat/` tests `src/features/chat/`)
