# Multilingual Literature Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full-stack multilingual literature flow that can search and select online case reports, run evidence extraction, and visualize the resulting knowledge graph for Chinese, Japanese, Korean, Russian, German, and English acceptance sets.

**Architecture:** Reuse the repo’s existing split between task-request APIs, literature gateways, Celery paper-task workers, and Neo4j-backed graph APIs. Keep the existing PubMed and web crawl workers where they already work, add one generic identifier/DOI lane for Crossref/J-Stage/DOAJ/Unpaywall candidates, and fix the agent-workflow acquisition path so downloaded files or acquisition markdown actually reach parsing/translation/extraction instead of stopping at search-only metadata.

**Tech Stack:** FastAPI, Pydantic v2, Celery, LangGraph, MinIO, PostgreSQL, Neo4j, React 19, Vite, Zustand, D3, pytest, Vitest.

---

## Constraints discovered in the current repo

1. `apps/backend/src/domain/literature/unified/workflow.py` can already route a **single** API or web provider, but it does not aggregate multilingual candidate results across providers.
2. `apps/backend/src/api/routes/task.py` still exposes PubMed-specific candidate/submit endpoints, while the confirmation response already advertises `pubmed`, `web`, and `upload` branches.
3. `apps/backend/src/services/task_manager.py` already has working execution lanes for:
   - uploaded PDFs/DOCX via `process_pdf_task`
   - PubMed via `process_pubmed_paper_task`
   - direct web URLs via `process_web_page_task`
   But there is **no generic DOI/identifier worker** for Crossref/J-Stage/DOAJ/Unpaywall candidate items.
4. The supervisor path is incomplete for online literature: `apps/backend/src/agents/acquisition/node.py` currently calls the unified workflow with `action="search"`, while `apps/backend/src/agents/parsing/node.py` only proceeds when `file_paths` exist. That means the agent workflow can stop after acquisition for pubmed/web sources.
5. The frontend still hard-codes a PubMed-only selection flow in `apps/frontend/src/pages/tasks/task-new-page.tsx` and `apps/frontend/src/pages/tasks/pubmed-candidates-page.tsx`.
6. The backend already has graph search APIs in `apps/backend/src/api/routes/evidence.py`, but `apps/frontend/src/pages/graph/graph-page.tsx` is still only a stats/resync console, not a graph explorer.

Use those facts to keep the implementation incremental instead of rewriting the pipeline.

### Task 1: Freeze the multilingual acceptance corpus

**Files:**
- Create: `apps/backend/tests/fixtures/multilingual_case_report_manifest.json`
- Create: `apps/backend/tests/integration/test_multilingual_case_report_manifest.py`

**Step 1: Write the failing test**

```python
import json
from collections import Counter
from pathlib import Path


def test_manifest_has_required_language_and_provider_coverage() -> None:
    manifest = json.loads(
        Path("apps/backend/tests/fixtures/multilingual_case_report_manifest.json").read_text()
    )

    language_counts = Counter(item["language"] for item in manifest)
    assert language_counts == {
        "zh": 2,
        "ja": 2,
        "ko": 2,
        "ru": 2,
        "de": 2,
        "en": 5,
    }

    providers = {item["provider"] for item in manifest}
    assert {
        "crossref",
        "pmc",
        "unpaywall",
        "doaj",
        "jstage",
        "pubscholar",
        "hans_publishers",
        "cyberleninka",
    } <= providers
```

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/integration/test_multilingual_case_report_manifest.py -q`
Expected: FAIL with `FileNotFoundError` or manifest-count assertion errors.

**Step 3: Write minimal implementation**

```json
[
  {
    "language": "zh",
    "country": "CN",
    "provider": "pubscholar",
    "route": "web",
    "query": "GLA c.92C>A Fabry disease case report",
    "title": "GLA基因c.92C>A突变法布雷病家系1例",
    "identifiers": {
      "url": "TO_FILL"
    },
    "expected_gene": "GLA",
    "expected_variant": "c.92C>A",
    "expected_disease": "Fabry disease"
  }
]
```

Fill the remaining 14 records so the manifest contains:
- zh: 2 entries using `pubscholar` / `hans_publishers`
- ja: 2 entries using `jstage`
- ru: 2 entries using `cyberleninka`
- ko: 2 entries using existing API providers only (`crossref`, `unpaywall`, `doaj`, `pmc`)
- de: 2 entries using existing API providers only (`crossref`, `unpaywall`, `doaj`, `pmc`)
- en: 5 entries spread across `pmc`, `crossref`, `unpaywall`, `doaj`

Do **not** invent new providers in this slice.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/integration/test_multilingual_case_report_manifest.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/tests/fixtures/multilingual_case_report_manifest.json apps/backend/tests/integration/test_multilingual_case_report_manifest.py
git commit -m "test: freeze multilingual case report acceptance set"
```

