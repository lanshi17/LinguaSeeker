# PRD — ACMG Lingua

## 1. Product Positioning

ACMG Lingua is a Multi-Agent infrastructure platform for medical genetics literature automation and structured evidence extraction. The product focuses on the upstream bottlenecks before medical rating: literature acquisition, multimodal document parsing, dual extraction across original and translated text, entity standardization, evidence matrix construction, bilingual source-linked review, and expert feedback capture.

The system provides a high-quality data foundation for downstream clinical interpretation and research computation. It does not perform final autonomous ACMG/GDV medical classification in the current scope.

## 2. Core Problems

| Problem | Product Response |
|---|---|
| Literature collection and reading consume expert time | Cross-database search, batch download, PMID/DOI/keyword workflows, and local PDF/DOCX upload shorten single-gene or variant literature gathering from hours to minutes. |
| Cross-language and multimodal evidence is missed | Use dual extraction: original-language native extraction plus translated-text secondary extraction, then cross-validate, deduplicate, fuse, and preserve bilingual traceability. |
| Evidence collection is fragmented and hard to standardize | Convert unstructured papers into a standardized evidence matrix with normalized genes, variants, diseases, phenotypes, methods, results, and source links. |
| Entity aliases and cross-database lookups are error-prone | Align extracted entities with HGNC, ClinVar, dbSNP, OMIM, HPO, ClinGen, and related public databases through exact, synonym, vector, and Agent-assisted conflict resolution. |
| Expert extraction experience is hard to reuse | Preserve original-text and translated-text absolute source positions, structured feedback, and corrected original-translation-evidence triples for institutional extraction knowledge bases and future model/prompt improvement. |

## 3. Target Users

The personas below are product users, not authorization roles. Current-stage authorization treats authenticated users as one user class.

| User Persona | Technical Level | Primary Use Case |
|---|---|---|
| Clinical Geneticist | No coding | Quickly review bilingual source-linked structured evidence extracted from papers. |
| Bioinformatics Analyst | Low/no coding | Batch collect and normalize variant/gene literature evidence. |
| Researcher | No coding | Mine multilingual literature for phenotypes, experiments, population data, and relationships. |
| Genetic Counselor | No coding | Review bilingual evidence chains and export evidence summary reports. |
| Lab Technician | No coding | Upload local PDF/DOCX documents and verify extracted data. |

## 4. Core User Stories

### US-1: Literature Upload and Processing

As a clinical geneticist, I upload a PDF or DOCX paper describing a functional assay. The system:

1. Extracts metadata before full parsing when possible: DOI, PMID, authors, year, journal.
2. Parses the document with MinerU/PaddleOCR or DOCX parsing into Markdown/HTML plus source anchors and bounding boxes.
3. Separates text, tables, figures, pedigrees, and medically relevant image regions.
4. Extracts target evidence in the original source language.
5. Translates the document or relevant sections to English/Chinese.
6. Extracts target evidence from the translated text a second time.
7. Fuses original-language and translated-text extraction results into one standardized evidence matrix with bilingual source links.

### US-2: Dual Cross-Lingual Evidence Extraction

As a researcher, I process a non-English paper. The system performs original-language extraction first, then translated-text secondary extraction, compares both JSON outputs, flags mismatches, deduplicates equivalent items, and preserves both original and translated snippets for review.

### US-3: Evidence Matrix Construction

As a bioinformatics analyst, I need a machine-readable evidence matrix containing variants, genes, diseases, phenotypes, experimental methods, experimental results, population frequencies, table values, figure-derived evidence, confidence scores, original source anchors, and translated-text anchors.

### US-4: Bilingual Source-Linked Evidence Review

As a reviewer, I click an extracted data point such as a population frequency, HPO phenotype, or biochemical assay result. The UI shows a bilingual side-by-side view: one pane highlights the original source paragraph/table/figure region and the other highlights the translated paragraph/table/figure region.

### US-5: Structured Expert Feedback

As an expert reviewer, I can record structured feedback at the correct failure point:

- Original-language extraction error.
- Translated-text extraction error.
- Translation error.
- Fusion/deduplication mismatch.
- Entity standardization error.
- Missed target phenotype, method, or result.
- Report wording issue.

Feedback is persisted for audit, report export, and future dataset/prompt/model improvement. Current-stage feedback does not mutate extracted evidence automatically unless a reviewed correction workflow is implemented.

### US-6: Evidence Summary Export

As a reviewer, I export a PDF/DOCX evidence summary report containing document metadata, standardized evidence matrix, original snippets, translated snippets, bilingual anchors, confidence scores, fusion status, and review feedback.

## 5. Functional Requirements

### Phase 1: Literature Acquisition and Digitization

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

### Phase 4: Evidence Visualization and Expert Bi-Directional Human-in-the-Loop

| ID | Requirement | Priority |
|---|---|---|
| F4.1 | Display parsed original document, translated document, and standardized evidence matrix in a bilingual split-panel UI. | P0 |
| F4.2 | Synchronize evidence clicks with highlights in original text/table/figure spans and translated text/table/figure spans. | P0 |
| F4.3 | Show confidence scores, extraction agreement status, and fusion uncertainty flags. | P0 |
| F4.4 | Accept structured expert feedback by target type: original extraction, translated extraction, translation, fusion, entity, evidence item, missed evidence, report. | P1 |
| F4.5 | Store corrected original-translation-evidence triples for future dataset/fine-tuning workflows. | P1 |
| F4.6 | Export evidence summary report as PDF. | P0 |
| F4.7 | Export evidence summary report as DOCX. | P1 |
| F4.8 | Stream real-time processing status through WebSocket. | P0 |

### Cross-Cutting Requirements

| ID | Requirement | Priority |
|---|---|---|
| F5.1 | FastAPI owns `/api/v1/*` API behavior and JWT signing/verification. | P0 |
| F5.2 | Next.js proxies API calls and renders UI; it does not sign or verify JWTs. | P0 |
| F5.3 | Registration, email verification, login, and 24h JWT TTL. | P0 |
| F5.4 | Async task creation/status/result flow; running task state may be in-memory for MVP. | P0 |
| F5.5 | Persist completed metadata, original document outputs, translated document outputs, evidence matrix, reports, and feedback. | P0 |
| F5.6 | Cache by PDF/DOCX hash, PMID, DOI, prompt version, parser version, translation version, extraction model versions, and model config. | P1 |
| F5.7 | Use loguru logs under `logs/`. | P0 |

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
