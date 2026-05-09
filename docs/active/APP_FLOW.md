# APP_FLOW — ACMG Lingua Application Flow

## 1. End-to-End Business Flow

```text
User Input (PMID / DOI / keyword / local PDF / local DOCX)
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Literature Acquisition & Digitization              │
│ - Literature Agent fetches PMID/DOI/keyword-selected files   │
│ - Upload workflow accepts local PDF/DOCX                     │
│ - Metadata extraction before full parsing                    │
│ - MinerU/PaddleOCR converts PDF to MD/HTML                   │
│ - DOCX parser extracts text, tables, images                  │
│ - Layout analysis extracts tables, figures, bbox anchors     │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Cross-Lingual Evidence Extraction                  │
│ - Multilingual-native coarse filtering                       │
│ - Fine-grained source-language evidence extraction           │
│ - Structured translation and denoising after extraction      │
│ - Target evidence: phenotype, methods, results, frequency    │
│ - Evidence items retain page/line/source_anchor/bbox spans   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Entity Standardization & Knowledge Alignment        │
│ - HGNC / ClinVar / dbSNP / OMIM / HPO / ClinGen matching     │
│ - Exact match → synonym → vector fuzzy → conflict resolver   │
│ - Store standardized evidence matrix                         │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Visualization & Expert Loop                         │
│ - Split-panel source/evidence review                         │
│ - Click evidence → highlight original text/table/figure      │
│ - Structured expert feedback and correction capture          │
│ - PDF/DOCX evidence summary report export                    │
│ - Curated extraction dataset for future prompt/model tuning  │
└─────────────────────────────────────────────────────────────┘
```

ACMG Lingua's current product scope ends at structured evidence extraction, standardization, review, and evidence summary export. Downstream medical rating can consume the evidence matrix, but final ACMG/GDV classification is out of current MVP scope.

## 2. Phase 1: Literature Acquisition and Digitization

### 2.1 Input Routing

`POST /api/v1/tasks` is the authoritative task creation endpoint.

```text
User Input
    ├── Local PDF ─────────────► POST /api/v1/tasks multipart ─► Document parsing
    ├── Local DOCX ────────────► POST /api/v1/tasks multipart ─► Document parsing
    ├── PMID ─────────────────► POST /api/v1/tasks JSON ───────► Fetch literature
    ├── DOI ──────────────────► POST /api/v1/tasks JSON ───────► Fetch literature
    └── Keyword
          │
          ├── Search first: GET /api/v1/literature/search
          │
          └── User selects analyzable candidate
                └── POST /api/v1/tasks with selected_candidate
```

For keyword-created tasks, `selected_candidate` must include:

- `provider`
- `title`
- `canonical_id` when available (`doi`, `pmid`, or URL)
- `selected_download_url`

A keyword candidate must expose a downloadable document URL before it can enter analysis.

### 2.2 Document Parsing Pipeline

```text
PDF/DOCX Input
    │
    ├── Metadata extraction
    │     └── DOI, PMID, authors, year, journal, candidate source quality
    │
    ├── PDF path
    │     ├── MinerU primary parse
    │     └── PaddleOCR fallback when MinerU fails
    │
    ├── DOCX path
    │     └── Structured text/table/image extraction
    │
    ├── Layout analysis
    │     ├── Markdown/HTML text
    │     ├── Table JSON/CSV
    │     ├── Figure/pedigree/plot image regions
    │     └── VLM descriptions for medically relevant images
    │
    └── Traceability gate
          ├── page + section/line + source_anchor + bbox available → continue
          └── no source anchors/bbox-backed spans → fail task clearly
```

Evidence extraction requires traceable source anchors or bbox-backed spans. Output that cannot support source-linked review cannot enter the standardized evidence matrix.

### 2.3 Chunking Strategy

1. Split rendered document by logical sections when headings are available: abstract, methods, results, discussion, tables, figures, supplementary material.
2. Split each section by paragraph, table row, or figure panel.
3. Estimate token size for each chunk.
4. Split oversized paragraphs by sentence; split oversized sentences by character window.
5. Merge adjacent chunks within `max_tokens` while preserving source span mapping.

### 2.4 Cache Reuse

Every request creates a new `task_id`, even when previous outputs are reused.

Cache keys include:

- PDF/DOCX SHA256 hash.
- PMID.
- DOI.
- Parser version.
- Prompt version.
- Model/version configuration.

The frontend receives normal processing-stage updates and does not need a cache-hit marker.

## 3. Phase 2: Cross-Lingual Processing and Evidence Extraction

### 3.1 Why Extraction Comes Before Translation

Medical genetics evidence depends on exact strings and context: HGVS variants, gene names, HPO phenotypes, family segregation, assay thresholds, figure labels, and table values. Translating full documents first can distort these details. ACMG Lingua therefore uses:

```text
Source-language document chunk
    │
    ▼
Coarse evidence filtering
    │   identifies chunks likely containing phenotype, variant, segregation,
    │   functional assay, population frequency, method, or result evidence
    ▼
Fine-grained multilingual-native extraction
    │   extracts source-language structured JSON and source anchors
    ▼
Structured translation and denoising
    │   translates extracted fields/snippets, not the whole raw document first
    ▼
Standard Evidence Item
    │   original_value + translated_value + source_span + confidence
```

Full translated renderings may be generated for reviewer convenience, but extraction-critical data must be anchored to source-language extraction.

### 3.2 Target Evidence Types

