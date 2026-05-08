# PRD — ACMG Lingua

## 1. Product Overview

ACMG Lingua is a web-based platform that automates ACMG variant classification and ClinGen Gene-Disease Validity (GDV) assessment. It ingests scientific literature (via PDF upload, PMID/DOI, or keyword search), translates non-English documents, extracts structured evidence items, standardizes entities against public databases, and produces classification drafts through multi-agent reasoning with expert arbitration.

## 2. Target Users

The roles below are user personas, not authorization roles. Current-stage access control treats users as a single logged-in user class.

| User Persona | Technical Level | Primary Use Case |
|--------------|----------------|-----------------|
| Clinical Geneticist | No coding | Upload functional assay papers, get PS3/BS3 evidence strength drafts |
| Researcher | No coding | Batch-process literature for variant-disease evidence drafts |
| Genetic Counselor | No coding | Query existing evidence chains for review support |
| Lab Technician | No coding | Upload PDFs and review extracted evidence drafts |

## 3. Core User Stories

### US-1: Literature Upload & Processing
As a clinical geneticist, I upload a PDF paper describing a functional assay for BRCA1 c.5266dup. The system automatically:
1. Parses the PDF (OCR if scanned)
2. Translates to English (if non-English)
3. Extracts structured evidence items (variant, disease, experiment details, controls, thresholds)
4. Standardizes gene/disease/variant names against HGNC, ClinVar, OMIM
5. Shows me a draft classification with full evidence chain

### US-2: Multi-Variant Analysis
As a researcher, I upload a paper containing 5 variants. The system processes all variants and produces separate evidence chains and classifications for each.

### US-3: Evidence Review & Feedback
As a genetic counselor, I review the system's draft classification. I can:
- See the MinerU-rendered MD/HTML document with evidence source anchors
- Add review comments and rationale without changing structured classification results
- Export a draft report as PDF

### US-4: Database Query
As a lab technician, I input "BRCA1 c.5266dup" or a gene-disease pair. The system returns existing evidence chains and current classification from the database.

### US-5: GDV Assessment
As a researcher, I input a gene-disease pair. The system uses the provided literature plus supplemental retrieval across configured literature providers, extracts genetic evidence (case-level, segregation, case-control) and experimental evidence (function, alteration, models/rescue), and produces a ClinGen GDV draft classification.

## 4. Functional Requirements

### Phase 1: Literature Acquisition & Digitization

| ID | Requirement | Priority |
|----|-------------|----------|
| F1.1 | Accept PDF upload (max 50MB, including scanned PDFs) | P0 |
| F1.2 | Accept PMID/DOI input for literature retrieval | P0 |
| F1.3 | Accept keyword search across multiple providers | P1 |
| F1.4 | OCR via MinerU API (primary) with PaddleOCR VLM fallback | P0 |
| F1.5 | Extract metadata (DOI, PMID, authors, year, journal) before full OCR | P1 |
| F1.6 | Parse tables to JSON/CSV format | P2 |
| F1.7 | Generate image descriptions via VLM | P2 |
| F1.8 | Chunk text by paragraph with max_tokens limit | P0 |
| F1.9 | Return MinerU source anchors / Bounding Box coordinates; no-bbox OCR output fails the task | P0 |
| F1.10 | Support multi-language sources: CN, JP, DE, RU, KR, EN | P0 |

### Phase 2: Translation & Evidence Extraction

| ID | Requirement | Priority |
|----|-------------|----------|
| F2.1 | Translate non-English documents to English before extraction | P0 |
| F2.2 | 5-stage translation pipeline: terminology → structure → draft → polish → review | P0 |
| F2.3 | Preserve medical terminology accuracy (HGVS, gene symbols, protein names) | P0 |
| F2.4 | Extract all evidence fields per GDV v12 + ACMG 2019 schema | P0 |
| F2.5 | Structured JSON output with confidence scores per field | P0 |
| F2.6 | Traceability: link each evidence item to MinerU source anchor / bbox-backed document span | P1 |

### Phase 3: Entity Standardization

