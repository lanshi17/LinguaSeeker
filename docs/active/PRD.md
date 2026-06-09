# PRD — ACMG Lingua

## 1. Product Positioning

ACMG Lingua is a next-generation medical genetics literature evidence mining and structured traceability workbench. It is an "evidence porter" — absolutely loyal to source data, ensuring every piece of extracted information is 100% traceable to its original location in the literature. The system organizes evidence collection, extraction, standardization, and expert review behind four fixed tabs: AI Assistant, Task Board, Knowledge Base Query, and Settings. (Note: this is the target design. The current implementation provides: Auth, Pipeline, Evidence Search, and Chat.)

The system provides a high-quality data foundation for downstream clinical interpretation and research computation. It does not perform final autonomous ACMG/GDV medical classification in the current scope.

### Design Principles

- **Minimal**: Every screen element must justify its existence. No decorative chrome.
- **Transparent**: Every piece of data must be traceable to its source. No black-box summaries that hide extraction provenance.
- **Restrained**: The system is an evidence porter, not a diagnostician. It collects, structures, and presents — it does not interpret.
- **Conversation-driven**: Literature processing is driven through natural conversation in the AI Assistant tab, not through multi-page form wizards.
- **Tab-organized**: Four fixed tabs provide clear, single-responsibility workspaces. No nested menus or hidden pages.
- **Open by default**: No user isolation in open-source deployment. Transparency replaces permission systems — all actions are recorded in audit logs.

## 1.1 Preferred Architecture Direction

New modules and components should prefer **Orchestrated Vertical Slice Architecture**: a thin orchestrator owns workflow topology, routing, and state transitions, while vertical feature slices own cohesive business logic end to end. The orchestrator decides **how the pipeline is connected**; feature packages decide **what a domain step does**.

For backend implementation, this maps to `src/agents/` as the orchestration layer, `src/core/<pipeline-slice>/` as feature slices, `src/core/config.py` plus `src/utils/`/`src/dao/` as shared infrastructure, and Pydantic contracts as the state/data boundary. For frontend implementation, route pages compose feature-oriented components and hooks rather than embedding pipeline logic directly in page files.

Design implications:

- Keep `GraphState`/task state as the single typed source of truth for pipeline data flow.
- Expose each feature to the orchestrator through a small node/API function that unpacks state, calls feature core logic, and returns a typed state delta.
- Keep LLM, database, file, and external-service SDK calls behind feature-local providers or shared clients; pure core logic must not depend directly on SDKs.
- Trace node input/output, duration, warnings, and errors consistently so evidence generation is linearly observable.

## 2. Core Problems

| Problem | Product Response |
|---|---|
| Literature collection and reading consume expert time | Cross-database search, batch download, PMID/DOI/keyword workflows, and local PDF/DOCX upload shorten single-gene or variant literature gathering from hours to minutes. |
| Cross-language and multimodal evidence is missed | Use dual extraction: original-language native extraction plus translated-text secondary extraction, then cross-validate, deduplicate, fuse, and preserve bilingual traceability. |
| Evidence collection is fragmented and hard to standardize | Convert unstructured papers into a standardized evidence matrix with normalized genes, variants, diseases, phenotypes, methods, results, and source links. |
| Entity aliases and cross-database lookups are error-prone | Align extracted entities with HGNC, ClinVar, dbSNP, OMIM, HPO, ClinGen, and related public databases through exact, synonym, vector, and Agent-assisted conflict resolution. |
| Expert extraction experience is hard to reuse | Preserve original-text and translated-text absolute source positions, structured feedback, and corrected original-translation-evidence triples for institutional extraction knowledge bases and future model/prompt improvement. |

## 3. Target Users

> **Implementation note:** User stories below describe target UX. The current implementation covers Pipeline submission/monitoring, Evidence search, and Chat.

The personas below are product users, not authorization roles. In open-source deployment, there is no user isolation — all tabs and task lists are visible to all visitors. Data transparency is maintained through audit logs rather than permission systems.

