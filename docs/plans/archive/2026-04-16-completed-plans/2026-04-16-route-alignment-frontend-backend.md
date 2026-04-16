# Route Alignment Frontend Backend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align the repo’s frontend routes, backend-exposed route coverage, and route documentation with the actual product flow while preserving the current request-centric user journey.

**Architecture:** Keep the current canonical frontend flow centered on `/tasks/new` → `/requests/:requestId` → `/documents/:documentId` and add web crawl as a third intake branch under `/tasks/new` instead of reorganizing all routes. Extend the existing Graph Console into a real graph search page backed by the already-implemented `/api/v1/evidence/search` and related evidence endpoints, then update stale docs that still describe removed routes like `/analysis/:id`, `/tasks/status`, and old `/pdf/*` endpoints.

**Tech Stack:** React 19, TypeScript, React Router, Zustand, FastAPI, Pydantic, pytest, Vitest.

---

## Execution notes

1. Execute each task with `@test-driven-development`.
2. If any route behavior is unclear while implementing, inspect the current route definitions before editing more files.
3. Only create commits if the user explicitly asks for them in the execution session.
4. Before claiming success, run the verification commands in the final section with `@verification-before-completion`.

---

### Task 1: Add frontend types and API helpers for the web-crawl branch and graph search

**Files:**
- Modify: `apps/frontend/src/types/api.ts:51-185`
- Modify: `apps/frontend/src/services/api.ts:1-117`
- Test: `apps/frontend/src/services/__tests__/api.test.ts`

**Step 1: Write the failing test**

Replace the placeholder API test with concrete contract checks.

```ts
import { describe, expect, it, vi, beforeEach } from 'vitest';

vi.mock('../http', () => ({
  requestGetJson: vi.fn(),
  requestJson: vi.fn(),
  requestFormData: vi.fn(),
}));

import { requestJson } from '../http';
import { webCrawlSubmit, searchEvidence } from '../api';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('api route helpers', () => {
  it('posts web crawl submissions to the web branch endpoint', async () => {
    vi.mocked(requestJson).mockResolvedValue({ request_id: 'req-1', status: 'queued' });

    await webCrawlSubmit({
      task_form: 'Find PS3 evidence',
      urls: ['https://example.com/paper'],
      source: 'web',
      force_refresh: false,
    });

    expect(requestJson).toHaveBeenCalledWith(
      '/tasks/requests/web/crawl',
      expect.objectContaining({ method: 'POST' }),
      expect.any(Object)
    );
  });

  it('posts graph search filters to the evidence search endpoint', async () => {
    vi.mocked(requestJson).mockResolvedValue({ code: 0, message: 'ok', data: { nodes: [], edges: [] } });

    await searchEvidence({ gene_symbol: 'BRCA1' });

    expect(requestJson).toHaveBeenCalledWith(
      '/evidence/search',
      expect.objectContaining({ method: 'POST', body: { gene_symbol: 'BRCA1' } }),
      expect.any(Object)
    );
  });
});
```

**Step 2: Run the test to verify it fails**

Run:
```bash
npm --prefix apps/frontend run test:run -- src/services/__tests__/api.test.ts
```

Expected: FAIL because `webCrawlSubmit` and `searchEvidence` do not exist yet.

**Step 3: Write the minimal implementation**

Add missing request/response types in `apps/frontend/src/types/api.ts`.

```ts
export type WebLiteratureCrawlRequest = {
  task_form: string;
  urls: string[];
  source?: string;
  force_refresh?: boolean;
};

export type GraphSearchRequest = {
  gene_symbol?: string;
  variant?: string;
  protein_change?: string;
  disease_name?: string;
  min_confidence?: number;
  only_valid?: boolean;
};
```

Add matching API helpers in `apps/frontend/src/services/api.ts`.

```ts
export async function webCrawlSubmit(payload: WebLiteratureCrawlRequest, options: ApiCallOptions = {}) {
  return requestJson<TaskRequestCreateResponse>('/tasks/requests/web/crawl', {
    method: 'POST',
    body: payload,
  }, { signal: options.signal });
}

export async function searchEvidence(payload: GraphSearchRequest, options: ApiCallOptions = {}) {
  return requestJson<EvidenceSearchResponse>('/evidence/search', {
    method: 'POST',
    body: payload,
  }, { signal: options.signal });
}
```

