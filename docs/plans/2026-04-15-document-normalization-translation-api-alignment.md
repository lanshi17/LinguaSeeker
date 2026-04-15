# Document Normalization, Translation Reliability, and API Contract Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure literature/web/PDF content always becomes a body-only standardized document, prevent silent non-English or untranslated outputs from entering extraction, and align the document/evidence API contract with the code the frontend actually uses.

**Architecture:** Normalize document body content at the boundary where web/PDF text enters the pipeline, then validate translation before extraction so downstream steps only see trusted English markdown. Expose a stable document-evidence response that reads processed artifacts plus graph evidence, and update frontend types/pages to consume that contract instead of generic `unknown` payloads and raw fallbacks.

**Tech Stack:** Python/FastAPI backend, Pydantic, MinIO, crawl4ai, BeautifulSoup, `lingua-language-detector`, pytest, TypeScript/React, vitest.

---

## Execution notes

1. Execute every task with `@test-driven-development`.
2. If a targeted test fails for an unexpected reason, stop and use `@systematic-debugging` before changing more code.
3. Before claiming completion, run the backend/frontend verification commands in the final section with `@verification-before-completion`.
4. This repository often runs under “do not commit unless explicitly requested”; each task includes a commit step for completeness, but only run it if the user explicitly asks for a commit in the execution session.

---

### Task 1: Add a shared body-only normalizer for HTML/markdown inputs

**Files:**
- Create: `apps/backend/src/domain/document_normalization.py`
- Create: `apps/backend/tests/unit/test_document_normalization.py`
- Read: `apps/backend/src/domain/literature/firecrawl_service.py:30-75`
- Read: `apps/backend/src/domain/agent/document_parsing.py:25-36`

**Step 1: Write the failing tests**

```python
from src.domain.document_normalization import normalize_document_body


def test_normalize_document_body_strips_html_scaffold_and_keeps_article_text() -> None:
    html = """
    <html>
      <body>
        <header>site nav</header>
        <main>
          <article>
            <h1>Example Title</h1>
            <p>这是正文第一段。</p>
            <p>Body paragraph two.</p>
          </article>
        </main>
        <footer>copyright</footer>
      </body>
    </html>
    """

    normalized = normalize_document_body(html)

    assert normalized.text == "# Example Title\n\n这是正文第一段。\n\nBody paragraph two."
    assert "site nav" not in normalized.text
    assert "copyright" not in normalized.text
    assert normalized.source_type == "html"
    assert normalized.body_selector in {"article", "main", "body"}


def test_normalize_document_body_removes_embedded_html_blocks_from_markdown() -> None:
    markdown = "# Title\n\n正文保留。\n\n<div>debug html</div>\n\n## Results\n\nEnglish body."

    normalized = normalize_document_body(markdown)

    assert normalized.text == "# Title\n\n正文保留。\n\n## Results\n\nEnglish body."
    assert "<div>" not in normalized.text
    assert normalized.source_type == "markdown"
```

**Step 2: Run the tests to verify they fail**

Run:
```bash
uv run --directory apps/backend pytest -q tests/unit/test_document_normalization.py
```

Expected: FAIL because `src/domain/document_normalization.py` does not exist yet.

**Step 3: Write the minimal implementation**

Create `apps/backend/src/domain/document_normalization.py` with a small shared normalizer that both web acquisition and parser collection can call.