| User Persona | Technical Level | Primary Use Case |
|---|---|---|
| Clinical Geneticist | No coding | Chat with AI Assistant to upload papers and review inline evidence cards; search knowledge base for variant evidence. |
| Bioinformatics Analyst | Low/no coding | Batch collect and normalize variant/gene literature evidence; monitor task board; export structured data from knowledge base. |
| Researcher | No coding | Mine multilingual literature via AI Assistant; query knowledge base with natural language for phenotypes, experiments, population data. |
| Genetic Counselor | No coding | Review evidence chains in workspace; generate ACMG classification drafts; export evidence summary reports. |
| Lab Technician | No coding | Upload local PDF/DOCX documents via AI Assistant; verify extracted data in evidence cards. |

### US-1: Chat-Driven Literature Upload and Processing

As a clinical geneticist, I open the AI Assistant tab, drag a PDF into the chat input, or type a PMID. The system streams parsing progress as a system message bubble with SSE typewriter effect, then renders structured evidence form cards inline in the chat. I can edit fields directly in the cards, correct errors via natural language, and confirm each card for ingestion.

### US-2: Inline Evidence Card Editing and Natural Language Correction

As a researcher reviewing extracted evidence, I see evidence form cards embedded in the chat stream. I click into any editable field (HPO phenotype, ACMG rule, conclusion label) and modify it inline. When I notice a systematic error, I type a natural language correction in the chat input ("change all PS3 to PS3_moderate for this paper"), and the system updates the cards accordingly. All edits are silently recorded in the delta audit log.

### US-3: Task Board Monitoring and Batch Operations

As a bioinformatics analyst, I switch to the Task Board tab to see all tasks across their lifecycle: parsing, extracting, pending review, completed, failed. I filter by status, search by PMID or gene name, select multiple failed tasks, and trigger batch retry. I open the resource monitoring panel to check queue depth and processing throughput.

### US-4: Evidence Workspace Review with Source Traceability

As a reviewer, I click "View Workspace" on a task board entry. The workspace shows the parsed Markdown document on the left and evidence cards on the right. I click a card, and the left pane scrolls to the corresponding source paragraph with a breathing-light highlight. I use keyboard shortcuts (J/K to navigate cards, E to edit, Enter to confirm) for rapid review. I open the traceability drawer to see the exact original text that produced each data point.

### US-5: Knowledge Base Query and Evidence Matrix Exploration

As a genetic counselor, I switch to the Knowledge Base Query tab and search for a variant by HGVS notation or gene symbol. I see a metadata dashboard and a flat evidence matrix grouped by ACMG/ClinGen evidence dimension. I expand groups, compare evidence rows across papers, and trace any data point back to its source literature via the slide-out drawer. I export a CSV of the evidence matrix or generate an ACMG classification draft.

### US-6: Natural Language to SQL Query

As a researcher, I switch the knowledge base search to AI Query mode and type: "find all functional assay evidence for BRCA1 published after 2022 with loss-of-function conclusions." The system generates and displays the corresponding SQL, executes it, and renders the result set in the evidence matrix. I can inspect and copy the SQL for my own use.

### US-7: Batch Offline Processing

As a lab technician, I toggle batch mode in the AI Assistant, upload a `.txt` file containing 20 PMIDs, and continue working. The system silently processes all papers in the background. When I return to the Task Board, all 20 tasks appear in the "pending review" queue. A notification entry appears in my chat history sidebar.

### US-8: Settings and Vocabulary Management

As a system administrator, I open the Settings tab to view current ontology versions (HPO, OMIM, ClinVar, gnomAD), trigger version checks and updates, review extraction prompt templates per evidence dimension, and configure MinerU parsing parameters and database connection strings.
## 5. Functional Requirements

### Phase 1: Literature Acquisition and Digitization

> **Status: DONE** — all core requirements implemented.