**Step 4: Run the test to verify it passes**

Run:
```bash
npm --prefix apps/frontend run test:run -- src/services/__tests__/api.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/frontend/src/types/api.ts apps/frontend/src/services/api.ts apps/frontend/src/services/__tests__/api.test.ts
git commit -m "feat(frontend): add route-aligned web and graph api helpers"
```

---

### Task 2: Add the web crawl branch to the canonical `/tasks/new` flow

**Files:**
- Modify: `apps/frontend/src/pages/tasks/task-new-page.tsx:23-397`
- Modify: `apps/frontend/src/types/api.ts:51-185`
- Test: `apps/frontend/src/pages/tasks/__tests__/task-new-page.test.tsx`

**Step 1: Write the failing test**

Add a focused branch test.

```ts
it('Web crawl: confirmed request + URLs submits web branch and navigates to /requests/:requestId', async () => {
  vi.mocked(webCrawlSubmit).mockResolvedValueOnce({ request_id: 'req-web', status: 'queued' });

  renderPage();

  fireEvent.change(screen.getByLabelText(/Web URLs/i), {
    target: { value: 'https://example.com/a\nhttps://example.com/b' },
  });
  fireEvent.click(screen.getByRole('button', { name: /Submit web crawl/i }));

  await waitFor(() => {
    expect(webCrawlSubmit).toHaveBeenCalledWith({
      task_form: expect.any(String),
      urls: ['https://example.com/a', 'https://example.com/b'],
      source: 'web',
      force_refresh: false,
    });
  });

  expect(mockNavigate).toHaveBeenCalledWith('/requests/req-web');
});
```

**Step 2: Run the test to verify it fails**

Run:
```bash
npm --prefix apps/frontend run test:run -- src/pages/tasks/__tests__/task-new-page.test.tsx
```

Expected: FAIL because the page has no web-branch UI or submission logic.

**Step 3: Write the minimal implementation**

In `apps/frontend/src/pages/tasks/task-new-page.tsx`:
- import `webCrawlSubmit`
- add local state for `webUrlsText` and `forceRefresh`
- parse newline-separated URLs with a small local helper
- add a third branch card next to upload and PubMed
- require `confirmedRequestId` before enabling submission
- submit to `webCrawlSubmit({ task_form: stringifyTaskForm(draft), urls, source: 'web', force_refresh })`
- navigate to `/requests/${request_id}` on success
- push a toast on invalid/empty URLs or API error

Use direct local logic instead of introducing a new helper module.

**Step 4: Run the test to verify it passes**

Run:
```bash
npm --prefix apps/frontend run test:run -- src/pages/tasks/__tests__/task-new-page.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/frontend/src/pages/tasks/task-new-page.tsx apps/frontend/src/pages/tasks/__tests__/task-new-page.test.tsx apps/frontend/src/types/api.ts
git commit -m "feat(frontend): add web crawl branch to task flow"
```

---

### Task 3: Upgrade `/graph` from stats console to route-aligned graph search page

**Files:**
- Modify: `apps/frontend/src/pages/graph/graph-page.tsx:1-158`
- Modify: `apps/frontend/src/pages/graph/graph-page.css:1-77`
- Test: `apps/frontend/src/pages/graph/graph-page.test.tsx`
- Read: `apps/backend/src/api/routes/evidence.py:147-345`
- Read: `apps/backend/src/domain/graph/search.py:42-73`

**Step 1: Write the failing test**

Create `apps/frontend/src/pages/graph/graph-page.test.tsx`.