```python
from __future__ import annotations

from dataclasses import dataclass
import re
from bs4 import BeautifulSoup


_REMOVED_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "form"}
_BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre"}


@dataclass(frozen=True)
class NormalizedDocument:
    text: str
    source_type: str
    body_selector: str | None = None


def normalize_document_body(content: str) -> NormalizedDocument:
    raw = str(content or "").strip()
    if not raw:
        return NormalizedDocument(text="", source_type="markdown", body_selector=None)
    if _looks_like_html(raw):
        return _normalize_html(raw)
    return _normalize_markdown(raw)


def _looks_like_html(text: str) -> bool:
    sample = text[:2000].lower()
    return bool(re.search(r"<\s*(html|body|article|main|div|p|section)\b", sample))


def _normalize_html(html: str) -> NormalizedDocument:
    soup = BeautifulSoup(html, "html.parser")
    for tag in list(soup.find_all(_REMOVED_TAGS)):
        tag.decompose()

    body = soup.select_one("article") or soup.select_one("main") or soup.body or soup
    selector = "article" if body and body.name == "article" else "main" if body and body.name == "main" else "body"

    blocks: list[str] = []
    for node in body.find_all(_BLOCK_TAGS):
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        if node.name and node.name.startswith("h"):
            level = int(node.name[1]) if node.name[1:].isdigit() else 1
            blocks.append(f"{'#' * max(1, min(level, 6))} {text}")
        elif node.name == "li":
            blocks.append(f"- {text}")
        else:
            blocks.append(text)

    normalized = "\n\n".join(blocks).strip()
    return NormalizedDocument(text=normalized, source_type="html", body_selector=selector)


def _normalize_markdown(markdown: str) -> NormalizedDocument:
    cleaned = re.sub(r"<[^>]+>", "", markdown)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return NormalizedDocument(text=cleaned, source_type="markdown", body_selector=None)
```

Keep the module intentionally small. Do not add a larger document-abstraction layer yet.

**Step 4: Run the tests to verify they pass**

Run:
```bash
uv run --directory apps/backend pytest -q tests/unit/test_document_normalization.py
```

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 2: Normalize web-acquired and parser-collected documents before storage/translation

**Files:**
- Modify: `apps/backend/src/domain/literature/firecrawl_service.py:30-75`
- Modify: `apps/backend/src/domain/agent/document_parsing.py:25-36,97-117`
- Modify: `apps/backend/src/services/task_manager.py:876-903,3178-3369`
- Modify: `apps/backend/tests/unit/test_firecrawl_service.py`
- Modify: `apps/backend/tests/unit/test_document_parsing_agent.py`
- Modify: `apps/backend/tests/unit/test_tasks.py`

**Step 1: Write the failing tests**

Add one web-acquisition test, one parser-collection test, and one pipeline wiring test.

```python
def test_firecrawl_service_fallback_normalizes_cleaned_html(monkeypatch) -> None:
    ...
    assert result.markdown == "# Example title\n\n正文内容。\n\nEnglish body."
    assert "<article>" not in result.markdown
    assert result.metadata["normalized_body"] is True
```

```python
def test_document_parsing_agent_collects_normalized_markdown(parsed_folder: Path) -> None:
    (parsed_folder / "full.md").write_text("# Title\n\n<div>debug</div>\n\n正文", encoding="utf-8")
    agent = DocumentParsingAgent(parser_component=FakeMinerUComponent())
    result = agent.parse_documents(["paper.pdf"])
    assert result.markdown_content == "# Title\n\n正文"
```

```python
def test_process_web_page_task_stores_normalized_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    async def fake_store_acquired_web_content(*, markdown_content: str, **kwargs: Any) -> str:
        captured["markdown_content"] = markdown_content
        return "literature/doc-1/source.md"

    ...
    _invoke_bound_task(tasks_module.process_web_page_task, "https://example.org", "doc-1", "paper-1", "req-1")
    assert captured["markdown_content"] == "# Example\n\n正文"
    assert "<div>" not in captured["markdown_content"]
```

**Step 2: Run the tests to verify they fail**

Run:
```bash
uv run --directory apps/backend pytest -q \
  tests/unit/test_firecrawl_service.py \
  tests/unit/test_document_parsing_agent.py \
  tests/unit/test_tasks.py::test_process_web_page_task_stores_normalized_markdown
```

Expected: FAIL because `FirecrawlService` still returns raw `cleaned_html` as markdown fallback, parser collection trusts `full.md` as-is, and the web task stores whatever crawl4ai returned.

**Step 3: Write the minimal implementation**

1. In `apps/backend/src/domain/literature/firecrawl_service.py`, normalize whichever text will become `result.markdown`.

