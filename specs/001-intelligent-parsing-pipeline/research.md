# Research: Technology Decisions & Best Practices

**Feature**: Intelligent Parsing Pipeline System
**Date**: 2026-01-30
**Purpose**: Document technology choices, architectural patterns, and integration strategies for ACMG evidence extraction pipeline

## Phase 0: Research Findings

### 1. PDF Parsing Technology: MinerU

**Decision**: Use MinerU as the PDF parsing engine

**Rationale**:
- **Layout Preservation**: MinerU excels at maintaining document structure (headings, tables, figures) which is critical for scientific papers
- **Multi-modal Output**: Extracts text, images, and layout metadata in structured formats (Markdown + JSON)
- **Academic Paper Optimization**: Specifically designed for research paper parsing with better handling of citations, formulas, and complex layouts compared to PyPDF2/pdfplumber
- **Integration Ready**: Provides clean API with async support for Celery integration

**Alternatives Considered**:
- **PyMuPDF (fitz)**: Rejected - lower quality text extraction for complex layouts, weaker table handling
- **pdfplumber**: Rejected - better than PyMuPDF but still struggles with multi-column academic papers
- **Camelot/Tabula**: Rejected - specialized for tables only, would require multiple libraries

**Best Practices**:
- Wrap MinerU in adapter pattern (`mineru_adapter.py`) to isolate external dependency
- Cache parsing results in MinIO to avoid re-parsing on Agent retry
- Implement timeout mechanism (5 min max) to handle pathological PDFs
- Extract metadata separately using PyPDF2 for fallback title/author extraction

### 2. State Machine Library: `transitions`

**Decision**: Use `transitions` library for Agent workflow orchestration

**Rationale**:
- **Explicit State Modeling**: Enforces state machine pattern with clear states and transitions, preventing invalid state combinations
- **Built-in Logging**: Automatic transition logging aligns with constitution's auditability requirement
- **Conditional Transitions**: Supports confidence threshold branching (≥0.85 → auto-accept, <0.85 → human review)
- **Async Support**: Compatible with FastAPI/Celery async patterns

**Alternatives Considered**:
- **Custom State Machine**: Rejected - reinventing the wheel, error-prone, lacks logging infrastructure
- **python-statemachine**: Rejected - less mature, weaker async support
- **Dramatiq + State Tracking**: Rejected - Dramatiq is task queue, not state machine library

**Best Practices**:
- Define states as enum: `AgentState(Enum)` with PENDING, LAYOUT, TRANSLATION, EVIDENCE, ARBITRATION, COMPLETED, FAILED
- Store state transitions in `agent_logs` table via callback hooks: `machine.on_enter_STATE(log_transition)`
- Implement checkpoint/resume pattern for long-running workflows
- Use `before_transition` guards to validate state preconditions

### 3. Async Task Queue: Celery + Redis

**Decision**: Celery with Redis broker/backend

**Rationale**:
- **Mature Ecosystem**: Industry-standard for Python async tasks with extensive documentation
- **Retry Mechanism**: Built-in exponential backoff (`retry_backoff=True`) matches constitution requirement (2s, 4s, 8s)
- **Progress Tracking**: Native `update_state()` API for real-time WebSocket progress updates
- **Dead Letter Queue**: Supports routing failed tasks after max retries for manual intervention

**Alternatives Considered**:
- **Dramatiq**: Rejected - less WebSocket integration, smaller ecosystem
- **RQ (Redis Queue)**: Rejected - simpler but lacks advanced features (chord, chain, progress tracking)
- **Huey**: Rejected - lightweight but insufficient for production-grade requirements

**Best Practices**:
- Configure task serializer: `task_serializer='json'` for cross-language compatibility
- Set task time limits: `task_time_limit=600` (10 min hard limit), `task_soft_time_limit=540` (9 min warning)
- Enable result backend: `result_backend='redis://...'` for task status queries
- Use task chaining for multi-stage pipeline: `chain(upload.s() | parse.s() | extract.s())()`
- Implement idempotency via task_id: check `agent_cache` before processing

### 4. Multi-Store Consistency: Saga Pattern

**Decision**: Implement Saga pattern in `StorageOrchestrationService`

