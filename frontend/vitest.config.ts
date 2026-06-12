import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: [
      "tests/evidence-search/BilingualComparison.test.tsx",
      "tests/evidence-search/EvidenceHighlightText.test.tsx",
      "tests/features/chat/ChatMarkdown.test.tsx",
    ],
  },
});