```python
from src.domain.document_normalization import normalize_document_body

...
raw_markdown = str(getattr(markdown_obj, "fit_markdown", "") or "").strip()
fallback_html = str(getattr(result, "cleaned_html", "") or "").strip()
normalized = normalize_document_body(raw_markdown or fallback_html)
if not normalized.text:
    raise RuntimeError("Fetch no result from crawl4ai")
...
merged_metadata = {
    **metadata,
    "provider": "crawl4ai",
    "source_url": normalized_url,
    "normalized_body": True,
    "body_selector": normalized.body_selector,
}
return FirecrawlMarkdownResult(..., markdown=normalized.text, metadata=merged_metadata)
```

2. In `apps/backend/src/domain/agent/document_parsing.py`, normalize the markdown collected from parser output before returning it.

```python
from src.domain.document_normalization import normalize_document_body

...
markdown_content = markdown_path.read_text(encoding="utf-8")
normalized = normalize_document_body(markdown_content)
image_paths = [str(path) for path in sorted(root.rglob("*.jpg"))]
return normalized.text, image_paths
```

3. In `apps/backend/src/services/task_manager.py`, keep the current flow but ensure the stored web content is the already-normalized markdown and tag the storage metadata as normalized.

```python
acquisition_object_key = asyncio.run(
    _store_acquired_web_content(
        document_id=document_id,
        url=str(getattr(crawl_result, "final_url", None) or url),
        markdown_content=markdown_content,
        metadata={**(getattr(crawl_result, "metadata", None) or {}), "normalized_body": True},
    )
)
```

Do not add a new persistence model yet. Reuse `markdown_content` as the normalized canonical body text.

**Step 4: Run the tests to verify they pass**

Run:
```bash
uv run --directory apps/backend pytest -q \
  tests/unit/test_firecrawl_service.py \
  tests/unit/test_document_parsing_agent.py \
  tests/unit/test_tasks.py::test_process_web_page_task_stores_normalized_markdown
```

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 3: Add translation skip/validation rules so untranslated output cannot silently pass downstream

**Files:**
- Create: `apps/backend/src/services/translation_validation.py`
- Create: `apps/backend/tests/unit/test_translation_validation.py`
- Modify: `apps/backend/src/services/task_manager.py:157-169,1436-1531`
- Modify: `apps/backend/src/domain/agent/workflow.py:680-721`
- Modify: `apps/backend/src/agents/supervisor.py:102-126`
- Modify: `apps/backend/tests/unit/test_tasks.py:1197-1212,1622-1637`
- Modify: `apps/backend/tests/unit/test_domain_agent.py`
- Modify: `apps/backend/tests/test_supervisor_e2e.py:356-376`

**Step 1: Write the failing tests**

```python
from src.services.translation_validation import should_skip_translation, validate_translation_output
import pytest


def test_should_skip_translation_rejects_ascii_heavy_cjk_text() -> None:
    text = "NM_000059.4:c.7790G>A 研究显示该变异影响功能。Table 1 shows the assay result."
    assert should_skip_translation(text) is False


def test_validate_translation_output_rejects_untranslated_copy() -> None:
    source = "这是一段需要翻译的中文医学内容。"
    with pytest.raises(ValueError, match="translation_validation_failed"):
        validate_translation_output(source, source)
```

```python
def test_run_node_translation_fails_when_output_is_still_non_english(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_pg = _FakePostgresForNodes()
    node_trace: Dict[str, str] = {}

    def fake_translate_markdown(state: Any) -> Any:
        state["translated_md"] = "这是一段需要翻译的中文医学内容。"
        return state

    monkeypatch.setattr(tasks_module._agents, "translate_markdown", fake_translate_markdown)

    with pytest.raises(exc.TranslationError, match="translation_validation_failed"):
        tasks_module.run_node_translation(fake_pg, "paper-1", "这是一段需要翻译的中文医学内容。", node_trace)
```