| ID | Requirement | Priority |
|---|---|---|
| F1.1 | Accept local PDF upload, including scanned PDFs. | P0 |
| F1.2 | Accept local DOCX upload. | P0 |
| F1.3 | Accept PMID/DOI input for literature retrieval. | P0 |
| F1.4 | Accept keyword search across configured providers. | P1 |
| F1.5 | Extract metadata before full OCR/parsing when possible: DOI, PMID, authors, year, journal, source quality signals. | P1 |
| F1.6 | Parse PDF through MinerU primary path and PaddleOCR fallback. | P0 |
| F1.7 | Convert documents to Markdown/HTML with source anchors and bounding boxes. | P0 |
| F1.8 | Reject parse output that cannot provide source anchors or bbox-backed spans for evidence review. | P0 |
| F1.9 | Parse tables into structured JSON/CSV where available. | P1 |
| F1.10 | Generate VLM image descriptions for figures, pedigrees, plots, and functional assay diagrams. | P1 |
| F1.11 | Chunk long documents by logical section and paragraph while preserving source span mapping. | P0 |
| F1.12 | Support multilingual sources including Chinese, Japanese, German, Russian, Korean, and English. | P0 |

### Phase 2: Cross-Lingual Processing and Dual Evidence Extraction

> **Status: IN PROGRESS** — translation and multi-stage evidence extraction implemented; dual-track cross-validation and fusion still being refined.

| ID | Requirement | Priority |
|---|---|---|
| F2.1 | Perform original-language native entity/relation/evidence extraction before translation. | P0 |
| F2.2 | Translate document sections or evidence-bearing chunks to standard English/Chinese after native extraction. | P0 |
| F2.3 | Perform translated-text secondary extraction on the translated content. | P0 |
| F2.4 | Preserve biomedical literals across both passes: HGVS, gene symbols, transcript IDs, protein names, rsIDs, accession IDs, measurements. | P0 |
| F2.5 | Use coarse-grained filtering to identify paragraphs/regions likely containing target evidence. | P1 |
| F2.6 | Use fine-grained extraction Agents for phenotypes, experimental methods, experimental results, population frequency, segregation, and other target evidence. | P0 |
| F2.7 | Cross-validate, deduplicate, and fuse original-language JSON and translated-text JSON into unified evidence items. | P0 |
| F2.8 | Output structured JSON with confidence scores, agreement status, and fusion rationale per field/evidence item. | P0 |
| F2.9 | Link each evidence item to bi-directional traceability anchors: original page/line/bbox and translated page/line/bbox where available. | P0 |
| F2.10 | Support table-derived, figure-derived, and text-derived evidence items. | P1 |

### Phase 3: Entity Standardization and Knowledge Alignment

> **Status: IN PROGRESS** — exact and similarity matching implemented; pgvector semantic matching and Agent conflict resolution planned.

| ID | Requirement | Priority |
|---|---|---|
| F3.1 | Match gene symbols and aliases against HGNC. | P0 |
| F3.2 | Match diseases against OMIM, MONDO, and HPO. | P0 |
| F3.3 | Match variants against ClinVar and dbSNP. | P0 |
| F3.4 | Align gene-disease context against ClinGen and OMIM where available. | P1 |
| F3.5 | Query population frequency from gnomAD where available. | P1 |
| F3.6 | Preserve original extracted values and translated extracted values alongside standardized values. | P0 |
| F3.7 | Use exact matching first, then synonym matching, then pgvector/embedding semantic matching. | P1 |
| F3.8 | Invoke heuristic + Agent conflict resolution for ambiguous aliases or multiple candidate entities. | P1 |
| F3.9 | Store standardized evidence matrix with match rationale and bilingual traceability. | P0 |

### Phase 4: Evidence Visualization, Task Management, Knowledge Base, and Expert-in-the-Loop

> **Status: PARTIALLY DONE** — Pipeline submission/monitoring, Evidence search, and Chat features are implemented. The full 4-tab UI (AI Assistant, Task Board, Knowledge Base Query, Settings), evidence workspace with traceability, and batch processing are planned.