### Task 2: Add a generic multilingual candidate search service

**Files:**
- Create: `apps/backend/src/domain/literature/unified/search_service.py`
- Create: `apps/backend/tests/test_literature_search_service.py`
- Modify: `apps/backend/src/services/dtos.py`
- Modify: `apps/backend/src/api/routes/task.py`

**Step 1: Write the failing test**

```python
from src.domain.literature.unified.search_service import build_provider_plan


def test_build_provider_plan_for_japanese_prefers_jstage() -> None:
    plan = build_provider_plan(language="ja")
    assert plan[0] == {"route": "api", "provider": "jstage"}
    assert {item["provider"] for item in plan} >= {"jstage", "crossref", "unpaywall"}
```

Add one more test that dedupes candidates by DOI / URL / normalized title.

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_literature_search_service.py -q`
Expected: FAIL with `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

```python
LANG_PROVIDER_MATRIX = {
    "zh": [
        {"route": "web", "provider": "pubscholar"},
        {"route": "web", "provider": "hans_publishers"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
    "ja": [
        {"route": "api", "provider": "jstage"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
    "ru": [
        {"route": "web", "provider": "cyberleninka"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
    ],
}
```

Then add Pydantic models in `apps/backend/src/services/dtos.py`:

```python
class LiteratureCandidateItem(BaseModel):
    candidate_id: str
    provider: str
    route: str
    title: str
    journal: Optional[str] = None
    year: Optional[str] = None
    language: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    identifiers: Dict[str, Any] = Field(default_factory=dict)
    detail_link: Optional[str] = None
```

Expose a new route in `apps/backend/src/api/routes/task.py`:
- `POST /tasks/requests/literature/candidates`
- input: request/task-form + target/disease/country/language + optional provider hints
- output: normalized `LiteratureCandidateItem[]`

Build the query as `"{target} {disease} case report"` and fan out through the provider plan using the existing unified workflow one provider at a time.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_literature_search_service.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/domain/literature/unified/search_service.py apps/backend/src/services/dtos.py apps/backend/src/api/routes/task.py apps/backend/tests/test_literature_search_service.py
git commit -m "feat: add multilingual literature candidate search service"
```

### Task 3: Add the request API contract for candidate search and selection

**Files:**
- Modify: `apps/backend/src/services/dtos.py`
- Modify: `apps/backend/src/api/routes/task.py`
- Create: `apps/backend/tests/integration/test_multilingual_literature_api.py`

**Step 1: Write the failing test**

```python
def test_literature_candidates_endpoint_returns_generic_candidates(client, monkeypatch):
    monkeypatch.setattr(
        task_api,
        "search_multilingual_candidates",
        lambda **_: [
            {
                "candidate_id": "cand-1",
                "provider": "jstage",
                "route": "api",
                "title": "Fabry disease case report",
                "language": "ja",
                "identifiers": {"doi": "10.1234/example"},
            }
        ],
    )

    response = client.post(
        f"{cfg.api_prefix}/tasks/requests/literature/candidates",
        json={
            "request_id": "req-123",
            "target": "GLA c.92C>A",
            "disease": "Fabry disease",
            "language": "ja",
            "source": "literature",
        },
    )

    assert response.status_code == 200
    assert response.json()["candidates"][0]["provider"] == "jstage"