```python
def test_translation_retranslates_invalid_existing_translation(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.agents.supervisor import translation

    mock_agent = MagicMock()
    mock_agent.translate_markdown.return_value = {"translated_md": "Translated English text."}

    state = _base_state(markdown_content="中文原文", translated_markdown="中文原文")
    with patch(f"{_NODE_PREFIX}.EvidenceAgent", return_value=mock_agent):
        result = translation(state)

    mock_agent.translate_markdown.assert_called_once()
    assert result.get("translated_markdown") == "Translated English text."
```

**Step 2: Run the tests to verify they fail**

Run:
```bash
uv run --directory apps/backend pytest -q \
  tests/unit/test_translation_validation.py \
  tests/unit/test_tasks.py::test_run_node_translation_fails_when_output_is_still_non_english \
  tests/test_supervisor_e2e.py::TestTranslationNode::test_translation_retranslates_invalid_existing_translation
```

Expected: FAIL because there is no validation module yet, `run_node_translation` only rejects empty output, and supervisor skips whenever `translated_markdown` is non-empty.

**Step 3: Write the minimal implementation**

Create `apps/backend/src/services/translation_validation.py` and use the existing `lingua-language-detector` dependency instead of the current ASCII-ratio shortcut.

```python
from __future__ import annotations

from difflib import SequenceMatcher
import re
from lingua import Language, LanguageDetectorBuilder

_DETECTOR = LanguageDetectorBuilder.from_languages(
    Language.ENGLISH,
    Language.CHINESE,
    Language.JAPANESE,
    Language.KOREAN,
).build()

_CJK_RE = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def should_skip_translation(text: str) -> bool:
    sample = str(text or "").strip()
    if not sample:
        return False
    if _CJK_RE.search(sample):
        return False
    detected = _DETECTOR.detect_language_of(sample[:4000])
    return detected == Language.ENGLISH


def validate_translation_output(source_text: str, translated_text: str) -> None:
    source = str(source_text or "").strip()
    translated = str(translated_text or "").strip()
    if not translated:
        raise ValueError("translation_validation_failed: empty")
    if _CJK_RE.search(translated):
        raise ValueError("translation_validation_failed: non_english_output")
    ratio = SequenceMatcher(None, source.lower(), translated.lower()).ratio()
    if source and ratio >= 0.85:
        raise ValueError("translation_validation_failed: unchanged")
    detected = _DETECTOR.detect_language_of(translated[:4000])
    if detected not in {None, Language.ENGLISH}:
        raise ValueError("translation_validation_failed: non_english_output")
```

Then wire it in three places:

1. Replace the `task_manager._detect_language` skip gate with `should_skip_translation`.

```python
from src.services.translation_validation import should_skip_translation, validate_translation_output

...
if should_skip_translation(md_content):
    ...
```

2. After HGVS correction in `run_node_translation`, validate before reporting success.

```python
corrected_text, all_restored = _attempt_hgvs_correction(md_content, en_text)
en_text = corrected_text
try:
    validate_translation_output(md_content, en_text)
except ValueError as exc_info:
    _log_node_end(
        postgres,
        paper_task_id,
        "translation",
        success=False,
        error_code="TRANSLATION_VALIDATION_FAILED",
        message=str(exc_info),
    )
    raise exc.TranslationError(str(exc_info)) from exc_info
```

3. In both `apps/backend/src/domain/agent/workflow.py` and `apps/backend/src/agents/supervisor.py`, only trust an existing translation if it passes validation.

```python
existing_translation = state.get("translated_md", "")
if isinstance(existing_translation, str) and existing_translation.strip():
    try:
        validate_translation_output(markdown_content, existing_translation)
        return state
    except ValueError:
        state["translated_md"] = ""
```

```python
existing = str(updated.get("translated_markdown", "") or "")
if existing:
    try:
        validate_translation_output(str(updated.get("markdown_content", "") or ""), existing)
        return cast(SupervisorState, cast(object, updated))
    except ValueError:
        updated["translated_markdown"] = ""
```

