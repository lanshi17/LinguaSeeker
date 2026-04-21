# COAJ Chinese Fulltext Fallback Design

## Goal
Use COAJ as a Chinese DOI fulltext fallback, with Unpaywall as the cross-language DOI fallback after primary download failure, so the two Chinese acceptance samples can move past `FULLTEXT_UNAVAILABLE` and enter the existing parsing/extraction pipeline.

## Scope
This design is intentionally narrow.

In scope:
- add a minimal COAJ DOI lookup helper
- enhance download fallback orchestration in `task_manager.py`
- re-run only the two Chinese samples for validation

Out of scope:
- making COAJ a first-class search provider
- changing literature candidate search architecture
- frontend changes
- full 15-paper revalidation in this slice

## Chosen Approach
### Primary approach
Add fallback logic at the download layer only.

Current behavior:
1. candidate selection succeeds
2. primary provider download fails
3. pipeline returns `FULLTEXT_UNAVAILABLE`

New behavior:
1. candidate selection succeeds
2. primary provider download fails
3. if DOI exists:
   - for Chinese samples, try COAJ DOI metadata lookup first
   - if COAJ cannot provide a usable PDF URL, try Unpaywall
4. if any fallback produces a usable PDF URL, continue through the existing `process_pdf_task` path
5. only return `FULLTEXT_UNAVAILABLE` if all fallback sources fail

This keeps the architecture stable while directly addressing the current blocker.

## Why this approach
- smallest surface area
- least regression risk
- most direct path to improving the two Chinese failures
- preserves the current multilingual provider architecture
- reuses existing downstream parsing / extraction / graph code unchanged

## Integration points
### 1. New COAJ helper
Add a small helper under `apps/backend/src/domain/literature/api/coaj/`.

Responsibilities:
- call `GET https://coaj.cn/api/v1/open/article/basic?doi=...`
- parse the response
- extract:
  - article title
  - journal info
  - article `pdfPath`
- normalize `pdfPath` into a final downloadable URL

Expected output shape should be minimal and internal, e.g.:
- `success`
- `doi`
- `title`
- `pdf_url`
- `journal`
- `publisher`
- `raw`

### 2. Download fallback orchestration
Enhance `_try_download_and_store_literature_pdf(...)` in `apps/backend/src/services/task_manager.py`.

Fallback order after the primary download fails:
1. primary provider
2. Chinese DOI -> COAJ
3. any DOI -> Unpaywall

Behavior notes:
- Chinese means the current sample/lane is recognized as Chinese via provider, language, or request context
- COAJ is only attempted when DOI is available
- Unpaywall remains the final DOI fallback for all languages
- successful fallback should still populate `source_trace` / warnings so later inspection shows how the PDF was obtained

### 3. No search-layer changes in this slice
Do not modify:
- provider matrix
- candidate ranking
- unified search routing
- frontend API or page behavior

The fallback is purely a fulltext recovery mechanism.

## PDF URL construction for COAJ
The COAJ response includes `article.pdfPath`, which may be a relative path.

Use the following normalization rules:
1. if `pdfPath` is already absolute, use it directly
2. if `pdfPath` starts with `/`, join with `https://coaj.cn`
3. otherwise prefix with `https://coaj.cn/`

Result must be a final PDF URL that can be downloaded with the existing downloader.

## Testing strategy
### Unit tests
Add targeted tests to `apps/backend/tests/unit/test_tasks.py` for:
1. primary failure + Chinese DOI -> COAJ success
2. primary failure + Chinese DOI + COAJ failure -> Unpaywall success
3. primary failure + non-Chinese DOI -> Unpaywall success
4. no DOI -> no COAJ / no Unpaywall fallback

If helper-specific tests are easier to isolate, add a focused COAJ helper test module too.

### Focused acceptance validation
Only re-run these two real samples after implementation:
1. Chinese DNAJB2 sample
2. Chinese ANK1 sample

Validation target:
- no longer fail at `FULLTEXT_UNAVAILABLE`
- enter parsing / extraction flow
- ideally reach `paper_status = success`
- if they still fail, the failure must be downstream of fulltext acquisition

## Success criteria
This slice is successful when:
1. COAJ fallback is implemented for Chinese DOI samples
2. Unpaywall fallback still works after COAJ fallback fails
3. the two Chinese samples no longer fail purely because fulltext could not be obtained
4. logs and trace data make it visible which fallback source was used

## Risks
- COAJ `pdfPath` may not always be a direct file path
- COAJ may return metadata but not a usable fulltext URL for all records
- some Chinese pages may still require HTML-to-markdown fallback later if no PDF exists anywhere

## If this slice is not enough
If one or both Chinese samples still fail after this design is implemented, the next step should be:
- add HTML/正文 fallback for PubScholar / Hans detail pages
- not broaden COAJ into the candidate search layer yet
