# Feature Specification: Intelligent Parsing Pipeline System

**Feature Branch**: `001-intelligent-parsing-pipeline`
**Created**: 2026-01-30
**Status**: Draft
**Input**: User description: "Core Functional Domains: 1. Intelligent Parsing Pipeline, 2. Three-Screen Interactive Review, 3. Knowledge Graph Aggregation, 4. System Governance"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Document Upload and Automated Evidence Extraction (Priority: P1)

A clinical geneticist needs to extract ACMG evidence codes from a newly published research paper. They upload a PDF document to the system, which automatically parses the document, translates it if needed, and extracts structured evidence with confidence scores. The system highlights low-confidence extractions for manual review.

**Why this priority**: This is the core value proposition - automating the time-consuming manual work of reading papers and extracting ACMG criteria. Without this working, there is no viable product.

**Independent Test**: Can be fully tested by uploading a PDF with known ACMG evidence, verifying that the system returns structured JSON with correct evidence codes and confidence scores ≥0.85, and confirming that low-confidence items are flagged for review.

**Acceptance Scenarios**:

1. **Given** a researcher has a PDF document with ACMG evidence, **When** they upload the PDF via the web interface, **Then** the system validates the file, stores it securely, and begins processing with a visible progress indicator
2. **Given** a document is being processed, **When** the parsing pipeline completes successfully, **Then** the system returns structured evidence with codes (PS1, PM2, BP3, etc.), confidence scores, and source coordinates (page number, bounding box)
3. **Given** the extraction completes, **When** any evidence has confidence <0.85, **Then** those items are marked for human review and appear in a separate "Needs Review" queue
4. **Given** a researcher provides a PMID or DOI, **When** they submit it instead of uploading, **Then** the system fetches the corresponding PDF automatically and processes it

---

### User Story 2 - Interactive Three-Screen Review and Editing (Priority: P2)

After automated extraction, a clinical researcher needs to verify the extracted evidence by reviewing the original source context. They use a unified dashboard showing the original PDF, translated/parsed text, and extracted evidence list side-by-side. Clicking any evidence item auto-scrolls all three views to the exact source location, and they can edit or approve the evidence directly.

**Why this priority**: While automated extraction provides initial value, researchers need confidence in the results before using them for clinical decisions. This verification interface is critical for trust and accuracy, but can be delivered after basic extraction works.

**Independent Test**: Can be tested by loading a previously parsed document, clicking evidence items to verify all three screens synchronize correctly, editing an evidence entry, and confirming changes persist.

**Acceptance Scenarios**:

1. **Given** a document has been parsed with extracted evidence, **When** the user opens the review dashboard, **Then** three synchronized panels display: original PDF (left), translated text (center), and evidence list (right)
2. **Given** the review dashboard is open, **When** the user clicks an evidence item in the right panel, **Then** the PDF and text panels auto-scroll to highlight the exact source coordinates where that evidence was found
3. **Given** the user reviews an evidence item, **When** they edit the evidence code, confidence score, or notes, **Then** changes are saved and reflected immediately in all views
4. **Given** extracted evidence has low confidence, **When** the user views it in the dashboard, **Then** it appears with a visual indicator (color, icon) distinguishing it from high-confidence items

---

### User Story 3 - Knowledge Graph Aggregation and Evidence Stacking (Priority: P3)

As multiple papers are processed, a research coordinator wants to see aggregated evidence across the entire literature corpus. The system builds a knowledge graph connecting variants, phenotypes, and evidence across documents. When reviewing a variant, the system automatically identifies "evidence stacking" - where multiple papers provide supporting evidence that elevates a variant's pathogenicity classification.

**Why this priority**: This provides advanced intelligence beyond single-document analysis, but requires a corpus of documents to be useful. It's valuable for mature usage but not needed for initial adoption.

**Independent Test**: Can be tested by processing multiple documents containing the same variant, verifying that the knowledge graph shows connections between them, and confirming that the system suggests evidence upgrades based on cross-document analysis.

**Acceptance Scenarios**:

1. **Given** multiple documents have been parsed with extracted variants and phenotypes, **When** the system processes a new document, **Then** it automatically merges new entities into the knowledge graph and identifies overlapping evidence
2. **Given** a variant appears in multiple papers with individual PM-level evidence, **When** the user views the aggregated evidence, **Then** the system suggests upgrading to PS-level based on corroborating mentions across papers
3. **Given** the knowledge graph contains connected evidence, **When** the user explores a variant, **Then** they can visualize the graph showing related papers, phenotypes, and evidence pathways with at least 2-hop traversal

---

### User Story 4 - Task Management and System Governance (Priority: P4)

A lab manager needs to monitor the document processing pipeline, prioritize urgent papers, handle failed parsing tasks, and audit the system's extraction decisions. They access a management dashboard showing all parsing queues, task statuses, failure reasons, and complete audit trails of Agent inputs/outputs for debugging low-confidence extractions.

**Why this priority**: Essential for production operations and debugging, but not needed for initial proof-of-concept. Can be added once the core extraction and review workflows are stable.

**Independent Test**: Can be tested by submitting multiple documents, viewing the queue status, manually prioritizing one task, forcing a failure scenario, and verifying the audit trail shows complete Agent decision history.

**Acceptance Scenarios**:

1. **Given** multiple documents are in various processing stages, **When** the manager views the task dashboard, **Then** they see all tasks with status (pending/processing/completed/failed), progress percentage, and elapsed time
2. **Given** an urgent document needs fast-tracked processing, **When** the manager adjusts its priority, **Then** it moves to the front of the queue and processes next
3. **Given** a parsing task fails, **When** the manager views the failure details, **Then** they see the error message, failed stage (Layout/Translation/Evidence/Arbitration), and can retry or escalate
4. **Given** a low-confidence extraction needs investigation, **When** the manager accesses the audit trail, **Then** they see complete Agent inputs (prompts, context), outputs (reasoning, raw extractions), confidence calculations, and all state transitions

---

### Edge Cases

- What happens when a PDF is corrupted, password-protected, or contains only scanned images without extractable text?
- How does the system handle documents in languages other than English and Chinese?
- What happens when MinerU extraction fails or produces malformed output?
- How does the system handle documents with no ACMG evidence found?
- What happens when a user uploads duplicate documents?
- How does the system handle extremely large PDFs (>100MB or >500 pages)?
- What happens when concurrent users edit the same evidence item simultaneously?
- How does the system handle network failures during PMID/DOI fetching?
- What happens when the confidence score is exactly 0.85 (boundary condition)?
- How does the system handle documents with conflicting evidence in the same paper?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept PDF documents via direct upload with validation (file type, size limits, integrity checks)
- **FR-002**: System MUST accept PMID or DOI identifiers and automatically fetch corresponding PDF documents from public repositories
- **FR-003**: System MUST store uploaded documents securely in designated storage with access controls
- **FR-004**: System MUST parse PDF documents to extract layout structure, text content, and embedded images
- **FR-005**: System MUST sanitize and structure extracted content into clean, machine-readable format
- **FR-006**: System MUST generate aligned English and Chinese translations of document text while preserving paragraph structure
- **FR-007**: System MUST extract ACMG evidence criteria (PS1-PS4, PM1-PM6, PP1-PP5, BA1, BS1-BS4, BP1-BP7) from document content
- **FR-008**: System MUST calculate confidence scores (0.0-1.0) for each extracted evidence item
- **FR-009**: System MUST apply confidence threshold of 0.85 - items below threshold MUST be flagged for human review
- **FR-010**: System MUST retain exact source coordinates (page number, bounding box) for every extracted evidence artifact
- **FR-011**: System MUST output structured evidence in queryable format with evidence codes, confidence scores, source coordinates, and supporting text
- **FR-012**: System MUST provide unified review interface displaying original PDF, translated text, and evidence list in synchronized panels
- **FR-013**: System MUST support evidence item editing (codes, scores, notes) with immediate persistence and reflection across all views
- **FR-014**: System MUST synchronize all three viewing panels - clicking evidence auto-scrolls PDF and text to exact source location
- **FR-015**: System MUST build knowledge graph connecting extracted variants, phenotypes, and evidence across all processed documents
- **FR-016**: System MUST identify cross-document evidence patterns and suggest evidence upgrades based on graph topology (minimum 2-hop analysis)
- **FR-017**: System MUST provide task management dashboard showing all document processing tasks with status, progress, and timing
- **FR-018**: System MUST support task prioritization allowing urgent documents to be fast-tracked
- **FR-019**: System MUST provide comprehensive audit trail logging all Agent decisions, inputs, outputs, state transitions, and confidence calculations for minimum 90 days
- **FR-020**: System MUST handle parsing failures gracefully with retry logic (max 3 attempts with exponential backoff)
- **FR-021**: System MUST route tasks exceeding retry limit to Dead Letter Queue for manual intervention
- **FR-022**: System MUST provide real-time progress updates during long-running parsing operations
- **FR-023**: System MUST maintain task failure rate below 1% under normal operating conditions
- **FR-024**: System MUST distinguish high-confidence (≥0.85) from low-confidence (<0.85) evidence with visual indicators