Do not add a new retry framework. Reuse the existing node-policy retries already in `task_manager.py:236-242, 408-449`.

**Step 4: Run the tests to verify they pass**

Run:
```bash
uv run --directory apps/backend pytest -q \
  tests/unit/test_translation_validation.py \
  tests/unit/test_tasks.py::test_run_node_translation_fails_when_output_is_still_non_english \
  tests/test_supervisor_e2e.py::TestTranslationNode::test_translation_retranslates_invalid_existing_translation
```

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 4: Replace the generic `/evidence/document/{document_id}` payload with a stable document-evidence contract

**Files:**
- Modify: `apps/backend/src/api/routes/evidence.py:48-54,93-110,205-224`
- Read: `apps/backend/src/infrastructure/minio.py:395-416`
- Read: `apps/backend/src/api/routes/core.py:379-410`
- Modify: `apps/backend/tests/integration/test_graph_api.py:42-53,141-147`
- Modify: `apps/backend/tests/integration/test_evidence_error_contract.py`

**Step 1: Write the failing tests**

```python
def test_get_document_evidence_returns_processed_text_and_graph(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    evidence_prefix: str,
) -> None:
    _patch_dependencies(monkeypatch)

    class DummyMinio:
        async def download_processed_result(self, object_key: str) -> bytes:
            if object_key == "12/original_format.md":
                return b"# Source\n\n\xe6\xad\xa3\xe6\x96\x87"
            if object_key == "12/en_format.md":
                return b"# Source\n\nEnglish body"
            raise FileNotFoundError(object_key)

        async def download_processed_result_json(self, document_id: str) -> bytes:
            assert document_id == "12"
            return b'{"strength": "PS3"}'

    monkeypatch.setattr(graph_api, "MinIOClient", DummyMinio)

    response = client.get(f"{evidence_prefix}/document/12")
    payload = response.json()["data"]

    assert payload["document_id"] == 12
    assert payload["source_text"].startswith("# Source")
    assert payload["translated_text"].endswith("English body")
    assert payload["ps3_evidence"]["strength"] == "PS3"
    assert payload["graph"]["total_evidence"] == 1
```

```python
def test_get_document_evidence_gracefully_handles_missing_artifacts(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    evidence_prefix: str,
) -> None:
    _patch_dependencies(monkeypatch)

    class DummyMinio:
        async def download_processed_result(self, object_key: str) -> bytes:
            raise FileNotFoundError(object_key)

        async def download_processed_result_json(self, document_id: str) -> bytes:
            raise FileNotFoundError(document_id)

    monkeypatch.setattr(graph_api, "MinIOClient", DummyMinio)

    response = client.get(f"{evidence_prefix}/document/12")
    payload = response.json()["data"]

    assert payload["source_text"] == ""
    assert payload["translated_text"] == ""
    assert payload["ps3_evidence"] == {}
    assert payload["graph"]["document_id"] == 12
```

**Step 2: Run the tests to verify they fail**

Run:
```bash
uv run --directory apps/backend pytest -q \
  tests/integration/test_graph_api.py::test_get_document_evidence_returns_processed_text_and_graph \
  tests/integration/test_graph_api.py::test_get_document_evidence_gracefully_handles_missing_artifacts
```

Expected: FAIL because the route still returns `SearchResult.to_dict()` directly and the response model only documents `data: Dict[str, Any]`.

**Step 3: Write the minimal implementation**

In `apps/backend/src/api/routes/evidence.py`, introduce a document-specific payload model and load processed artifacts from MinIO.

```python
import json
from src.infrastructure.minio import MinIOClient


class DocumentEvidencePayload(BaseModel):
    document_id: int | str
    source_text: str = ""
    translated_text: str = ""
    ps3_evidence: Dict[str, Any] = Field(default_factory=dict)
    graph: Dict[str, Any] = Field(default_factory=dict)
```

Add a small internal loader in the same file:

```python
async def _load_document_artifacts(document_id: str) -> tuple[str, str, Dict[str, Any]]:
    minio = MinIOClient()

    async def _read_text(object_path: str) -> str:
        try:
            payload = await minio.download_processed_result(f"{document_id}/{object_path}")
            return payload.decode("utf-8")
        except FileNotFoundError:
            return ""

    source_text = await _read_text("original_format.md")
    translated_text = await _read_text("en_format.md")
    try:
        ps3_evidence = json.loads(
            (await minio.download_processed_result_json(document_id)).decode("utf-8")
        )
    except FileNotFoundError:
        ps3_evidence = {}
    return source_text, translated_text, ps3_evidence
```

Change `get_document_evidence` so it preserves the existing graph search result under `graph` and merges the processed document artifacts into the stable contract:

```python
normalized_id, numeric_id = _parse_document_identifier(document_id)
result = engine.get_document_evidence(normalized_id)
graph_payload = _inject_document_identifier(result.to_dict(), normalized_id, numeric_id)
source_text, translated_text, ps3_evidence = await _load_document_artifacts(normalized_id)
payload = DocumentEvidencePayload(
    document_id=numeric_id if numeric_id is not None else normalized_id,
    source_text=source_text,
    translated_text=translated_text,
    ps3_evidence=ps3_evidence,
    graph=graph_payload,
)
return EvidenceSearchResponse(data=payload.model_dump())
```

Do not change the other evidence routes yet.

**Step 4: Run the tests to verify they pass**

Run:
```bash
uv run --directory apps/backend pytest -q \
  tests/integration/test_graph_api.py::test_get_document_evidence_returns_processed_text_and_graph \
  tests/integration/test_graph_api.py::test_get_document_evidence_gracefully_handles_missing_artifacts
```

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 5: Align frontend types and document/export pages with the stable backend contract

**Files:**
- Modify: `apps/frontend/src/types/api.ts:127-152`
- Modify: `apps/frontend/src/services/api.ts:100-103`
- Modify: `apps/frontend/src/utils/normalizeEvidence.ts:42-100`
- Modify: `apps/frontend/src/pages/documents/document-page.tsx:24-205`
- Modify: `apps/frontend/src/pages/requests/request-export-page.tsx:76-239`
- Modify: `apps/frontend/src/pages/documents/document-page.test.tsx`
- Modify: `apps/frontend/src/pages/requests/request-export-page.test.tsx`

**Step 1: Write the failing tests**

```tsx
it('document page renders stable document evidence payload instead of contract-warning fallback', async () => {
  vi.mocked(getEvidenceDocument).mockResolvedValue({
    code: 0,
    message: 'ok',
    data: {
      source_text: 'source text',
      translated_text: 'translated text',
      ps3_evidence: { strength: 'PS3' },
      graph: { total_evidence: 1 },
    },
  });
  ...
  expect(await screen.findByText(/Structured evidence/i)).toBeInTheDocument();
  expect(screen.queryByText(/without a stable evidence schema/i)).not.toBeInTheDocument();
})
```

```tsx
it('request export page renders reading columns from the stable document evidence payload', async () => {
  vi.mocked(getEvidenceDocument).mockResolvedValue({
    code: 0,
    message: 'ok',
    data: {
      source_text: '段落一\n\n段落二',
      translated_text: 'Paragraph one\n\nParagraph two',
      ps3_evidence: {},
      graph: { total_evidence: 1 },
    },
  });
  ...
  expect(await screen.findByText(/Paragraph one/i)).toBeInTheDocument();
})
```

**Step 2: Run the tests to verify they fail**

Run:
```bash
npm --prefix apps/frontend run test:run -- \
  src/pages/documents/document-page.test.tsx \
  src/pages/requests/request-export-page.test.tsx
```

Expected: FAIL because frontend typing still treats the payload as generic `unknown`, `DocumentPage` still displays the “without a stable evidence schema” warning, and `getEvidenceDocument` does not expose a document-specific response type.

**Step 3: Write the minimal implementation**

1. In `apps/frontend/src/types/api.ts`, add a document-specific response type and sync the task-status type with fields the backend already returns.

