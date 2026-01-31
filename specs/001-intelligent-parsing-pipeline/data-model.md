# Data Model: Intelligent Parsing Pipeline System

**Feature**: 001-intelligent-parsing-pipeline
**Date**: 2026-01-30
**Purpose**: Define entity schemas, relationships, and validation rules for ACMG evidence extraction system

## Entity Relationship Overview

```
Document 1──────* Evidence Item
   │                    │
   │                    │
   *                    *
Translation Pair    Variant ──────* Phenotype
                       │
                       │
                       *
                 Knowledge Graph Node

Parsing Task ───1 Document
     │
     *
Audit Log Entry
```

## Core Entities

### 1. Document

**Purpose**: Represents a biomedical research paper uploaded or fetched from external sources

**Attributes**:
- `id` (UUID, PK): Unique identifier
- `title` (String, 500 chars): Paper title
- `authors` (JSONB): Array of author objects `[{name, affiliation}]`
- `journal` (String, 200 chars): Publication venue
- `publication_date` (Date): When paper was published
- `pmid` (String, nullable): PubMed ID if available
- `doi` (String, nullable): Digital Object Identifier if available
- `content_hash` (String, 64 chars): SHA256 hash of PDF content (for deduplication and traceability)
- `file_size_bytes` (Integer): Original PDF size
- `page_count` (Integer): Number of pages
- `storage_path` (String): MinIO object key (e.g., `/acmg_documents/2026/01/abc123.pdf`)
- `processing_status` (Enum): PENDING | PROCESSING | COMPLETED | FAILED | NEEDS_REVIEW
- `created_at` (Timestamp): Upload timestamp
- `updated_at` (Timestamp): Last modification

**Relationships**:
- Has many `Evidence Items` (1-to-many)
- Has many `Translation Pairs` (1-to-many)
- Has one `Parsing Task` (1-to-1)

**Validation Rules**:
- `file_size_bytes` ≤ 100MB (104,857,600 bytes)
- `content_hash` must be unique (prevent duplicate uploads)
- At least one of `pmid` or `doi` should be present if fetched externally
- `page_count` must be > 0

**Indexes**:
- Primary: `id`
- Unique: `content_hash`
- Lookup: `pmid`, `doi`
- Filter: `processing_status`, `created_at`

---

### 2. Evidence Item

**Purpose**: A single ACMG criterion extracted from a document with confidence score and source coordinates

**Attributes**:
- `id` (UUID, PK): Unique identifier
- `document_id` (UUID, FK → Document): Source document
- `acmg_code` (Enum): PS1-PS4 | PM1-PM6 | PP1-PP5 | BA1 | BS1-BS4 | BP1-BP7
- `confidence_score` (Decimal(3,2)): Range 0.00-1.00
- `source_page` (Integer): Page number where evidence found (1-indexed)
- `bounding_box` (JSONB): Coordinates `{x, y, width, height}` in PDF coordinate space
- `source_hash` (String, 64 chars): SHA256 hash linking to document content
- `supporting_text` (Text): Excerpt from paper supporting this evidence
- `review_required` (Boolean): True if confidence_score < 0.85
- `human_reviewed` (Boolean): True if manually verified
- `human_notes` (Text, nullable): Reviewer comments
- `variant_id` (UUID, FK → Variant, nullable): Linked genetic variant
- `extracted_at` (Timestamp): When Agent extracted this evidence
- `updated_at` (Timestamp): Last edit timestamp

**Relationships**:
- Belongs to one `Document` (many-to-1)
- Belongs to one `Variant` (many-to-1, optional)

**Validation Rules**:
- `confidence_score` ∈ [0.00, 1.00]
- `review_required` = True if `confidence_score` < 0.85
- `source_page` ≤ `document.page_count`
- `bounding_box` must have keys: x, y, width, height (all non-negative)
- `source_hash` must match `document.content_hash` (immutability check)

**Indexes**:
- Primary: `id`
- Foreign Key: `document_id`, `variant_id`
- Filter: `review_required`, `human_reviewed`, `acmg_code`
- Range: `confidence_score`, `extracted_at`