| ID | Requirement | Priority |
|---|---|---|
| F4.1 | AI Assistant tab: chat-driven upload (drag-drop PDF, PMID input), SSE streaming parse progress, inline evidence form cards with editable fields. | P0 |
| F4.2 | Evidence cards: HPO autocomplete search, ACMG rule selector, conclusion label dropdown, source snippet expansion, silent delta recording on edits. | P0 |
| F4.3 | Natural language correction in chat: user describes errors, system updates card fields and re-renders. | P0 |
| F4.4 | Chat session persistence: history sidebar with search by PMID/gene/date; click to restore full conversation context. | P0 |
| F4.5 | Task Board tab: status-filtered list, search, multi-select, batch retry/delete/export CSV. | P0 |
| F4.6 | Resource monitoring panel: queue depth, active processes, 24h average time, daily throughput. | P1 |
| F4.7 | Delta audit log: per-task modification history in diff format, accessible from task row menu. | P1 |
| F4.8 | Evidence Workspace: left/right split (Markdown document + evidence cards), scroll-into-view source highlighting with breathing-light animation. | P0 |
| F4.9 | Workspace keyboard shortcuts: J/K card navigation, E edit, Enter confirm, Esc close, Ctrl+Z undo. | P1 |
| F4.10 | Traceability drawer: slide-out panel showing original Markdown paragraph with highlighted source sentence. | P0 |
| F4.11 | Knowledge Base Query tab: HGVS/gene/PMID exact search, AI natural language to SQL mode, advanced filter panel. | P0 |
| F4.12 | Variant detail page: metadata dashboard, evidence matrix grouped by ACMG/ClinGen dimension, quality labels, row comparison mode, traceability drawer. | P0 |
| F4.13 | Export: CSV of evidence matrix, ACMG classification draft generation with disclaimer. | P0 |
| F4.14 | Settings tab: ontology version display and update triggers, extraction prompt template cards, MinerU config, DB connection settings. | P1 |
| F4.15 | Batch processing mode: upload .txt file of PMIDs, silent background processing, results in task board pending-review queue. | P1 |

### Cross-Cutting Requirements

> **Status: MOSTLY DONE** — API layer, async task flow, persistence, and logging are in place. NL-to-SQL endpoint is planned.

| ID | Requirement | Priority |
|---|---|---|
| F5.1 | FastAPI owns `/api/v1/*` API behavior and JWT signing/verification. | P0 |
| F5.2 | Next.js proxies API calls and renders UI; it does not sign or verify JWTs. | P0 |
| F5.3 | Chat sessions, task board, and knowledge base are publicly visible in open-source deployment; audit logs replace permission-based isolation. | P0 |
| F5.4 | Async task creation/status/result flow; SSE streams chat and processing progress via Vercel AI SDK. | P0 |
| F5.5 | Persist chat sessions, delta edits, completed metadata, document outputs, evidence matrix, reports, and feedback. | P0 |
| F5.6 | Cache by PDF/DOCX hash, PMID, DOI, prompt version, parser version, translation version, extraction model versions, and model config. | P1 |
| F5.7 | Use loguru logs under `logs/`. | P0 |
| F5.8 | HPO autocomplete/search API for evidence card phenotype fields. | P0 |
| F5.9 | NL-to-SQL endpoint for knowledge base natural language queries; return generated SQL alongside results for transparency. | P1 |

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Scope Safety | Current scope is evidence extraction and evidence summarization, not final autonomous medical rating. |
| Bi-directional Traceability | Every displayed evidence item must link to original source anchors and translated-text anchors when translated text exists. |
| Reliability | Failed extraction, missing traceability, low confidence, or disagreement between extraction passes must surface as explicit task errors/warnings, not silent success. |
| Security | No hardcoded secrets; environment-variable configuration; upload warning for sensitive clinical data. |
| Performance | Future production target: single-document processing under 5 minutes where model/provider latency allows; dual extraction may require staged progress visibility. |
| Scale | Future production target: 10,000 registered users, 100 concurrent analyses. |
| Storage | Current MVP can use PostgreSQL + local filesystem; object storage is deferred unless re-scoped. |
| LLM | OpenAI-compatible API format for original extraction, translated extraction, translation, VLM, embedding, and rerank roles. |

## 7. Out of Scope for Current MVP Unless Re-Scoped

- Autonomous ACMG/AMP classification or final clinical diagnosis.
- Full ClinGen GDV scoring workflow as a product output.
- External LIMS/EHR integration.
- Automated PHI de-identification or privacy enforcement beyond warnings.
- Production-grade distributed task queue.
- Production Redis/Neo4j/MinIO dependency.
- Full active-learning fine-tuning automation, although dataset capture hooks should be designed.
- Human edits that directly mutate extracted evidence without a reviewed correction workflow.
