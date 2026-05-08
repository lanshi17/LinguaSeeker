# APP_FLOW — ACMG Lingua Application Flow

## 1. High-Level Pipeline

```
User Input (PDF / PMID / DOI / keyword-selected candidate)
        │
        ▼
┌─────────────────────────────┐
│  Phase 1: Acquisition       │  Literature fetch / PDF upload
│  & Digitization             │  → OCR (MinerU primary)
│                             │  → Markdown/HTML + source anchors + bbox JSON
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Phase 2: Translation       │  Non-EN → EN (5-stage pipeline)
│  & Evidence Extraction      │  → Structured JSON extraction
│                             │  → Confidence scores + source spans
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Phase 3: Entity            │  Gene → HGNC
│  Standardization            │  Disease → OMIM/MONDO/HPO
│  & Knowledge Alignment      │  Variant → ClinVar/dbSNP
│                             │  Frequency → gnomAD
│                             │  Predictions → CADD/REVEL/SpliceAI
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│  Phase 4: Dual-Track Reasoning              │
│  ┌──────────────────┐  ┌──────────────────┐ │
│  │ Track A: ACMG/AMP│  │ Track B: GDV     │ │
│  │ Multi-agent      │  │ Multi-agent      │ │
│  │ reasoning        │  │ reasoning        │ │
│  └────────┬─────────┘  └────────┬─────────┘ │
│           │                     │           │
│           ▼                     ▼           │
│  ┌──────────────────────────────────────┐   │
│  │ Arbitration (strongest model)        │   │
│  │ → Rule matrix check → Retry if needed│   │
│  └──────────────────────────────────────┘   │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────┐
│  Phase 5: Visualization     │  MinerU MD/HTML evidence review
│  & Human-in-the-Loop        │  Source anchors / bbox-backed spans
│                             │  Review comments → draft PDF export
└─────────────────────────────┘
```

All classifications are expert-review drafts. Rule matrices are authoritative when they conflict with LLM reasoning.

## 2. Phase 1: Literature Acquisition & Digitization

### 2.1 Task Creation and Input Routing

`POST /api/v1/tasks` is the authoritative analysis creation endpoint.

- PDF upload uses `multipart/form-data` on the same route.
- PMID, DOI, and keyword-selected candidate flows use JSON on the same route.
- `document_id` is internal and is not supplied by the frontend during task creation.
- Deployed environments should require login for task creation; local development may allow unrestricted creation.

```
User Input
    ├── PDF Upload ───────────────► POST /api/v1/tasks (multipart) ─► OCR
    ├── PMID ─────────────────────► POST /api/v1/tasks (JSON) ──────► Fetch PDF → OCR
    ├── DOI ──────────────────────► POST /api/v1/tasks (JSON) ──────► Fetch PDF → OCR
    └── Keyword
          │
          ├── Search first: GET/POST /api/v1/literature/search
          │
          └── User selects analyzable candidate
                └── POST /api/v1/tasks with selected_candidate ────► Fetch PDF → OCR
```

For keyword-created tasks, `selected_candidate` must include enough information to reproduce the selected source:

- `provider`
- `title`
- `canonical_id` when available (`doi`, `pmid`, or `url`)
- `selected_download_url`

A keyword candidate must have at least one PDF download URL before analysis task creation.

### 2.2 OCR Pipeline

```
PDF Input
    │
    ▼
MinerU API (primary)
    ├── Success → JSON with bbox + rendered Markdown/HTML
    │               │
    │               ▼
    │         Parse source anchors and bbox coordinates
    │         Chunk by paragraph (max_tokens)
    │               │
    │               ▼
    │         Output: rendered document + source_anchor/bbox map
    │
    └── Failure
            │
            ▼
        PaddleOCR VLM fallback
            ├── Success with source anchors/bbox-backed spans → continue
            ├── Success without source anchors/bbox-backed spans → fail task
            └── Failure → fail task
```

Evidence chain extraction requires traceable source anchors or bbox-backed spans. OCR output without traceability cannot enter the evidence chain.

### 2.3 Text Chunking Strategy