---

### 3. Translation Pair

**Purpose**: Aligned English and Chinese text segments from a document with paragraph-level correspondence

**Attributes**:
- `id` (UUID, PK): Unique identifier
- `document_id` (UUID, FK → Document): Source document
- `paragraph_index` (Integer): Sequential paragraph number in document
- `source_language` (Enum): EN | ZH
- `source_text` (Text): Original text segment
- `target_text` (Text): Translated text segment
- `source_page` (Integer): Page number of source text
- `source_coordinates` (JSONB): Bounding box `{x, y, width, height}`
- `alignment_confidence` (Decimal(3,2)): Translation alignment quality (0.00-1.00)
- `created_at` (Timestamp): When translation generated

**Relationships**:
- Belongs to one `Document` (many-to-1)

**Validation Rules**:
- `paragraph_index` must be sequential within document (no gaps)
- `source_page` ≤ `document.page_count`
- `alignment_confidence` ∈ [0.00, 1.00]
- `source_text` and `target_text` cannot both be empty

**Indexes**:
- Primary: `id`
- Foreign Key: `document_id`
- Composite: `(document_id, paragraph_index)` for ordered retrieval

---

### 4. Variant

**Purpose**: A genetic variant mentioned in documents with associated evidence

**Attributes**:
- `id` (UUID, PK): Unique identifier
- `hgvs_notation` (String, 200 chars): Variant notation in HGVS format (e.g., `NM_000059.3:c.1521_1523delCTT`)
- `gene` (String, 50 chars): Gene symbol (e.g., `BRCA1`)
- `chromosome` (String, 5 chars): Chromosome location (e.g., `chr17`)
- `position` (Integer): Genomic position
- `reference_allele` (String, 1000 chars): Reference sequence
- `alternate_allele` (String, 1000 chars): Variant sequence
- `pathogenicity_classification` (Enum): BENIGN | LIKELY_BENIGN | VUS | LIKELY_PATHOGENIC | PATHOGENIC | CONFLICTING
- `aggregated_confidence` (Decimal(3,2)): Cross-document aggregated confidence (0.00-1.00)
- `evidence_count` (Integer): Number of evidence items linked
- `created_at` (Timestamp): First mention timestamp
- `updated_at` (Timestamp): Last evidence update

**Relationships**:
- Has many `Evidence Items` (1-to-many)
- Has many `Phenotypes` (many-to-many via graph)

**Validation Rules**:
- `hgvs_notation` must be unique
- `aggregated_confidence` ∈ [0.00, 1.00]
- `evidence_count` ≥ 0
- `pathogenicity_classification` derived from ACMG evidence rules

**Indexes**:
- Primary: `id`
- Unique: `hgvs_notation`
- Lookup: `gene`, `chromosome`
- Filter: `pathogenicity_classification`

---

### 5. Phenotype

**Purpose**: Clinical phenotype associated with variants

**Attributes**:
- `id` (UUID, PK): Unique identifier
- `hpo_code` (String, 20 chars): Human Phenotype Ontology code (e.g., `HP:0000001`)
- `description` (String, 500 chars): Human-readable phenotype description
- `severity` (Enum): MILD | MODERATE | SEVERE | PROFOUND
- `affected_system` (String, 100 chars): Biological system (e.g., `Cardiovascular`, `Neurological`)
- `prevalence` (Decimal(5,4)): Population frequency (0.0000-1.0000)
- `created_at` (Timestamp): First mention timestamp

**Relationships**:
- Has many `Variants` (many-to-many via graph)

**Validation Rules**:
- `hpo_code` must match regex `^HP:\d{7}$`
- `prevalence` ∈ [0.0000, 1.0000]

**Indexes**:
- Primary: `id`
- Unique: `hpo_code`
- Filter: `severity`, `affected_system`

---

### 6. Parsing Task

**Purpose**: Asynchronous job processing a document through the pipeline