```text
Evidence Extraction Agent Output
    ├── Document metadata
    │     └── DOI, PMID, authors, year, journal, language
    ├── Variant data
    │     └── gene, HGVS, transcript, genomic coordinates, original mention
    ├── Disease and phenotype data
    │     └── disease name, HPO terms, clinical descriptors
    ├── Functional/experimental data
    │     └── assay method, material, controls, thresholds, quantitative result, conclusion
    ├── Genetic data
    │     └── segregation, de novo, case-control, proband count when present
    ├── Population data
    │     └── frequency, ancestry subset, source
    ├── Computational data
    │     └── conservation, protein predictors, splicing predictors when reported
    └── Traceability
          └── page, line/section, source_anchor, bbox, snippet, table/figure ID
```

Each evidence field has a confidence score. Missing or ambiguous source anchoring is a blocking quality issue for evidence display.

## 4. Phase 3: Entity Standardization and Knowledge Alignment

```text
Extracted Evidence JSON
    │
    ├── Gene mentions ─────────────► HGNC exact/synonym match
    ├── Disease mentions ──────────► OMIM / MONDO / HPO match
    ├── Phenotype mentions ────────► HPO match
    ├── Variant mentions ─────────► HGVS normalization → ClinVar / dbSNP
    ├── Population frequency ─────► gnomAD lookup when available
    ├── Gene-disease context ─────► ClinGen / OMIM support context when available
    │
    ▼
Match decision
    ├── Exact match → accept
    ├── Synonym match → accept with source
    ├── Single high-similarity vector match → accept with score
    ├── Multiple plausible candidates → conflict resolver Agent
    └── No reliable match → keep original and flag unstandardized
    │
    ▼
Standard Evidence Matrix
    └── original_value + standardized_value + source_db + match_status + rationale
```

Ambiguous aliases are resolved using article context, co-mentioned disease, variant coordinates, organism/species, and surrounding biomedical terms.

## 5. Phase 4: Evidence Visualization and Expert Loop

### 5.1 Processing Status

The frontend connects to `WS /api/v1/tasks/{task_id}/ws` after task creation. Final results are fetched with `GET /api/v1/tasks/{task_id}/result`.

```json
{ "type": "status", "step": "acquisition", "progress": 20 }
{ "type": "status", "step": "parsing", "progress": 50 }
{ "type": "status", "step": "native_extraction", "progress": 65 }
{ "type": "status", "step": "structured_translation", "progress": 72 }
{ "type": "status", "step": "standardization", "progress": 85 }
{ "type": "status", "step": "report_preparation", "progress": 95 }
{ "type": "complete", "task_id": "xxx" }
{ "type": "error", "step": "parsing", "message": "Traceable parsing failed" }
```

### 5.2 Evidence Review UI

```text
┌──────────────────────────────────────────────────────────────────┐
│ Topbar: task, status, export                                     │
├────────────────────────────────┬─────────────────────────────────┤
│ Document Panel                 │ Evidence Panel                  │
│                                │                                 │
│ MinerU/PaddleOCR/DOCX MD/HTML  │ Standardized evidence matrix    │
│ Tables rendered as table views │ Evidence items by category      │
│ Figures with VLM descriptions  │ Original + translated snippets  │
│                                │ Confidence and match status     │
│ Highlighted source span        │ Structured expert feedback      │
│ linked by source_anchor/bbox   │ Export actions                  │
└────────────────────────────────┴─────────────────────────────────┘
```

Clicking an evidence item scrolls the source document to the exact highlighted source span. Table and figure evidence should highlight the row/cell/region when available.

### 5.3 Human Feedback Targets

Expert feedback is structured by target type:

- `translation`: translated structured field/snippet is wrong.
- `entity`: standardized gene/disease/variant/phenotype mapping is wrong.
- `evidence_item`: extracted evidence is missing, wrong, or over-interpreted.
- `missed_evidence`: important phenotype, method, or result was not extracted.
- `report`: evidence summary wording/commentary issue.

Feedback is persisted for audit and future dataset construction. Current-stage feedback does not directly mutate evidence rows unless a reviewed correction workflow is implemented.

### 5.4 Report Export Content

Evidence summary report exports include:

1. Report title and non-diagnostic disclaimer.
2. Document metadata and source list.
3. Standardized evidence matrix.
4. Extracted phenotype, method, experiment result, population, and computational evidence.
5. Entity standardization table with match status/rationale.
6. Source snippets and translated snippets.
7. Table/figure references and VLM descriptions.
8. Confidence scores and low-confidence flags.
9. Expert comments and structured feedback.
10. Appendix with source anchors, page/line references, and bbox/table/figure IDs.

## 6. API Flow Summary

```text
Frontend (Next.js)
    │
    ├── /api/v1/* proxy via next.config.ts
    ▼
Backend (FastAPI)
    ├── POST /api/v1/auth/register
    ├── POST /api/v1/auth/verify-email
    ├── POST /api/v1/auth/login
    ├── GET  /api/v1/literature/search
    ├── POST /api/v1/tasks
    ├── GET  /api/v1/tasks/{task_id}
    ├── WS   /api/v1/tasks/{task_id}/ws
    ├── GET  /api/v1/tasks/{task_id}/result
    ├── POST /api/v1/tasks/{task_id}/comments
    ├── POST /api/v1/tasks/{task_id}/export
    ├── GET  /api/v1/evidence          # P1/future
    └── GET  /api/v1/health
```

Task/result reads are public in the current MVP. Comments/feedback require login. Deployed task creation should require login; local development may allow unrestricted task creation.
