# AGENT.md

## 1. Purpose
This file defines the execution contract for engineering agents working on this repository.
All implementation decisions must follow the frozen product specifications in:
1. `docs/PRD.md`
2. `docs/APP_FLOW.md`
3. `docs/TECH_STACK.md`
4. `docs/FRONTEND_GUIDELINES.md`
5. `docs/BACKEND_STRUCTURE.md`
6. `docs/IMPLEMENTATION_PLAN.md`

If any conflict appears, resolve by priority:
1. `docs/PRD.md`
2. `docs/BACKEND_STRUCTURE.md`
3. `docs/APP_FLOW.md`
4. Remaining docs

## Project Rules
1. The project must use **uv** exclusively for dependency installation and management; the use of other tools such as pip or conda is prohibited.
2. With the exception of the main entry file, all business code must be placed in **src/**.
3. All documentation must be centralized in **docs/**.
4. All test files must be centralized in **tests/**.
5. Upon completion of each task milestone, the project progress must be recorded in the root directory’s **progress.txt** file.
6. Each debugging session or iterative troubleshooting effort must be reviewed and documented in **lesson.md**.
7. Logging must be implemented using **loguru**, with log files stored in **logs/** and named by date and time (e.g., YYYY-MM-DD_HHMMSS.log); the testing framework must be **pytest**.
8. Scripts related to initialization and startup must be centralized in **scripts/**.
9. Database-related files must be centralized in **database/**.
10. Any ambiguous requirements must be clarified through consultation and confirmation; making assumptions on one’s own is strictly prohibited.
11. The primary integration branch for this repository is **`yangzs-agents`**.

## 2. Scope (MVP)
Implement the main 6-node workflow:
1. Literature acquisition
2. Document parsing
3. Multilingual processing
4. Evidence extraction
5. ACMG classification (PS3/BS3 only)
6. Expert adjudication

Out of scope for MVP:
1. Quality assessment agent
2. Quality API (must be removed, legacy calls return 404)
3. pgvector migration (keep Qdrant)
4. Illegal or unauthorized data-source integrations, including paywall-bypass strategies

## 3. Hard Requirements
1. Primary goal is evidence-source explainability.
2. Task form must be natural language and persisted.
3. Query clarification max rounds: 2.
4. Request IDs and paper task IDs must be UUIDv4.
5. One Celery task per paper.
6. Request status set: `queued/running/partial_failed/failed/success`.
7. Paper status set: `queued/running/success/failed`.
8. `FILE_DUPLICATE` must be counted in both success numerator and denominator.
9. If all papers in one request are duplicates, request status must be `success`.

## 4. Data Source and Compliance
1. MVP literature acquisition uses approved multi-source adapters only:
   - API: `biopython/pubmed`, `pmc`, `crossref`, `doaj`, `jstage`, `unpaywall`
   - Crawler: `hans_publishers`, `pubscholar`, `cyberleninka`
2. The legacy Firecrawl naming in helper modules is compatibility-only. Current web crawling must use the crawl4ai-backed path and current retrieval configuration, not old Firecrawl-specific config keys.
3. Do not introduce or rely on `FIRECRAWL_*` environment variables for active flows. Use the repository's current retrieval/web acquisition configuration surface instead.
2. Country mapping is ISO-based and must not degrade to language-only approximation.
3. Unsupported country mapping or empty hit must return `FETCH_NO_RESULT`.
4. Full text unavailable must fall back to metadata+abstract evidence with `fulltext_unavailable=true`.
5. Only legal and authorized sources are allowed.

## 5. Upload and Dedup Rules
1. Allowed file types: PDF, DOCX.
2. Upload limits:
   - max files: 10
   - max file size: 10MB
   - max total size: 50MB
3. Dedup strategy: global SHA-256.
4. On duplicate:
   - create new `paper_task_id`
   - set status `success`
   - set error code `FILE_DUPLICATE`
   - set `duplicate_of=<historical_paper_task_id>`
   - skip processing nodes

## 6. Model and Processing Rules
1. Model routing by task type:
   - translation: `MT_MODEL`
   - evidence extraction: `EVIDENCE_MODEL`
   - ACMG: `ARBITRATION_MODEL`
2. Parsing uses MinerU, fallback to PaddleOCR-VL-1.5 (inside parsing node).
3. DOCX parse failure is terminal for that paper.
4. If source text is English, skip translation.
5. On HGVS/gene corruption during translation, auto-correct; if correction fails, continue with warning `HGVS_AUTOCORRECT_FAILED`.
6. Alignment must be stored in PostgreSQL alignment table and keep both English-first and source coordinates.

## 7. Retry/Failure Policy
Node retry defaults and caps:
1. acquisition: `default_retries=2, retries_cap=5, delay=300s, timeout=900s`
2. parsing: `default_retries=1, retries_cap=3, delay=600s, timeout=1800s`
3. translation: `default_retries=2, retries_cap=4, delay=120s, timeout=1200s`
4. extraction: `default_retries=2, retries_cap=4, delay=300s, timeout=1800s`
5. acmg_classification: `default_retries=1, retries_cap=3, delay=180s, timeout=900s`
6. expert_adjudication: `default_retries=1, retries_cap=3, delay=180s, timeout=900s`

Source ordering and source-level retries remain dynamically decided within these caps.

Failure handling:
1. No automatic reopen for business users.
2. Ops can manually reopen by script only.
3. Reopen reuses original `paper_task_id`.
4. Log event `reopened_by_ops_script`.

## 8. Error Contract
All failed API responses must return:
1. `status=failed`
2. `error_code`
3. `log_link`

Frozen error code set:
`INPUT_INVALID, FILE_TOO_LARGE, FILE_TYPE_UNSUPPORTED, FILE_DUPLICATE, FETCH_TIMEOUT, FETCH_NO_RESULT, FULLTEXT_UNAVAILABLE, PARSE_FAILED, OCR_FAILED, OCR_TIMEOUT, TRANSLATION_FAILED, TRANSLATION_EMPTY, ALIGNMENT_FAILED, ENTITY_EXTRACTION_FAILED, EVIDENCE_EXTRACTION_FAILED, ACMG_RULE_UNSUPPORTED, ACMG_PARSE_FAILED, GRAPH_SYNC_FAILED, TASK_TIMEOUT, INTERNAL_ERROR`

## 9. Logging and Link Reissue
1. `log_link` is a signed temporary URL.
2. URL validity: 24 hours.
3. Reissue is allowed.
4. Reissue rate limit: 1 request per minute per `task_id`.
5. Any logged-in user can reissue (accepted risk).

## 10. Retention Policy
1. Keep forever:
   - task form text
   - structured task metadata
2. Keep but no auto-delete:
   - original uploaded files (ops may manually clean)
3. Auto-delete after 7 days:
   - parsing intermediate artifacts
   - runtime logs

## 11. KG Service Contract
1. KG is an independent service.
2. Main service emits Celery events to trigger KG updates.
3. KG reads from PostgreSQL and updates Neo4j.
4. First launch must support full backfill script + incremental updates.
5. Backfill must support resume from checkpoint.
6. KG retry queue uses ACMG node retry policy.

## 12. Release Acceptance Gate
Per release number:
1. fixed 100-paper acceptance set must not change within same release
2. literature-level success rate >= 95%
3. per-paper end-to-end time <= 30 minutes, measured from worker start
4. six-language support: ZH/EN/JA/FR/DE/RU

## 13. Change Control
No silent requirement change is allowed.
Any change to statuses, error codes, retries, retention, or acceptance metrics requires:
1. doc update in `docs/`
2. explicit release note
3. backward impact statement