**Rationale**:
- **No Distributed Transactions**: PostgreSQL, MinIO, Neo4j, Qdrant don't support 2PC (two-phase commit)
- **Compensating Actions**: Saga pattern provides rollback via compensation (e.g., delete MinIO object if PostgreSQL commit fails)
- **Auditability**: Each saga step logged to `storage_operations` table for debugging

**Alternatives Considered**:
- **Two-Phase Commit (2PC)**: Rejected - unsupported by MinIO and Qdrant
- **Event Sourcing**: Rejected - overengineering for this use case, adds complexity
- **Best-Effort**: Rejected - violates constitution's consistency requirement

**Best Practices**:
- Order operations: MinIO write → PostgreSQL commit (fail-fast on metadata)
- Store idempotency keys: `task_id` UUID prevents duplicate saga execution
- Implement compensation methods: `_rollback_minio_write(object_key)`
- Use database transactions for atomic PostgreSQL writes
- Log saga state: `saga_logs` table with (saga_id, step, status, timestamp)

### 5. LLM Integration for Agents

**Decision**: Abstract LLM provider via adapter pattern

**Rationale**:
- **Provider Agnostic**: Adapter (`llm_adapter.py`) allows switching between OpenAI, Anthropic, local models without changing domain logic
- **Prompt Versioning**: Store prompts in configuration files with version hashes for cache invalidation
- **Rate Limiting**: Adapter handles retries, backoff, and quota management
- **Cost Tracking**: Centralized logging of token usage per Agent invocation

**Alternatives Considered**:
- **Direct OpenAI SDK**: Rejected - vendor lock-in, no abstraction for model switching
- **LangChain**: Rejected - heavyweight framework, unnecessary complexity for deterministic workflows

**Best Practices**:
- Define `LLMRequest` and `LLMResponse` DTOs in domain layer
- Implement caching layer: hash(`prompt + input`) → check `agent_cache` before LLM call
- Set temperature=0 for deterministic output (evidence extraction should be consistent)
- Use structured output (JSON mode) to parse ACMG codes reliably
- Implement timeout circuit breaker: fail task if LLM request exceeds 60s

### 6. Neo4j Graph Schema Design

**Decision**: Property graph with typed relationships

**Rationale**:
- **Flexible Schema**: Property graphs support evolving evidence relationships without migrations
- **Cypher Query Power**: Native graph traversal for 2-hop evidence stacking analysis
- **ACID Guarantees**: Neo4j provides transactions for consistent graph updates

**Schema Design**:
```cypher
// Nodes
(:Document {id, title, pmid, doi, content_hash})
(:Variant {id, hgvs_notation, gene})
(:Phenotype {id, hpo_code, description})
(:Evidence {id, acmg_code, confidence_score, source_page, bounding_box})

// Relationships
(:Document)-[:MENTIONS]->(:Variant)
(:Document)-[:DESCRIBES]->(:Phenotype)
(:Document)-[:HAS_EVIDENCE]->(:Evidence)
(:Evidence)-[:SUPPORTS]->(:Variant)
(:Variant)-[:ASSOCIATED_WITH]->(:Phenotype)
(:Evidence)-[:EXTRACTED_FROM {page, bbox}]->(:Document)
```

**Best Practices**:
- Index on frequently queried properties: `CREATE INDEX ON :Variant(hgvs_notation)`
- Use relationship properties for source traceability: `{page, bbox}`
- Implement merge logic: `MERGE (v:Variant {hgvs_notation: $notation})` to avoid duplicates
- Batch writes in transactions: group 100 evidence items per commit
- Use parameterized queries to prevent Cypher injection

### 7. Qdrant Vector Store for RAG

**Decision**: Qdrant for embedding storage and similarity search

**Rationale**:
- **GPU Acceleration**: `gpu-nvidia` version leverages CUDA for fast similarity search
- **Metadata Filtering**: Combine vector search with metadata filters (document date, confidence score)
- **Scalability**: Handles 10K+ documents with <100ms query latency
- **Python Integration**: Native asyncio support for FastAPI integration

**Alternatives Considered**:
- **FAISS**: Rejected - lacks metadata filtering, no persistence layer
- **Pinecone**: Rejected - SaaS vendor lock-in, higher cost
- **Milvus**: Rejected - heavier infrastructure requirements