```

Add a second failing test for `POST /tasks/requests/literature/submit` with empty selection returning `INPUT_INVALID`.

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/integration/test_multilingual_literature_api.py -q`
Expected: FAIL with 404 or validation errors.

**Step 3: Write minimal implementation**

```python
class LiteratureCandidateSearchRequest(BaseModel):
    request_id: Optional[str] = None
    task_form: Optional[str] = None
    target: str
    disease: str
    country: str = "不限"
    language: str = "auto"
    source: str = "literature"
    candidate_limit: int = Field(15, ge=1, le=20)


class LiteratureSelectionSubmitRequest(BaseModel):
    request_id: Optional[str] = None
    task_form: str
    source: str = "literature"
    selected_candidates: List[Dict[str, Any]] = Field(..., min_length=1, max_length=10)
```

Route behavior:
- `POST /requests/literature/candidates` uses `search_multilingual_candidates(...)`
- `POST /requests/literature/submit` validates 1–10 selected candidates and echoes the standard `TaskRequestCreateResponse`
- Keep `pubmed` and `web` legacy routes untouched until the frontend migration is green

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/integration/test_multilingual_literature_api.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/services/dtos.py apps/backend/src/api/routes/task.py apps/backend/tests/integration/test_multilingual_literature_api.py
git commit -m "feat: add multilingual literature task API contract"
```

### Task 4: Dispatch selected candidates into the right worker lane

**Files:**
- Modify: `apps/backend/src/api/routes/task.py`
- Modify: `apps/backend/src/services/task_manager.py`
- Modify: `apps/backend/src/services/__init__.py`
- Modify: `apps/backend/tests/unit/test_tasks.py`
- Modify: `apps/backend/tests/integration/test_multilingual_literature_api.py`

**Step 1: Write the failing test**

```python
def test_submit_literature_dispatches_identifier_candidates_to_new_worker(monkeypatch):
    queued = {}

    class DummyAsyncResult:
        id = "celery-123"

    class DummyTask:
        def apply_async(self, args):
            queued["args"] = args
            return DummyAsyncResult()

    monkeypatch.setattr(task_api, "process_literature_identifier_task", DummyTask())
    monkeypatch.setattr(task_api, "_celery_task", lambda task: task)

    # post a candidate with DOI but no PMID / URL and assert the new worker is used
```

Add sibling tests for:
- web candidate -> `process_web_page_task`
- PMID candidate -> `process_pubmed_paper_task`

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/integration/test_multilingual_literature_api.py -q -k dispatch`
Expected: FAIL because the generic submit route still does not branch by candidate type.

**Step 3: Write minimal implementation**

```python
if candidate["route"] == "web" and candidate.get("url"):
    async_result = _celery_task(process_web_page_task).apply_async(...)
elif candidate.get("identifiers", {}).get("pmid"):
    async_result = _celery_task(process_pubmed_paper_task).apply_async(...)
else:
    async_result = _celery_task(process_literature_identifier_task).apply_async(
        args=[candidate, document_id, paper_task_id, request_id]
    )
```

Also add a new Celery task in `apps/backend/src/services/task_manager.py`:

```python
@celery_app.task(name="tasks.process_literature_identifier", bind=True, ...)
def process_literature_identifier_task(self, candidate, document_id, paper_task_id, request_id):
    ...
```

That task is only for API candidates that do not already map cleanly to the existing PubMed or web lanes.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/integration/test_multilingual_literature_api.py apps/backend/tests/unit/test_tasks.py -q -k "dispatch or literature_identifier"`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/api/routes/task.py apps/backend/src/services/task_manager.py apps/backend/src/services/__init__.py apps/backend/tests/unit/test_tasks.py apps/backend/tests/integration/test_multilingual_literature_api.py
git commit -m "feat: dispatch multilingual candidates by worker lane"
```

### Task 5: Implement the identifier/DOI worker by reusing the PDF pipeline

**Files:**
- Modify: `apps/backend/src/services/task_manager.py`
- Modify: `apps/backend/tests/unit/test_tasks.py`