1. Split markdown by double newline → paragraphs
2. For each paragraph, estimate tokens (ascii/4 + non-ascii chars)
3. If paragraph > max_tokens, split by sentences
4. If sentence > max_tokens, split by character chunk
5. Merge adjacent chunks that fit within max_tokens

### 2.4 Metadata Extraction

Before full OCR, extract:

- DOI, PMID, authors, year, journal
- Used for: source attribution, evidence weighting, deduplication

### 2.5 Cache Reuse

Every analysis request creates a new `task_id`, even when previous outputs are reused.

Cache reuse may reuse all valid pipeline outputs:

- Acquisition result
- OCR/document rendering
- Translation
- Extraction
- Standardization
- Reasoning/arbitration output
- Export-ready final result data

Cache keys include PDF hash and PMID/DOI where available. Cache entries are invalidated by rule, prompt, or model version changes. The frontend receives normal WebSocket stage updates and does not receive a cache-hit marker.

## 3. Phase 2: Translation & Evidence Extraction

### 3.1 Translation Pipeline (5 Stages)

```
Source Markdown/HTML (any language)
    │
    ▼
Stage 1: Terminology Planning
    → Extract bilingual term map
    → Preserve HGVS, gene symbols, accession IDs exactly
    │
    ▼
Stage 2: Structure Planning
    → Re-express logical structure for English rendering
    → Restore omitted subjects, split long clauses
    │
    ▼
Stage 3: Draft Translation
    → Translate segment by segment (max_tokens aware)
    → Apply terminology map and structure plan
    │
    ▼
Stage 4: Polish
    → Improve fluency for academic English
    → Preserve biomedical literals
    │
    ▼
Stage 5: Review
    → Compare source vs translation
    → Flag ambiguity, dropped content, terminology drift
    │
    ▼
Output: translated_markdown/html (English)
```

### 3.2 Evidence Extraction

```
Translated English Markdown/HTML + source anchor map
    │
    ▼
LLM Extraction (structured prompt with full field schema)
    │
    ├── Variant info (Gene, HGVS, Transcript, Genomic coords)
    ├── Disease info (Name, MONDO ID)
    ├── Population data (gnomAD frequency)
    ├── In silico predictions (Conservation, Protein, Splicing)
    ├── Genetic data (Case-control, Segregation)
    ├── Functional data (Experiments array with full detail)
    ├── Gene context (Disease mechanism, GDV validity, Dosage)
    ├── GDV evidence (Case-level, Segregation, Case-control, Experimental)
    └── Evidence chain (RuleID, Level, Source field, PMID, source_anchor, bbox_span)
    │
    ▼
Output: ExtractedEvidence JSON + field_confidence_scores
```

### 3.3 Extraction Prompt Design

Based on old version patterns:

- `QUESTION_TEMPLATE_3`: full structured extraction (variants, disease, experiment method)
- `QUESTION_TEMPLATE_5`: ACMG PS3/BS3 flowchart-based evaluation
- `QUESTION_TEMPLATE_6`: quick variant detection from paragraphs

New prompts combine these into comprehensive extraction covering ACMG and GDV fields. `knowledges/` files are reference material, not the executable rule-matrix source.

## 4. Phase 3: Entity Standardization

### 4.1 Matching Pipeline

```
Extracted JSON Fields
    │
    ├── Gene.Symbol ──────────────► HGNC lookup (exact → fuzzy)
    ├── Disease.Name ─────────────► OMIM + MONDO + HPO (exact → vector)
    ├── Disease.MONDO_ID ─────────► MONDO validation
    ├── Variant.HGVS ────────────► ClinVar + dbSNP (exact → fuzzy)
    ├── PopulationData.Source ────► gnomAD API
    ├── InSilicoData ─────────────► CADD/REVEL/SpliceAI lookup
    │
    ▼
For each match:
    ├── Exact match → auto-accept
    ├── Fuzzy match (vector similarity) → accept if > threshold
    ├── Multiple candidates → conflict resolution agent
    └── No match → keep original, flag as unstandardized
    │
    ▼
Output: original_value + standardized_value + match_status + source_db
```

### 4.2 Local Database Strategy