### Key Entities

- **Document**: A biomedical research paper uploaded or fetched by PMID/DOI. Contains metadata (title, authors, journal, publication date), original PDF content, processing status, and relationships to extracted evidence.

- **Evidence Item**: A single ACMG criterion extracted from a document. Contains evidence code (e.g., PS1, PM2), confidence score (0.0-1.0), source coordinates (page number, bounding box), supporting text excerpt, human review status, and link back to source document.

- **Translation Pair**: Aligned English and Chinese text segments from a document. Maintains paragraph-level correspondence and links to source document coordinates.

- **Variant**: A genetic variant mentioned in documents. Contains variant notation (HGVS format typically), associated evidence items, relationships to phenotypes, and position in knowledge graph.

- **Phenotype**: A clinical phenotype associated with variants. Contains phenotype description, severity indicators, relationships to variants, and position in knowledge graph.

- **Parsing Task**: An asynchronous job processing a document through the pipeline. Contains task ID, document reference, current stage (ingestion/decomposition/layout/translation/evidence/arbitration), progress percentage, status (pending/processing/completed/failed), retry count, and timestamps.

- **Audit Log Entry**: An immutable record of Agent decision-making. Contains timestamp, task ID, Agent type (Layout/Translation/Evidence/Arbitration), input prompt, output reasoning, confidence calculation details, state transitions, latency metrics, and failure reasons if applicable.

- **Knowledge Graph Node**: A node in the cross-document graph representing a variant, phenotype, or evidence cluster. Contains entity type, entity attributes, edges to related nodes, and aggregated evidence strength from connected documents.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Researchers can upload a document and receive structured ACMG evidence extraction results without manual coding of the paper
- **SC-002**: System extracts evidence with ≥85% confidence for at least 70% of evidence items in typical biomedical papers
- **SC-003**: Document processing completes within 5 minutes for papers under 20 pages and 10 minutes for papers under 50 pages
- **SC-004**: Users can locate the source of any extracted evidence in the original PDF within 3 clicks
- **SC-005**: Task failure rate remains below 1% across all document processing operations
- **SC-006**: When viewing aggregated evidence for a variant, users can identify supporting evidence from at least 3 connected documents within 2 minutes
- **SC-007**: Researchers can monitor the status of their document processing tasks in real-time with progress updates at least every 30 seconds
- **SC-008**: System administrators can identify and debug low-confidence extractions using audit trails within 10 minutes
- **SC-009**: Edited evidence changes persist immediately and remain consistent across all viewing interfaces
- **SC-010**: Cross-document evidence stacking correctly identifies at least 80% of variants appearing in multiple papers within the corpus

### Assumptions

- Documents are primarily in English or Chinese (other languages trigger a fallback or unsupported language warning)
- ACMG evidence criteria codes follow standard 2015 guidelines (PS1-PS4, PM1-PM6, PP1-PP5, BA1, BS1-BS4, BP1-BP7)
- Users have sufficient training to understand ACMG terminology and evidence classification
- PDFs are text-based or contain OCR-readable content (pure image scans without text layer may have reduced accuracy)
- Document upload size limit is set at 100MB per file (configurable by administrators)
- PMID/DOI fetching relies on public repositories (PubMed, DOI.org) being accessible
- Concurrent editing by multiple users on the same evidence item uses last-write-wins conflict resolution
- Knowledge graph analysis requires at least 10 documents in the corpus to provide meaningful evidence stacking
- Confidence score calculation uses consistent scoring model across all Agent stages
- Real-time progress updates use WebSocket connections with automatic reconnection on failure