**Step 1: Write the failing test**

```python
def test_process_literature_identifier_task_downloads_pdf_and_reuses_pdf_pipeline(monkeypatch):
    candidate = {
        "provider": "jstage",
        "route": "api",
        "title": "Fabry case report",
        "identifiers": {"doi": "10.1234/example"},
        "detail_link": "https://www.jstage.jst.go.jp/article/example",
    }

    async def fake_download(**kwargs):
        return {
            "downloaded": True,
            "local_file_path": "/tmp/literature-downloads/doc-1/paper.pdf",
            "sha256": "abc",
        }

    called = {}

    def fake_process_pdf(file_paths, **kwargs):
        called["file_paths"] = file_paths
        return {"status": "success"}
```

Assert the worker passes the downloaded PDF into the existing upload/PDF pipeline instead of duplicating parsing/extraction logic.

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_tasks.py -q -k literature_identifier`
Expected: FAIL because the new worker does not yet preserve the downloaded file path.

**Step 3: Write minimal implementation**

First, extend the shared downloader:

```python
async def _try_download_and_store_literature_pdf(..., preserve_local_file: bool = False) -> Dict[str, Any]:
    ...
    return {
        "downloaded": True,
        "local_file_path": str(file_path) if preserve_local_file else None,
        "sha256": file_hash,
        ...
    }
```

Then keep the new worker thin:

```python
def process_literature_identifier_task(...):
    download = asyncio.run(
        _try_download_and_store_literature_pdf(
            document_id=document_id,
            source="pubmed" if candidate.get("identifiers", {}).get("pmid") else "web",
            query=candidate.get("title") or candidate.get("identifiers", {}).get("doi") or "",
            identifiers=list((candidate.get("identifiers") or {}).values()),
            detail_link=candidate.get("detail_link"),
            selected_title=candidate.get("title"),
            preserve_local_file=True,
        )
    )
    if not download.get("downloaded"):
        return {"status": "failed", "error_code": "FULLTEXT_UNAVAILABLE"}
    return process_pdf_task.run(
        file_paths=[download["local_file_path"]],
        file_hash=download.get("sha256"),
        document_id=document_id,
        paper_task_id=paper_task_id,
        request_id=request_id,
    )
```

Reuse the existing PDF/upload lane; do not copy parsing/translation/extraction code into a second worker.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_tasks.py -q -k literature_identifier`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/services/task_manager.py apps/backend/tests/unit/test_tasks.py
git commit -m "feat: process DOI literature via shared pdf pipeline"
```

### Task 6: Fix supervisor acquisition → parsing parity for online literature

**Files:**
- Modify: `apps/backend/src/state/global_state.py`
- Modify: `apps/backend/src/agents/acquisition/node.py`
- Modify: `apps/backend/src/agents/parsing/node.py`
- Modify: `apps/backend/src/agents/supervisor.py`
- Modify: `apps/backend/tests/test_agents_acquisition.py`
- Modify: `apps/backend/tests/test_supervisor_integration.py`

**Step 1: Write the failing test**

```python
def test_run_acquisition_node_pubmed_download_sets_file_paths(monkeypatch) -> None:
    async def fake_workflow(payload):
        assert payload["action"] == "download"
        return {
            "success": True,
            "downloads": [{"file_path": "/tmp/paper.pdf"}],
            "warnings": [],
            "route": {"used": "api", "api_provider": "pmc"},
            "raw": {"api": {"source_trace": []}},
        }

    monkeypatch.setattr(acquisition_node, "literature_unified_workflow", fake_workflow, raising=False)
    result = acquisition_node.run_acquisition_node(...)
    assert result["file_paths"] == ["/tmp/paper.pdf"]
```

Add a second failing supervisor test for `markdown_content` fallback: parsing should synthesize `parsing_result` when acquisition already supplied markdown, so the workflow continues to translation instead of going to `finalize_failed`.

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_agents_acquisition.py apps/backend/tests/test_supervisor_integration.py -q`
Expected: FAIL because acquisition still uses `action="search"` and parsing still requires `file_paths` only.