**Best Practices**:
- Collection schema: `{vector: [768], metadata: {document_id, section_type, page_num}}`
- Use `cosine` distance metric for semantic similarity
- Chunk documents: 512-token chunks with 50-token overlap for context preservation
- Implement hybrid search: combine vector similarity with BM25 keyword matching
- Cache embeddings: store in PostgreSQL `embeddings` table to avoid re-encoding

### 8. WebSocket Progress Updates

**Decision**: FastAPI WebSocket with Redis pub/sub for task progress

**Rationale**:
- **Real-Time Push**: WebSocket enables server-initiated updates (no polling overhead)
- **Redis Pub/Sub**: Decouple Celery workers from WebSocket connections via message broker
- **Connection Management**: FastAPI's `WebSocketManager` handles reconnection logic

**Architecture**:
```
Celery Worker → Redis PUBLISH (task:{task_id}:progress) →
Redis SUBSCRIBE → FastAPI WebSocket → Client Browser
```

**Best Practices**:
- Publish progress every 30 seconds or on stage change
- Include structured payload: `{task_id, percentage, stage, eta, message}`
- Implement heartbeat: send ping every 10s to detect stale connections
- Client-side reconnection: exponential backoff (1s, 2s, 4s, 8s max)
- Handle disconnection gracefully: buffer last 10 progress messages in Redis for reconnect replay

### 9. Database Partitioning for Audit Logs

**Decision**: PostgreSQL table partitioning with 90-day TTL

**Rationale**:
- **Performance**: Partition by month (`created_at`) for fast range queries
- **Automated Cleanup**: Drop old partitions via cron job instead of DELETE queries
- **Index Efficiency**: Partition-local indexes reduce query overhead

**Schema**:
```sql
CREATE TABLE agent_logs (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL,
    created_at TIMESTAMP NOT NULL,
    agent_type VARCHAR(50),
    state_from VARCHAR(50),
    state_to VARCHAR(50),
    confidence_score DECIMAL(3,2),
    latency_ms INTEGER,
    input_prompt TEXT,
    output_reasoning TEXT,
    failure_reason TEXT
) PARTITION BY RANGE (created_at);

CREATE TABLE agent_logs_2026_01 PARTITION OF agent_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

**Best Practices**:
- Create partitions 1 month in advance via cron
- Drop partitions older than 90 days: `DROP TABLE agent_logs_2025_10`
- Index on `task_id` for task-specific log retrieval
- Use `pg_partman` extension for automated partition management

### 10. Testing Strategy

**Decision**: Layered testing with testcontainers for integration tests

**Rationale**:
- **Unit Tests**: Fast, isolated tests for domain logic (Agents, value objects) without external dependencies
- **Integration Tests**: testcontainers spin up real PostgreSQL/Redis/Neo4j/Qdrant for multi-store scenarios
- **Contract Tests**: OpenAPI schema validation ensures API backwards compatibility

**Best Practices**:
- Mock external services in unit tests: `MagicMock(LLMAdapter)`
- Use pytest fixtures for database setup/teardown
- Implement test data builders: `DocumentBuilder().with_pmid("12345").build()`
- Run integration tests in CI with Docker Compose
- Maintain >80% code coverage requirement
- Use `pytest-benchmark` for performance regression testing (e.g., parsing latency)

## Summary of Key Decisions

| Component | Technology | Justification |
|-----------|-----------|---------------|
| PDF Parsing | MinerU | Layout preservation for academic papers |
| State Machine | transitions | Explicit state modeling with logging |
| Task Queue | Celery + Redis | Mature ecosystem, retry/progress tracking |
| Consistency | Saga Pattern | Compensating transactions for multi-store |
| LLM Integration | Adapter Pattern | Provider-agnostic with caching |
| Graph Database | Neo4j | Property graph for evidence relationships |
| Vector Store | Qdrant | GPU acceleration, metadata filtering |
| Real-Time Updates | WebSocket + Redis Pub/Sub | Server push, scalable architecture |
| Audit Retention | PostgreSQL Partitioning | Automated 90-day TTL with performance |
| Testing | pytest + testcontainers | Layered strategy with real dependencies |

## Next Steps

All technology decisions are finalized. Proceed to **Phase 1: Design & Contracts** to generate:
1. `data-model.md` - Entity schemas and relationships
2. `contracts/openapi.yaml` - REST API specification
3. `contracts/websocket.md` - WebSocket protocol
4. `quickstart.md` - Developer setup guide