Pre-download and index locally:

- HGNC gene symbols → PostgreSQL table
- OMIM gene-disease pairs → PostgreSQL table
- MONDO ontology → PostgreSQL table
- HPO phenotype terms → PostgreSQL table
- ClinVar variant annotations → PostgreSQL table
- dbSNP rsID mappings → PostgreSQL table
- gnomAD frequency data → PostgreSQL table (key variants)
- CADD/REVEL/SpliceAI scores → PostgreSQL table

Embedding vectors are stored in pgvector for fuzzy matching.

## 5. Phase 4: Dual-Track Reasoning

### 5.1 ACMG/AMP Track

```
Standardized Evidence JSON
    │
    ▼
Agent: PVS1 Evaluator (Null variants)
Agent: PS1-4 Evaluator (Strong pathogenic)
Agent: PM1-6 Evaluator (Moderate pathogenic)
Agent: PP1-5 Evaluator (Supporting pathogenic)
Agent: BA1 Evaluator (Stand-alone benign)
Agent: BS1-4 Evaluator (Strong benign)
Agent: BP1-6 Evaluator (Supporting benign)
    │
    ▼
Each agent outputs:
    - Rule triggered (e.g., PS3)
    - Evidence strength (Supporting/Moderate/Strong/Very Strong)
    - Confidence score
    - Supporting data from extracted fields
    - Source PMID + source_anchor/bbox_span
    │
    ▼
Aggregator: Combine triggered rules → ACMG draft classification
```

### 5.2 GDV Track

GDV is a draft assessment based on the provided literature plus supplemental retrieval across configured literature providers.

```
Standardized Evidence JSON + supplemental retrieval results
    │
    ▼
Agent: Case-Level Genetic Evidence
    → Proband count, variant category, de novo status
Agent: Segregation Evidence
    → LOD score, family count, sequencing method
Agent: Case-Control Evidence
    → Sample size, matching, statistical significance
Agent: Experimental Evidence
    → Biochemical function, protein interaction, expression
    → Functional alteration (patient cells, non-patient cells)
    → Models & rescue (type, species, phenotype replicated)
    │
    ▼
Score Calculator:
    Genetic evidence total + Experimental evidence total
    + replicated-over-time check
    │
    ▼
GDV Draft Classification:
    Definitive / Strong / Moderate / Limited /
    No Known Disease Validity / Disputed / Refuted
```

### 5.3 Arbitration and Gating Flow

```
ACMG preliminary result + GDV preliminary result
    │
    ▼
Arbitration Agent (ArbitrationConfig — strongest reasoning model)
    │
    ├── Review evidence chains
    ├── Check internal consistency
    ├── Check rule-matrix compliance
    ├── Produce confidence score + targeted feedback
    │
    ▼
Decision:
    ├── Rule matrix conflicts with LLM output → rule matrix wins
    ├── Confidence ≥ threshold → approve draft result
    ├── Confidence < threshold → retry disputed parts only
    │       │
    │       ▼
    │   Re-evaluate only flagged evidence items
    │   Max retries: configurable (default 3)
    │
    └── Apply GDV gating
            ├── No Known / Disputed / Refuted → block ACMG tier display
            └── Limited → show ACMG tier with warning
```

When GDV blocks ACMG display, the stored result may still retain internal ACMG reasoning artifacts, but the user-facing result and export show GDV-only content plus the block reason.

### 5.4 Optional Neo4j Background Knowledge (P1/Future)

Neo4j is not required for the current MVP. When enabled later, it may provide:

- Gene-disease associations
- Related variants in the same gene
- Multi-document evidence aggregation
- Existing ClinGen gene-disease validity classifications
- Dosage sensitivity scores

## 6. Phase 5: Visualization & Human-in-the-Loop

### 6.1 Processing Status (WebSocket)

The frontend connects to `WS /api/v1/tasks/{task_id}/ws` after task creation. WebSocket messages are for processing status; final results are fetched through `GET /api/v1/tasks/{task_id}/result`.