**Step 3: Write minimal implementation**

Change acquisition to download artifacts, not just search metadata:

```python
def _build_workflow_payload(source: str, plan_items: list[AcquisitionPlanItem]) -> dict[str, Any]:
    primary = plan_items[0].normalized_value if plan_items else ""
    if source == "web":
        return {
            "action": "download",
            "query": primary,
            "identifiers": [primary],
            "prefer": "web",
            "detail_link": primary,
            "selected_title": primary,
            "raw": True,
        }
    return {
        "action": "download",
        "query": f"PMID:{primary}",
        "identifiers": [primary],
        "prefer": "api",
        "api_provider": "pmc",
        "raw": True,
    }
```

Adopt downloaded files into supervisor state:

```python
download_paths = [
    str(item.get("file_path"))
    for item in acquisition_result.get("downloads", [])
    if str(item.get("file_path") or "").strip()
]
if download_paths:
    updated["file_paths"] = download_paths
```

And in `apps/backend/src/agents/parsing/node.py`, allow prebuilt markdown to keep the graph moving:

```python
if not file_paths and updated.get("markdown_content"):
    updated["current_node"] = "parsing"
    updated["parsing_result"] = {
        "parser_backend": "acquisition_fallback",
        "markdown_content": updated["markdown_content"],
        "image_paths": [],
    }
    return cast(SupervisorState, cast(object, updated))
```

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/test_agents_acquisition.py apps/backend/tests/test_supervisor_integration.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/state/global_state.py apps/backend/src/agents/acquisition/node.py apps/backend/src/agents/parsing/node.py apps/backend/src/agents/supervisor.py apps/backend/tests/test_agents_acquisition.py apps/backend/tests/test_supervisor_integration.py
git commit -m "fix: carry online acquisition artifacts into supervisor parsing"
```

### Task 7: Replace PubMed-only frontend state with generic literature candidates

**Files:**
- Modify: `apps/frontend/src/types/api.ts`
- Modify: `apps/frontend/src/services/api.ts`
- Modify: `apps/frontend/src/store/appStore.ts`
- Modify: `apps/frontend/src/store/__tests__/useAppStore.test.ts`

**Step 1: Write the failing test**

```ts
it('stores generic literature candidates and selected candidate ids', async () => {
  await useAppStore.getState().fetchCandidates({
    request_id: 'req-123',
    target: 'GLA c.92C>A',
    disease: 'Fabry disease',
    language: 'ja',
    source: 'literature'
  })

  expect(useAppStore.getState().candidates[0]).toEqual(
    expect.objectContaining({ provider: 'jstage', route: 'api' })
  )
})
```

Rename the selected state from `selectedPmids` to `selectedCandidateIds` in the test first.

**Step 2: Run test to verify it fails**

Run: `npm --prefix apps/frontend run test:run -- src/store/__tests__/useAppStore.test.ts`
Expected: FAIL because the store and types are still PubMed-specific.

**Step 3: Write minimal implementation**

```ts
export type LiteratureCandidateItem = {
  candidate_id: string;
  provider: string;
  route: 'api' | 'web';
  title: string;
  language?: string;
  doi?: string;
  url?: string;
  identifiers?: Record<string, unknown>;
  detail_link?: string;
};
```

Then update the store shape:

```ts
ui: {
  ...state.ui,
  selectedCandidateIds: exists
    ? state.ui.selectedCandidateIds.filter((item) => item !== candidateId)
    : [...state.ui.selectedCandidateIds, candidateId],
}
```

And switch the API client to the new routes:

```ts
return requestJson<LiteratureCandidateSearchResponse>('/tasks/requests/literature/candidates', ...)
return requestJson<TaskRequestCreateResponse>('/tasks/requests/literature/submit', ...)
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix apps/frontend run test:run -- src/store/__tests__/useAppStore.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/frontend/src/types/api.ts apps/frontend/src/services/api.ts apps/frontend/src/store/appStore.ts apps/frontend/src/store/__tests__/useAppStore.test.ts
git commit -m "refactor: make candidate state source-agnostic"
```

### Task 8: Replace the PubMed-only branch page with a multilingual literature page

**Files:**
- Create: `apps/frontend/src/pages/tasks/literature-candidates-page.tsx`
- Create: `apps/frontend/src/pages/tasks/__tests__/literature-candidates-page.test.tsx`
- Modify: `apps/frontend/src/pages/tasks/task-new-page.tsx`
- Modify: `apps/frontend/src/pages/tasks/__tests__/task-new-page.test.tsx`
- Modify: `apps/frontend/src/router/index.tsx`
- Delete: `apps/frontend/src/pages/tasks/pubmed-candidates-page.tsx`
- Delete: `apps/frontend/src/pages/tasks/__tests__/pubmed-candidates-page.test.tsx`

**Step 1: Write the failing test**

```ts
it('navigates to the multilingual literature page after confirmation', () => {
  renderPage();
  fireEvent.click(screen.getByRole('button', { name: /Go to candidates/i }));
  expect(mockNavigate).toHaveBeenCalledWith('/tasks/literature/candidates');
});
```

Add a page test that renders provider / route / language badges and submits selected generic candidates.

**Step 2: Run test to verify it fails**

Run: `npm --prefix apps/frontend run test:run -- src/pages/tasks/__tests__/task-new-page.test.tsx src/pages/tasks/__tests__/literature-candidates-page.test.tsx`
Expected: FAIL because the route and page are still PubMed-only.

**Step 3: Write minimal implementation**

Before editing the React page, use `@vercel-react-best-practices`.

```tsx
<div style={{ fontWeight: 800 }}>Online literature candidates</div>
<div className="muted">Crossref / PMC / Unpaywall / DOAJ / J-Stage / web gateways</div>
{candidates.map((candidate) => {
  const checked = ui.selectedCandidateIds.includes(candidate.candidate_id);
  return (
    <label key={candidate.candidate_id}>
      <input type="checkbox" checked={checked} onChange={() => toggleCandidateSelection(candidate.candidate_id)} />
      <div>{candidate.title}</div>
      <div className="muted">
        {candidate.provider} · {candidate.route} · {candidate.language ?? 'unknown'}
      </div>
    </label>
  );
})}
```

Update the task-new-page branch CTA to navigate to `/tasks/literature/candidates` and rename the panel text from `PubMed candidates` to `Online literature candidates`.

**Step 4: Run test to verify it passes**

Run: `npm --prefix apps/frontend run test:run -- src/pages/tasks/__tests__/task-new-page.test.tsx src/pages/tasks/__tests__/literature-candidates-page.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/frontend/src/pages/tasks/literature-candidates-page.tsx apps/frontend/src/pages/tasks/__tests__/literature-candidates-page.test.tsx apps/frontend/src/pages/tasks/task-new-page.tsx apps/frontend/src/pages/tasks/__tests__/task-new-page.test.tsx apps/frontend/src/router/index.tsx
git rm apps/frontend/src/pages/tasks/pubmed-candidates-page.tsx apps/frontend/src/pages/tasks/__tests__/pubmed-candidates-page.test.tsx
git commit -m "feat: replace pubmed-only candidate page with multilingual literature flow"
```

### Task 9: Turn the graph console into a searchable knowledge graph explorer

**Files:**
- Modify: `apps/frontend/src/types/api.ts`
- Modify: `apps/frontend/src/services/api.ts`
- Modify: `apps/frontend/src/pages/graph/graph-page.tsx`
- Modify: `apps/frontend/src/pages/graph/graph-page.css`
- Create: `apps/frontend/src/pages/graph/__tests__/graph-page.test.tsx`

**Step 1: Write the failing test**

```ts
it('renders graph search results and opens a document link from a node', async () => {
  vi.mocked(api.searchEvidenceGraph).mockResolvedValue({
    code: 0,
    message: 'ok',
    data: {
      nodes: [{ id: 'doc:1', type: 'document', label: 'Fabry case report' }],
      edges: [],
      evidence_records: [],
      document_count: 1,
      total_evidence: 1,
    },
  });

  render(<GraphPage />);
  fireEvent.change(screen.getByLabelText(/Variant/i), { target: { value: 'GLA:c.92C>A' } });
  fireEvent.click(screen.getByRole('button', { name: /Search graph/i }));

  expect(await screen.findByText(/Fabry case report/i)).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix apps/frontend run test:run -- src/pages/graph/__tests__/graph-page.test.tsx`
Expected: FAIL because the page still only supports stats/resync.

**Step 3: Write minimal implementation**

Before editing the graph UI, use `@vercel-react-best-practices`.

Add a typed API helper:

```ts
export async function searchEvidenceGraph(payload: EvidenceSearchRequest, options: ApiCallOptions = {}) {
  return requestJson<EvidenceSearchResponse>('/evidence/search', {
    method: 'POST',
    body: payload,
  }, { signal: options.signal });
}
```

Then render nodes/edges with D3:

```tsx
const simulation = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(edges).id((d: any) => d.id).distance(120))
  .force('charge', d3.forceManyBody().strength(-260))
  .force('center', d3.forceCenter(width / 2, height / 2));
```

Keep the existing stats/resync controls, but add a first-class search panel for gene / variant / protein / disease filters and a side panel that lists evidence records and links document nodes to `/documents/:documentId`.

After the page works, run `@web-design-guidelines` on the final UI.

**Step 4: Run test to verify it passes**

Run: `npm --prefix apps/frontend run test:run -- src/pages/graph/__tests__/graph-page.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/frontend/src/types/api.ts apps/frontend/src/services/api.ts apps/frontend/src/pages/graph/graph-page.tsx apps/frontend/src/pages/graph/graph-page.css apps/frontend/src/pages/graph/__tests__/graph-page.test.tsx
git commit -m "feat: add searchable knowledge graph explorer"
```

## Final verification checklist

### Backend

Run:

```bash
uv run --project apps/backend pytest \
  apps/backend/tests/integration/test_multilingual_case_report_manifest.py \
  apps/backend/tests/test_literature_search_service.py \
  apps/backend/tests/integration/test_multilingual_literature_api.py \
  apps/backend/tests/test_agents_acquisition.py \
  apps/backend/tests/test_supervisor_integration.py \
  apps/backend/tests/unit/test_tasks.py -q
```

Expected: all targeted multilingual search / submit / worker / supervisor tests PASS.

### Frontend

Run:

```bash
npm --prefix apps/frontend run test:run -- \
  src/store/__tests__/useAppStore.test.ts \
  src/pages/tasks/__tests__/task-new-page.test.tsx \
  src/pages/tasks/__tests__/literature-candidates-page.test.tsx \
  src/pages/graph/__tests__/graph-page.test.tsx
```

Expected: PASS

### Manual full-stack smoke test

**Backend**

```bash
uv run --project apps/backend uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Expected: FastAPI boots and mounts task + evidence routers.

**Frontend**

```bash
npm --prefix apps/frontend run dev -- --host 0.0.0.0 --port 5173
```

Expected: Vite dev server starts.

**Browser flow**

1. Open `/tasks/new`.
2. Confirm a task form like `GLA c.92C>A / Fabry disease / Japan / ja`.
3. Open `/tasks/literature/candidates`.
4. Verify mixed-provider results show provider/language badges.
5. Select one J-Stage case report and one Chinese or Russian web case report.
6. Submit and wait for `/requests/:requestId` to show queued → running → success/partial_failed.
7. Open `/graph`, search by the target gene or variant, and confirm document nodes + evidence side panel render.
8. Open a document node and confirm `/documents/:documentId` loads without client errors.

### Done means

- Candidate search is no longer PubMed-only.
- The curated manifest contains 15 target case reports with the requested language spread.
- Selected candidates can be submitted through one API contract and dispatched to the correct worker lane.
- DOI/J-Stage/DOAJ/Unpaywall candidates have a real execution path.
- Agent-workflow online acquisition no longer dead-ends before parsing.
- `/graph` is a real graph explorer instead of only a stats console.