**Attributes**:
- `id` (UUID, PK): Celery task ID
- `document_id` (UUID, FK → Document): Document being processed
- `current_stage` (Enum): INGESTION | DECOMPOSITION | LAYOUT | TRANSLATION | EVIDENCE | ARBITRATION | COMPLETED
- `progress_percentage` (Integer): 0-100 completion percentage
- `status` (Enum): PENDING | PROCESSING | COMPLETED | FAILED | RETRY
- `priority` (Integer): Queue priority (0=lowest, 10=highest)
- `retry_count` (Integer): Number of retry attempts (max 3)
- `failure_reason` (Text, nullable): Error message if failed
- `started_at` (Timestamp, nullable): When processing began
- `completed_at` (Timestamp, nullable): When processing finished
- `created_at` (Timestamp): Task creation timestamp
- `estimated_completion` (Timestamp, nullable): ETA for completion

**Relationships**:
- Belongs to one `Document` (1-to-1)
- Has many `Audit Log Entries` (1-to-many)

**Validation Rules**:
- `progress_percentage` ∈ [0, 100]
- `retry_count` ≤ 3
- `priority` ∈ [0, 10]
- `completed_at` > `started_at` when status=COMPLETED

**Indexes**:
- Primary: `id`
- Foreign Key: `document_id`
- Filter: `status`, `current_stage`, `priority`
- Range: `created_at`, `started_at`

---

### 7. Audit Log Entry

**Purpose**: Immutable record of Agent decision-making for debugging and optimization

**Attributes**:
- `id` (UUID, PK): Unique identifier
- `task_id` (UUID, FK → Parsing Task): Associated task
- `created_at` (Timestamp): Log entry timestamp (partition key)
- `agent_type` (Enum): LAYOUT | TRANSLATION | EVIDENCE | ARBITRATION
- `state_from` (String, 50 chars): Previous state
- `state_to` (String, 50 chars): New state
- `confidence_score` (Decimal(3,2), nullable): If applicable
- `latency_ms` (Integer): Agent execution time in milliseconds
- `input_prompt` (Text): Full prompt sent to LLM/Agent
- `output_reasoning` (Text): Agent's reasoning/response
- `failure_reason` (Text, nullable): Error details if transition failed
- `model_version` (String, 50 chars): LLM model identifier (e.g., `gpt-4-2024-01`)
- `token_count` (Integer, nullable): LLM tokens consumed

**Relationships**:
- Belongs to one `Parsing Task` (many-to-1)

**Validation Rules**:
- `latency_ms` > 0
- `confidence_score` ∈ [0.00, 1.00] if not null
- Immutable after insert (no updates/deletes)

**Partitioning**:
- Partitioned by `created_at` (monthly partitions)
- Auto-drop partitions older than 90 days

**Indexes**:
- Primary: `id`
- Foreign Key: `task_id`
- Filter: `agent_type`, `state_to`
- Range: `created_at`, `latency_ms`

---

### 8. Knowledge Graph Node (Neo4j)

**Purpose**: Graph representation of variants, phenotypes, and evidence for cross-document analysis

**Node Types**:

#### Document Node
```cypher
(:Document {
    id: UUID,
    title: String,
    pmid: String,
    doi: String,
    content_hash: String,
    publication_date: Date
})
```

#### Variant Node
```cypher
(:Variant {
    id: UUID,
    hgvs_notation: String,
    gene: String,
    pathogenicity: String,
    aggregated_confidence: Float
})
```

#### Phenotype Node
```cypher
(:Phenotype {
    id: UUID,
    hpo_code: String,
    description: String,
    severity: String
})
```

#### Evidence Node
```cypher
(:Evidence {
    id: UUID,
    acmg_code: String,
    confidence_score: Float,
    source_page: Integer
})
```

**Relationship Types**:

```cypher
// Document mentions a variant
(:Document)-[:MENTIONS {first_page: Integer, mention_count: Integer}]->(:Variant)

// Document describes a phenotype
(:Document)-[:DESCRIBES {context: String}]->(:Phenotype)

// Document has evidence
(:Document)-[:HAS_EVIDENCE {extracted_at: DateTime}]->(:Evidence)

// Evidence supports a variant
(:Evidence)-[:SUPPORTS {weight: Float}]->(:Variant)

// Variant associated with phenotype
(:Variant)-[:ASSOCIATED_WITH {strength: String}]->(:Phenotype)

// Evidence extracted from document
(:Evidence)-[:EXTRACTED_FROM {page: Integer, bbox: Map}]->(:Document)
```

**Graph Constraints**:
```cypher
CREATE CONSTRAINT variant_hgvs_unique ON (v:Variant) ASSERT v.hgvs_notation IS UNIQUE;
CREATE CONSTRAINT phenotype_hpo_unique ON (p:Phenotype) ASSERT p.hpo_code IS UNIQUE;
CREATE INDEX variant_gene_idx ON :Variant(gene);
CREATE INDEX document_pmid_idx ON :Document(pmid);
```

---

## Supporting Tables

### Agent Cache

**Purpose**: Cache Agent outputs to prevent redundant LLM calls

**Attributes**:
- `input_hash` (String(64), PK): SHA256 hash of prompt + input
- `agent_type` (Enum): LAYOUT | TRANSLATION | EVIDENCE | ARBITRATION
- `model_version` (String, 50 chars): LLM model identifier
- `output` (JSONB): Cached Agent response
- `created_at` (Timestamp): Cache entry timestamp
- `hit_count` (Integer): Number of cache hits

**Validation Rules**:
- TTL: 30 days (auto-delete via PostgreSQL)
- Invalidate when `model_version` changes

---

### Storage Operations (Saga Log)

**Purpose**: Track multi-store operations for consistency debugging

**Attributes**:
- `saga_id` (UUID, PK): Unique saga identifier
- `task_id` (UUID, FK → Parsing Task): Associated task
- `step_name` (String, 100 chars): Operation name (e.g., `write_minio`, `commit_postgres`)
- `status` (Enum): PENDING | COMPLETED | FAILED | COMPENSATED
- `target_store` (Enum): MINIO | POSTGRES | NEO4J | QDRANT
- `operation_data` (JSONB): Store-specific details
- `created_at` (Timestamp): Step start time
- `completed_at` (Timestamp, nullable): Step completion time

**Validation Rules**:
- Steps within saga must be atomic (no partial writes)
- Failed steps trigger compensation for previous steps

---

## Validation Rules Summary

### Cross-Entity Constraints

1. **Confidence Threshold Enforcement**:
   - `evidence_item.review_required` = True if `confidence_score` < 0.85
   - Arbitration Agent must set this flag automatically

2. **Traceability Linkage**:
   - `evidence_item.source_hash` MUST equal `document.content_hash`
   - Prevents evidence orphaning if document re-uploaded

3. **Task Lifecycle**:
   - `parsing_task.status` = COMPLETED only if `document.processing_status` = COMPLETED
   - State machine enforces this via transitions library

4. **Audit Immutability**:
   - `audit_log_entry` rows cannot be updated or deleted
   - PostgreSQL triggers enforce this

5. **Graph Synchronization**:
   - Neo4j nodes mirror PostgreSQL primary entities
   - Eventual consistency via background sync job (Celery task)

### Data Type Conventions

- **UUIDs**: All primary keys (PostgreSQL `uuid-ossp` extension)
- **Timestamps**: UTC timezone, PostgreSQL `TIMESTAMPTZ`
- **Enums**: PostgreSQL `ENUM` types for type safety
- **JSONB**: Semi-structured data (bounding boxes, metadata)
- **Decimal**: Financial/score precision (avoid float for confidence)

---

## Migration Strategy

1. **Alembic Migrations**: All schema changes versioned
2. **Backward Compatibility**: Add columns with defaults, deprecate old columns
3. **Data Backfill**: Celery tasks for populating new columns on existing rows
4. **Index Maintenance**: Create concurrently to avoid locks

---

## Next Steps

Proceed to **Phase 1: Contracts** to generate:
1. `contracts/openapi.yaml` - REST API endpoints
2. `contracts/websocket.md` - WebSocket protocol