```
Frontend ←── WS /api/v1/tasks/{task_id}/ws ──→ Backend

Messages:
    { "type": "status", "step": "acquisition", "progress": 20 }
    { "type": "status", "step": "ocr", "progress": 50 }
    { "type": "status", "step": "translation", "progress": 30 }
    { "type": "status", "step": "extraction", "progress": 80 }
    { "type": "status", "step": "reasoning", "progress": 60 }
    { "type": "status", "step": "arbitration", "progress": 90 }
    { "type": "complete", "task_id": "xxx" }
    { "type": "error", "step": "ocr", "message": "Traceable OCR failed" }
```

Running tasks are in-memory and may disappear on service restart. Completed task metadata, document/OCR output, final results, and review comments persist.

### 6.2 Evidence Display UI

```
┌──────────────────────────────────────────────────────────────┐
│  Left Panel: Document View          │  Right Panel: Evidence │
│  MinerU-rendered MD/HTML            │                        │
│                                     │  Variant: BRCA1        │
│  [Highlighted source span linked    │  HGVS: NM_...c.5266dup │
│   by source_anchor/bbox_span]       │  Disease: Breast Ca    │
│                                     │                        │
│  ┌─────────────────────────────┐    │  ┌──────────────────┐  │
│  │ Source paragraph with       │    │  │ Evidence Chain   │  │
│  │ highlighted evidence span   │    │  │ PS3: Moderate    │  │
│  └─────────────────────────────┘    │  │ Confidence: 0.85 │  │
│                                     │  │ PMID: 12345678   │  │
│                                     │  └──────────────────┘  │
│                                     │                        │
│                                     │  ┌──────────────────┐  │
│                                     │  │ ACMG draft:      │  │
│                                     │  │ shown only if    │  │
│                                     │  │ GDV does not     │  │
│                                     │  │ block display    │  │
│                                     │  │                  │  │
│                                     │  │ GDV draft:       │  │
│                                     │  │ Moderate         │  │
│                                     │  └──────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 6.3 Human Review Flow

```
System shows draft evidence chain and draft classification
    │
    ▼
User reviews source-linked evidence
    │
    ├── Add review comment/rationale (login required)
    │       │
    │       ▼
    │   Save comment → Persist comment → Include in export
    │
    └── Export draft report PDF
```

Users do not change structured classification results, evidence strengths, or ACMG/GDV tiers in the current stage.

### 6.4 PDF Export Content

1. Title: Variant Classification Draft Report
2. Variant summary (Gene, HGVS, Disease)
3. GDV draft classification + rationale
4. ACMG draft classification + rationale, only when GDV does not block display
5. GDV block reason when ACMG display is blocked
6. Evidence chain table (RuleID, Strength, Source, PMID, source anchor)
7. Functional experiment details
8. Population frequency data
9. Computational predictions
10. Review comments and rationale, if any
11. Appendix: source text snippets with translations

Multi-variant reports may include normal ACMG sections for unblocked variants and GDV/block-reason-only sections for blocked variants.

## 7. API Flow Summary

```
Frontend (Next.js)
    │
    ├── /api/v1/* proxy via next.config.ts
    │
    ▼
Backend (FastAPI)
    ├── POST /api/v1/auth/register              Register account
    ├── POST /api/v1/auth/verify-email          Verify email
    ├── POST /api/v1/auth/login                 Login, return 24h JWT
    ├── GET  /api/v1/literature/search          Keyword/provider search
    ├── POST /api/v1/tasks                      Create analysis task
    ├── GET  /api/v1/tasks/{task_id}            Get task metadata/status
    ├── WS   /api/v1/tasks/{task_id}/ws         Processing status stream
    ├── GET  /api/v1/tasks/{task_id}/result     Get final result
    ├── POST /api/v1/tasks/{task_id}/comments   Add review comment (login required)
    ├── POST /api/v1/tasks/{task_id}/export     Generate draft PDF report
    ├── GET  /api/v1/evidence                   Query evidence chains (P1)
    ├── GET  /api/v1/graph/*                    Neo4j graph queries (P1/future)
    └── GET  /api/v1/health                     Health check
```

Task and result reads are public. Review comments require login. FastAPI signs and verifies JWTs; Next.js only proxies API calls.