```ts
export type DocumentEvidencePayload = {
  document_id?: string | number;
  source_text: string;
  translated_text: string;
  ps3_evidence?: Record<string, unknown>;
  graph?: Record<string, unknown>;
};

export type DocumentEvidenceResponse = {
  code: number;
  message: string;
  data: DocumentEvidencePayload;
};

export type TaskStatusResponse = {
  task_id: string;
  status: string;
  workflow_status?: string | null;
  workflow_status_description?: string | null;
  progress_percentage?: number | null;
  processing_steps?: Record<string, unknown> | null;
  paper_task_id?: string | null;
  document_id?: string | null;
  file_size_bytes?: number | null;
  processing_duration_seconds?: number | null;
  warning_codes?: string[] | null;
  trace_chain?: Record<string, unknown> | null;
  parsing_metadata?: Record<string, unknown> | null;
  error?: string | null;
  error_details?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
};
```

2. In `apps/frontend/src/services/api.ts`, make `getEvidenceDocument` return the stable document type.

```ts
export async function getEvidenceDocument(documentId: string, options: ApiCallOptions = {}) {
  return requestGetJson<DocumentEvidenceResponse>(`/evidence/document/${encodeURIComponent(documentId)}`, {
    signal: options.signal
  });
}
```

3. In `apps/frontend/src/utils/normalizeEvidence.ts`, prefer `source_text` / `translated_text` directly and keep only a light fallback.

```ts
const sourceText = asString(data.source_text) ?? '';
const targetText = asString(data.translated_text) ?? '';
if (sourceText || targetText) {
  ...
  return {
    sourceLang: 'source',
    targetLang: 'en',
    segments,
    raw: data,
  };
}
```

4. In `apps/frontend/src/pages/documents/document-page.tsx`, replace the current raw-contract disclaimer with a stable structured-evidence panel.

```tsx
<div style={{ fontWeight: 800 }}>Structured evidence</div>
<div className="muted" style={{ marginTop: 6 }}>
  Stable document evidence payload from the backend.
</div>
<pre ...>
  {JSON.stringify(payload?.data.ps3_evidence ?? payload?.data.graph ?? {}, null, 2)}
</pre>
```

5. In `apps/frontend/src/pages/requests/request-export-page.tsx`, keep the existing reading layout but rely on the same stable response type returned by `normalizeEvidence`.

Do not redesign the UI in this task. Only remove the contract mismatch and make the existing reading/export views work reliably.

**Step 4: Run the tests to verify they pass**

Run:
```bash
npm --prefix apps/frontend run test:run -- \
  src/pages/documents/document-page.test.tsx \
  src/pages/requests/request-export-page.test.tsx
```

Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

## Final verification

After Task 1-5 pass individually, run the focused end-to-end slice below.

**Backend verification**

Run:
```bash
uv run --directory apps/backend pytest -q \
  tests/unit/test_document_normalization.py \
  tests/unit/test_firecrawl_service.py \
  tests/unit/test_document_parsing_agent.py \
  tests/unit/test_translation_validation.py \
  tests/unit/test_tasks.py::test_process_web_page_task_stores_normalized_markdown \
  tests/unit/test_tasks.py::test_run_node_translation_fails_when_output_is_still_non_english \
  tests/test_supervisor_e2e.py::TestTranslationNode::test_translation_retranslates_invalid_existing_translation \
  tests/integration/test_graph_api.py::test_get_document_evidence_returns_processed_text_and_graph \
  tests/integration/test_graph_api.py::test_get_document_evidence_gracefully_handles_missing_artifacts
```

Expected: PASS.

**Frontend verification**

Run:
```bash
npm --prefix apps/frontend run test:run -- \
  src/pages/documents/document-page.test.tsx \
  src/pages/requests/request-export-page.test.tsx
```

Expected: PASS.

**Optional build-level verification after the targeted tests are green**

Run:
```bash
npm --prefix apps/frontend run build
```

Expected: PASS.