```ts
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

vi.mock('../../services/api', () => ({
  getEvidenceGraphStats: vi.fn(),
  resyncEvidenceDocument: vi.fn(),
  searchEvidence: vi.fn(),
}));

import { GraphPage } from './graph-page';
import { searchEvidence } from '../../services/api';

beforeEach(() => vi.clearAllMocks());

it('submits graph search filters and renders node/edge counts', async () => {
  vi.mocked(searchEvidence).mockResolvedValue({
    code: 0,
    message: 'ok',
    data: {
      nodes: [{ id: 'g1', type: 'gene', label: 'BRCA1' }],
      edges: [{ source: 'g1', target: 'd1', relationship: 'RELATED_TO' }],
      total_evidence: 2,
      document_count: 1,
    },
  });

  render(<GraphPage />);

  fireEvent.change(screen.getByLabelText(/Gene symbol/i), { target: { value: 'BRCA1' } });
  fireEvent.click(screen.getByRole('button', { name: /Search graph/i }));

  await waitFor(() => expect(searchEvidence).toHaveBeenCalledWith({ gene_symbol: 'BRCA1' }));
  expect(await screen.findByText(/Nodes: 1/i)).toBeInTheDocument();
  expect(screen.getByText(/Edges: 1/i)).toBeInTheDocument();
  expect(screen.getByText(/Evidence: 2/i)).toBeInTheDocument();
});
```

**Step 2: Run the test to verify it fails**

Run:
```bash
npm --prefix apps/frontend run test:run -- src/pages/graph/graph-page.test.tsx
```

Expected: FAIL because the page currently has no search form or graph result rendering.

**Step 3: Write the minimal implementation**

Update `apps/frontend/src/pages/graph/graph-page.tsx` to:
- keep the existing stats + resync panels
- add search state for `gene_symbol`, `variant`, `protein_change`, `disease_name`
- add a `searchEvidence` call
- derive a summary from `data.nodes`, `data.edges`, `data.total_evidence`, `data.document_count`
- render a simple list-based graph summary and raw JSON preview instead of introducing D3/ForceGraph now

Example result projection:

```ts
const graphData = (searchResult?.data ?? {}) as Record<string, unknown>;
const nodes = Array.isArray(graphData.nodes) ? graphData.nodes : [];
const edges = Array.isArray(graphData.edges) ? graphData.edges : [];
const totalEvidence = typeof graphData.total_evidence === 'number' ? graphData.total_evidence : 0;
const documentCount = typeof graphData.document_count === 'number' ? graphData.document_count : 0;
```

Update CSS only as needed for a small search form and summary cards.

**Step 4: Run the test to verify it passes**

Run:
```bash
npm --prefix apps/frontend run test:run -- src/pages/graph/graph-page.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/frontend/src/pages/graph/graph-page.tsx apps/frontend/src/pages/graph/graph-page.css apps/frontend/src/pages/graph/graph-page.test.tsx
git commit -m "feat(frontend): align graph page to evidence search routes"
```

---

### Task 4: Update frontend route docs to match the implemented flow

**Files:**
- Modify: `docs/reference/frontend/API_IMPLEMENTATION.md:1-220`
- Modify: `docs/reference/frontend/API_STATUS.md:1-80`
- Modify: `docs/APP_FLOW.md:10-129`
- Modify: `docs/reference/frontend/APP_FLOW.md:10-80`

**Step 1: Write the failing documentation assertions**

Create a tiny grep-based checklist in the task notes and use it as the acceptance gate.

Required removals:
- `/analysis/:id`
- `/tasks/status`
- `/api/v1/documents/:id` redirect docs
- `/pdf/fetch-by-pmid`
- `/pdf/fetch-by-doi`

Required additions:
- `/tasks/new`
- `/tasks/pubmed/candidates`
- `/requests/:requestId`
- `/documents/:documentId`
- `/graph`
- `/tasks/requests/web/crawl`
- `GET /api/v1/evidence/search*` / `POST /api/v1/evidence/search`

**Step 2: Run the grep checks to verify docs are stale**

Run:
```bash
grep -R "/analysis/:id\|/tasks/status\|/pdf/fetch-by-pmid\|/pdf/fetch-by-doi" docs/reference/frontend/API_IMPLEMENTATION.md docs/reference/frontend/API_STATUS.md docs/APP_FLOW.md docs/reference/frontend/APP_FLOW.md
```

Expected: matches are found before editing.

**Step 3: Write the minimal doc updates**

Update the docs so they describe the actual canonical flow:
- `/tasks/new` handles clarification + branch selection
- upload, PubMed, and web crawl are three intake branches
- `/requests/:requestId` is the monitoring hub
- `/documents/:documentId` shows parsed document evidence and judgment data
- `/graph` is the graph search/control page backed by evidence APIs
- `API_STATUS.md` should stop claiming removed `/pdf/*` routes are current frontend paths

