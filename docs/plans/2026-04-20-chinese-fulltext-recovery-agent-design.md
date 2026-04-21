# Chinese Fulltext Recovery Agent Design

## Goal
Add a dedicated Chinese fulltext recovery layer so the two Chinese target papers can move past `FULLTEXT_UNAVAILABLE` even when no usable PDF is available from the primary source, COAJ, or Unpaywall.

## Scope
This design is intentionally narrow.

In scope:
- add a dedicated LangGraph agent for Chinese fulltext recovery
- use deterministic body extraction first
- use format LLM normalization only as a fallback
- wire the result into the existing backend processing path for the two Chinese samples

Out of scope:
- changing literature candidate search architecture
- turning COAJ into a first-class search provider
- changing frontend behavior
- broad multilingual fallback logic beyond the Chinese body path

## Chosen Approach
When PDF acquisition fails for a Chinese source, call a separate LangGraph agent that tries to recover a usable正文/markdown body from the article detail page.

Flow:
1. primary provider PDF download fails
2. Chinese DOI fallback tries COAJ
3. DOI fallback tries Unpaywall
4. if all PDF fallbacks fail but we still have a detail page URL for a Chinese source, invoke a Chinese Fulltext Recovery Agent
5. if the agent returns a validated normalized markdown body, continue with the existing parsing/translation/extraction flow without requiring a PDF
6. only return `FULLTEXT_UNAVAILABLE` when the agent also fails

This keeps the current system architecture stable while giving Chinese web sources a realistic way to proceed without a standards-compliant PDF.

## Why this approach
- directly targets the current Chinese blocker
- avoids forcing LLM on all pages
- deterministic extraction remains the default path
- the LangGraph agent is only used for hard cases
- lowest-risk way to extend the system without rewriting the supervisor graph

## Integration points
### 1. New agent package
Add a small dedicated package under:
- `apps/backend/src/agents/chinese_fulltext_recovery/agent.py`
- `apps/backend/src/agents/chinese_fulltext_recovery/tools.py`

The agent should be independent of the supervisor graph. It is a download-layer recovery mechanism, not a new top-level workflow branch.

### 2. Download layer hook
Modify:
- `apps/backend/src/services/task_manager.py`

Enhance `_try_download_and_store_literature_pdf(...)` so that after:
1. primary provider download fails
2. Chinese DOI -> COAJ fails
3. DOI -> Unpaywall fails

it can optionally call:
- `run_chinese_fulltext_recovery(...)`

when all of the following are true:
- source is Chinese-origin web content
- a detail page URL is available
- no usable PDF was recovered

### 3. Existing processing chain reuse
Modify `process_literature_identifier_task(...)` so it accepts either:
- `local_file_path` -> send into `process_pdf_task.run(...)`
- `normalized_markdown` -> send into the existing markdown-based extraction path

Recommended implementation:
- extract the markdown continuation logic currently embedded in `process_web_page_task(...)` into a small reusable helper
- then reuse it for Chinese recovered markdown bodies

Do not duplicate translation/extraction/graph sync code a second time.

## LangGraph state
Use a minimal state shape only for Chinese body recovery:

```python
class ChineseFulltextRecoveryState(TypedDict, total=False):
    source_url: str
    provider: str
    doi: str | None
    html: str
    extracted_body: str
    normalized_markdown: str
    body_selector: str | None
    warnings: list[str]
    status: str
```

## Nodes and tools
### Node 1: fetch_detail_html
Use a tool in `tools.py` to fetch the detail page HTML.

Input:
- `source_url`

Output:
- `html`
- `status=html_fetched`
- `warnings` when redirects/login wrappers are encountered

Prefer a deterministic HTTP/crawler fetch over LLM.

### Node 2: extract_readable_body
Use a tool that:
- applies `normalize_document_body(...)`
- optionally applies source-specific selectors for:
  - Yiigle-style pages
  - Hans Publishers pages

Output:
- `extracted_body`
- `body_selector`

Goal:
- recover the title / abstract / main body without invoking the LLM first

### Node 3: should_normalize_with_llm
Route node only.

If extracted body is already good enough, skip the LLM.

Heuristics:
- body length over threshold
- multiple paragraphs exist
- not obviously navigation/login text
- not dominated by menus/boilerplate

### Node 4: normalize_body_with_format_llm
Only runs when Node 3 says the deterministic extraction is not sufficient.

Use the existing format-model configuration.

Prompt constraints:
- do not invent facts
- preserve original language
- only restructure/clean
- output normalized markdown with sections when possible

### Node 5: validate_normalized_body
Use deterministic checks:
- non-empty
- above minimum length
- not login/navigation boilerplate
- contains enough body text to justify downstream processing

If valid:
- `status=ready`
- return `normalized_markdown`

If invalid:
- `status=failed`

## Result contract
The recovery agent should return a small internal contract like:

```python
{
  "success": True,
  "normalized_markdown": "...",
  "provider": "chinese_fulltext_recovery",
  "warnings": ["fallback:html_body"],
  "body_selector": "article"
}
```

or:

```python
{
  "success": False,
  "warnings": ["fallback:html_body_failed"],
  "reason": "no_usable_body"
}
```

## Testing strategy
### Unit tests
Add focused tests for:
1. detail page HTML fetch succeeds
2. deterministic body extraction succeeds without LLM
3. deterministic extraction fails quality gate and triggers LLM normalization
4. invalid LLM output is rejected
5. `_try_download_and_store_literature_pdf(...)` returns `normalized_markdown` after PDF fallbacks fail
6. `process_literature_identifier_task(...)` continues when it receives `normalized_markdown`

### Chinese sample validation
Only re-run:
- DNAJB2 sample
- ANK1 sample

Success criteria:
- no longer stop at `FULLTEXT_UNAVAILABLE`
- at minimum reach translation/extraction stage
- ideally produce non-empty document content and graph records

## Success criteria
This slice is successful when:
1. Chinese PDF failure no longer necessarily ends in `FULLTEXT_UNAVAILABLE`
2. the recovery agent can return usable normalized markdown for Chinese detail pages
3. the existing processing chain can consume recovered markdown without requiring a PDF
4. at least one of the two Chinese target samples moves beyond the current fulltext-acquisition failure mode

## Risks
- some Chinese pages may still be mostly login or shell HTML
- format LLM normalization may clean structure but still not recover enough domain detail
- source-specific selectors may be needed for stable extraction

## If this slice still fails
If the two Chinese samples still do not progress after this agent is added, the next step should be:
- source-specific extractor rules for Yiigle and Hans DOM structures
- not expanding COAJ search scope
