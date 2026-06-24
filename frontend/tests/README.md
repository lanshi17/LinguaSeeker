# Tests

> Frontend test suite for LinguaSeeker. Uses **Vitest** with jsdom environment and React Testing Library. Test organization mirrors the `src/` source structure.

## Quick Start

```bash
cd frontend

# Run all tests
bun run test

# Run a specific test file
bun run test tests/features/chat/sse.test.ts

# Run with coverage
bun run test --coverage

# Type checking
bun run type-check
```

## Directory Map

```
tests/
|-- audit/
|   |-- reviewPatch.test.tsx               Review patch operation building
|   +-- useAuditEvents.test.tsx            Audit events hook
|-- config/
|   +-- layeredConfig.test.ts              Layered configuration loading
|-- evidence-db/
|   +-- variantAggregation.test.tsx        Variant aggregation utilities
|-- evidence-search/
|   |-- BilingualComparison.test.tsx       Bilingual comparison component
|   |-- EvidenceHighlightText.test.tsx     Evidence text highlighting
|   +-- literatureRows.test.ts             Literature row aggregation
+-- features/
    +-- chat/
        |-- acmgChatProvider.test.tsx      Chat provider behavior
        |-- ChatActionBubble.test.tsx      Action bubble rendering
        |-- ChatMarkdown.test.tsx          Markdown rendering in chat
        |-- localSessions.test.ts          Local session persistence
        |-- messageHistory.test.ts         Message history management
        |-- messageRequests.test.ts        Message request construction
        |-- messageStore.test.tsx          Message store behavior
        |-- sse.test.ts                    SSE event parsing
        +-- useChatSessions.test.tsx       Chat sessions hook
```

## Test Coverage by Area

| Area | File(s) | What is tested |
|------|---------|----------------|
| **Audit** | `reviewPatch.test.tsx` | `buildReviewPatchOperations()` and `cardFieldForFieldId()` |
| | `useAuditEvents.test.tsx` | Audit events React Query hook |
| **Config** | `layeredConfig.test.ts` | Layered config loading, env override, defaults |
| **Evidence DB** | `variantAggregation.test.tsx` | Variant aggregation and filtering utilities |
| **Evidence Search** | `BilingualComparison.test.tsx` | Side-by-side bilingual evidence display |
| | `EvidenceHighlightText.test.tsx` | Evidence text highlight markup |
| | `literatureRows.test.ts` | Literature row building, grouping by source_document_id, confidence averaging |
| **Chat** | `acmgChatProvider.test.tsx` | Chat provider request/response behavior |
| | `ChatActionBubble.test.tsx` | Action intent bubble rendering |
| | `ChatMarkdown.test.tsx` | Markdown rendering in chat messages |
| | `localSessions.test.ts` | Session persistence in localStorage |
| | `messageHistory.test.ts` | Message history state management and conversion |
| | `messageRequests.test.ts` | Message request construction and dispatch |
| | `messageStore.test.tsx` | Message store state management |
| | `sse.test.ts` | SSE event parsing: text, action, done, keepalive, error |
| | `useChatSessions.test.tsx` | Chat sessions React Query hook |

## Writing Tests

### Component Tests

Use React Testing Library for component rendering and interaction:

```tsx
import { render, screen } from "@testing-library/react";

it("renders content", () => {
  render(<MyComponent />);
  expect(screen.getByText("expected text")).toBeInTheDocument();
});
```

### Unit Tests

Plain TypeScript tests for hooks, utilities, and services:

```ts
import { buildLiteratureRows } from "@/features/evidence-search/utils/literatureRows";

it("groups results by source document", () => {
  const rows = buildLiteratureRows([...]);
  expect(rows).toHaveLength(2);
});
```

### Naming Convention

- Test files: `<ModuleName>.test.ts` or `<ModuleName>.test.tsx`
- Test functions: `it("<behavior description>")` or `test("<behavior description>")`
- Directory structure mirrors `src/` (e.g., `tests/features/chat/` tests `src/features/chat/`)

## Configuration

Test runner: Vitest with jsdom environment. Config in `frontend/vitest.config.ts`.

```ts
// vitest.config.ts
{
  plugins: [react()],
  resolve: { alias: { "@": "src" } },
  test: { environment: "jsdom", include: ["tests/**/*.test.tsx"] },
}
```

Note: The include pattern matches `.test.tsx` files. Pure `.test.ts` files are also run by Vitest but may require the `tsconfig.test.json` configuration.