Keep the language factual and route-focused; do not add speculative architecture.

**Step 4: Run the grep checks to verify docs are updated**

Run:
```bash
grep -R "/analysis/:id\|/tasks/status\|/pdf/fetch-by-pmid\|/pdf/fetch-by-doi" docs/reference/frontend/API_IMPLEMENTATION.md docs/reference/frontend/API_STATUS.md docs/APP_FLOW.md docs/reference/frontend/APP_FLOW.md
```

Expected: no matches.

Then run:
```bash
grep -R "/tasks/new\|/tasks/pubmed/candidates\|/requests/:requestId\|/documents/:documentId\|/graph\|/requests/web/crawl" docs/reference/frontend/API_IMPLEMENTATION.md docs/reference/frontend/API_STATUS.md docs/APP_FLOW.md docs/reference/frontend/APP_FLOW.md
```

Expected: matches found for the new route set.

**Step 5: Commit**

```bash
git add docs/reference/frontend/API_IMPLEMENTATION.md docs/reference/frontend/API_STATUS.md docs/APP_FLOW.md docs/reference/frontend/APP_FLOW.md
git commit -m "docs: align frontend route documentation with implemented flow"
```

---

### Task 5: Update backend route docs to match the actual mounted API surface

**Files:**
- Modify: `apps/backend/src/api/README.md:1-63`
- Optionally modify: `docs/reference/frontend/API_IMPLEMENTATION.md:178-220`
- Read: `apps/backend/main.py:143-161`
- Read: `apps/backend/src/api/routes/task.py:477-1851`
- Read: `apps/backend/src/api/routes/evidence.py:147-526`
- Read: `apps/backend/src/api/routes/stream.py:8-69`

**Step 1: Write the failing documentation assertions**

Define these required corrections:
- prefix must remain `/api/v1`, not `/api`
- task routes must include `/interaction/confirm`, `/requests/upload`, `/requests/web/crawl`, `/requests/{request_id}/source-stats`, `/papers/{paper_task_id}`, `/papers/{paper_task_id}/resume`, `/tasks`
- evidence routes must include `/search`, `/document/{document_id}`, `/graph/stats`, `/sync/document/{document_id}`
- stream routes must mention both request and task websocket endpoints

**Step 2: Run the grep checks to verify the backend README is stale**

Run:
```bash
grep -n "/api\|/interaction/confirm\|/requests/upload\|/requests/web/crawl\|/papers/{paper_task_id}\|/graph/stats\|/stream/requests" apps/backend/src/api/README.md
```

Expected: prefix or routes are missing/inaccurate.

**Step 3: Write the minimal doc updates**

Update `apps/backend/src/api/README.md` so the route inventory matches the mounted routers from `main.py` and the actual handlers in `core.py`, `task.py`, `evidence.py`, and `stream.py`.

Do not try to document every minor route in prose; a concise bullet inventory is enough as long as it is accurate.

**Step 4: Run the grep checks to verify it passes**

Run:
```bash
grep -n "/api/v1\|/interaction/confirm\|/requests/upload\|/requests/web/crawl\|/papers/{paper_task_id}\|/graph/stats\|/stream/requests" apps/backend/src/api/README.md
```

Expected: all required entries appear.

**Step 5: Commit**

```bash
git add apps/backend/src/api/README.md docs/reference/frontend/API_IMPLEMENTATION.md
git commit -m "docs(backend): align route inventory with mounted api surface"
```

---

### Task 6: Verify backend route contracts already cover the preserved architecture and add any missing assertions

**Files:**
- Modify: `apps/backend/tests/integration/test_task_error_contract.py`
- Modify: `apps/backend/tests/integration/test_graph_api.py`
- Read: `apps/backend/tests/integration/test_m2_candidates_handoff.py`
- Read: `apps/backend/tests/integration/test_m2_upload_branch_handoff.py`

**Step 1: Write one missing backend assertion if needed**

Add a focused integration assertion for preserved behavior that the docs now rely on. Recommended gap:

```python
def test_web_crawl_accepts_valid_web_source(client: TestClient, monkeypatch: pytest.MonkeyPatch, task_prefix: str) -> None:
    class DummyAgent:
        def plan_web_request(self, urls: list[str]) -> list[Any]:
            return [SimpleNamespace(normalized_value=urls[0], display_name=urls[0], fingerprint='hash-1')]

    # patch postgres/task queue similarly to existing web crawl tests
    response = client.post(
        f"{task_prefix}/requests/web/crawl",
        json={"task_form": "Find PS3 evidence", "urls": ["https://example.com"], "source": "web"},
    )
    assert response.status_code == 200
```

Only add this if current tests do not already cover the successful route path you need for docs.

**Step 2: Run the targeted backend tests to verify current/red state**

Run:
```bash
uv run --directory apps/backend pytest -q tests/integration/test_task_error_contract.py tests/integration/test_graph_api.py tests/integration/test_m2_candidates_handoff.py tests/integration/test_m2_upload_branch_handoff.py
```

Expected: PASS, or a single targeted failure if you added a new test first.

**Step 3: Write the minimal implementation if a new test was added**

Only if needed, patch the smallest route/test fixture surface required. If all current tests already pass and cover the preserved route architecture, make no production code changes in this task.

**Step 4: Run the targeted backend tests again**

Run the same command.

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/backend/tests/integration/test_task_error_contract.py apps/backend/tests/integration/test_graph_api.py
git commit -m "test(backend): lock route-aligned task and graph contracts"
```

---

### Task 7: Run end-to-end verification for the aligned route surface

**Files:**
- Verify only

**Step 1: Run frontend tests for affected routes**

Run:
```bash
npm --prefix apps/frontend run test:run -- src/services/__tests__/api.test.ts src/pages/tasks/__tests__/task-new-page.test.tsx src/pages/tasks/__tests__/pubmed-candidates-page.test.tsx src/pages/graph/graph-page.test.tsx src/pages/documents/document-page.test.tsx src/pages/requests/request-monitor-page.test.tsx src/services/__tests__/websocket.test.ts
```

Expected: PASS.

**Step 2: Run frontend type-check/build**

Run:
```bash
npx --prefix apps/frontend tsc --noEmit
npm --prefix apps/frontend run build
```

Expected: PASS.

**Step 3: Run backend route/integration tests**

Run:
```bash
uv run --directory apps/backend pytest -q tests/integration/test_task_error_contract.py tests/integration/test_graph_api.py tests/integration/test_m2_candidates_handoff.py tests/integration/test_m2_upload_branch_handoff.py tests/integration/test_task_api.py
```

Expected: PASS.

**Step 4: Run a docs drift grep sweep**

Run:
```bash
grep -R "/analysis/:id\|/tasks/status\|/pdf/fetch-by-pmid\|/pdf/fetch-by-doi" docs apps/backend/src/api/README.md
```

Expected: no current-doc matches outside archive directories.

**Step 5: Commit**

```bash
git add apps/frontend apps/backend docs
git commit -m "chore: verify aligned frontend backend routes"
```

---

## Final verification checklist

Run all of the following before declaring completion:

```bash
npm --prefix apps/frontend run test:run -- src/services/__tests__/api.test.ts src/pages/tasks/__tests__/task-new-page.test.tsx src/pages/tasks/__tests__/pubmed-candidates-page.test.tsx src/pages/graph/graph-page.test.tsx src/pages/documents/document-page.test.tsx src/pages/requests/request-monitor-page.test.tsx src/services/__tests__/websocket.test.ts
npx --prefix apps/frontend tsc --noEmit
npm --prefix apps/frontend run build
uv run --directory apps/backend pytest -q tests/integration/test_task_error_contract.py tests/integration/test_graph_api.py tests/integration/test_m2_candidates_handoff.py tests/integration/test_m2_upload_branch_handoff.py tests/integration/test_task_api.py
grep -R "/analysis/:id\|/tasks/status\|/pdf/fetch-by-pmid\|/pdf/fetch-by-doi" docs apps/backend/src/api/README.md
```

Expected final state:
- current frontend routes stay request-centric
- `/tasks/new` exposes upload + PubMed + web crawl branches
- `/graph` uses actual evidence search routes instead of only stats/resync console behavior
- stale route docs are removed or rewritten
- backend route inventory docs match the mounted `/api/v1` surface