| ID | Requirement | Priority |
|----|-------------|----------|
| F3.1 | Match gene symbols against HGNC | P0 |
| F3.2 | Match disease names against OMIM, MONDO, HPO | P0 |
| F3.3 | Match variants against ClinVar, dbSNP | P0 |
| F3.4 | Query population frequency from gnomAD | P0 |
| F3.5 | Query computational predictions from CADD, REVEL, SpliceAI | P1 |
| F3.6 | Preserve original values alongside standardized values | P0 |
| F3.7 | Vector-based fuzzy matching using pgvector (Qwen3-Embedding) | P1 |
| F3.8 | Conflict resolution via heuristic + agent for ambiguous matches | P1 |

### Phase 4: Dual-Track Reasoning & Arbitration

| ID | Requirement | Priority |
|----|-------------|----------|
| F4.1 | ACMG/AMP classification (Pathogenic → Benign, 5-tier) | P0 |
| F4.2 | ClinGen GDV draft classification (Definitive → No Known Disease Validity) | P0 |
| F4.3 | Multi-agent architecture: separate agents per evidence category | P0 |
| F4.4 | Arbitration via stronger reasoning model (ArbitrationConfig); rule matrices remain authoritative when LLM output conflicts | P0 |
| F4.5 | Retry mechanism: re-evaluate disputed parts only | P0 |
| F4.6 | Confidence scoring per evidence item | P0 |
| F4.7 | GDV gating: No Known / Disputed / Refuted blocks ACMG tier display; Limited is shown as a warning | P0 |
| F4.8 | Query Neo4j gene-disease graph for background knowledge | P1 |
| F4.9 | ACMG rules: 2015 guidelines + 2019 updates + latest refinements | P0 |
| F4.10 | GDV rules: ClinGen Gene-Disease Validity framework v12 | P0 |

### Phase 5: Visualization & Human-in-the-Loop

| ID | Requirement | Priority |
|----|-------------|----------|
| F5.1 | Display translated MinerU MD/HTML document alongside evidence chain | P0 |
| F5.2 | Highlight source text linked to evidence items through source anchors / bbox-backed spans | P1 |
| F5.3 | Allow user to add review comments and rationale without changing structured classification output | P0 |
| F5.4 | Export draft report as PDF | P0 |
| F5.5 | Real-time processing status via WebSocket | P0 |
| F5.6 | Multi-variant view within single session | P0 |

### Cross-Cutting

| ID | Requirement | Priority |
|----|-------------|----------|
| F6.1 | JWT authentication via `/api/v1/auth/*`; FastAPI signs/verifies tokens and Next.js proxies | P0 |
| F6.2 | Public email/password registration, required email verification, login, 24h JWT TTL; password reset deferred | P0 |
| F6.3 | Async task creation/status/result flow via `/api/v1/tasks`; running tasks are in-memory, completed metadata, document/OCR output, results, and comments persist | P0 |
| F6.4 | Evidence graph query and statistics | P1 |
| F6.5 | Health check endpoint | P0 |
| F6.6 | File hash / PMID / DOI cache reuse with version invalidation | P1 |

## 5. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Scale | Future production target: 10,000 registered users, 100 concurrent |
| Performance | Future production target: single document processing < 5 minutes (PDF → classification draft) |
| Availability | Future production target: 99.5% uptime for cloud deployment |
| Security | JWT auth, required email verification, no hardcoded secrets, .env-based config; PHI/privacy handling is user responsibility with upload warnings |
| Storage | Local file system (MinIO deferred) |
| LLM | Custom OpenAI-compatible API format |
| Database | PostgreSQL 16 + pgvector for current MVP; Neo4j and Redis are P1/future |

## 6. Out of Scope (Current Phase)

- Celery task queue (deferred; running tasks are in-memory and may disappear on restart)
- MinIO object storage (deferred, using local filesystem)
- Redis and Neo4j production integrations (P1/future)
- Password reset and refresh-token flows
- Chat Assistant beyond status-oriented UX (P1/future)
- DOCX export (PDF only)
- Model fine-tuning / active learning flywheel
- Advanced table/chart structured extraction (basic only)
- Automated PHI de-identification or privacy enforcement
- LIMS or external clinical system integration
