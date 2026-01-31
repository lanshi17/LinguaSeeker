<!--
Sync Impact Report
==================
Version: 0.0.0 → 1.0.0 (INITIAL RATIFICATION)
Rationale: Initial constitution establishing core architectural and operational principles for the ACMG-PS3 Intelligence System.

Modified Principles: N/A (initial version)
Added Sections:
  - Core Principles (4 principles: Architectural Sovereignty & Modularity, Domain Integrity & Precision, Resilience & Consistency, Performance & UX)
  - Governance

Removed Sections: N/A

Templates Requiring Updates:
  ✅ .specify/templates/plan-template.md - Constitution Check section verified
  ✅ .specify/templates/spec-template.md - Requirements alignment verified
  ✅ .specify/templates/tasks-template.md - Task categorization verified

Follow-up TODOs: None
-->

# ACMG-PS3 Intelligence System Constitution

## Core Principles

### I. Architectural Sovereignty & Modularity

The system MUST enforce strict architectural boundaries to ensure maintainability and prevent technical debt accumulation.

**Strict Layered Governance**: The system MUST adhere to unidirectional flow: Presentation → Application → Domain → Infrastructure. Layer bypassing (e.g., Presentation directly accessing Infrastructure) is strictly prohibited. All cross-layer communication MUST traverse through the defined interfaces of adjacent layers.

**Granular Decomposition**: Code maintainability is paramount. No single Python source file shall exceed 200 lines of code. When a file approaches this limit, functionality MUST be decomposed into atomic sub-modules. This constraint ensures cognitive load remains manageable and promotes single-responsibility design.

**DTO Isolation**: Data transfer between layers MUST occur exclusively via dedicated Data Transfer Objects (DTOs). Domain models shall NOT leak into the Presentation layer, and database entities shall NOT leak into the Domain layer. This prevents coupling and enables independent evolution of each layer.

**Rationale**: Layered architecture with strict boundaries prevents "big ball of mud" anti-pattern, enables parallel development across layers, and allows replacement of infrastructure components without domain logic changes. The 200-line limit enforces modularity at the file level, making code review and testing tractable.

### II. Domain Integrity & Precision

The system's core competency is automated extraction of ACMG evidence codes with measurable accuracy and full traceability.

**ACMG Compliance**: The system's core function is extraction of PS/PM/BP evidence codes from biomedical literature. The acceptance threshold for automated extraction is a confidence score ≥ 0.85. Scores below this threshold MUST trigger the "Human-in-the-Loop" fallback mechanism, routing the document to manual review queues.

**Traceability**: Every extracted evidence artifact MUST retain a cryptographic link to its source coordinates (page number, bounding box coordinates). This enables the "Three-Screen Linkage" capability (Source PDF ↔ Translation ↔ Evidence List) without ambiguity. The link MUST be immutable once created.

**Agent Determinism**: The Agent workflow MUST be state-machine driven using the `transitions` library. State transitions MUST be explicit and logged. Intermediate outputs (Agent reasoning steps) MUST be cached via Input Hash (SHA256) to prevent redundant processing and ensure auditability. Cache invalidation MUST occur only on explicit version updates to the Agent prompt or model.

**Rationale**: ACMG evidence extraction is mission-critical for clinical decision-making. The 0.85 confidence threshold balances automation efficiency with patient safety. Cryptographic traceability ensures reproducibility and supports regulatory audit requirements. State-machine determinism prevents non-deterministic Agent behavior from corrupting downstream analysis.

### III. Resilience & Consistency

The system MUST guarantee data consistency across heterogeneous storage backends and graceful degradation under failure scenarios.

**Transactional Orchestration**: Cross-resource operations spanning PostgreSQL (metadata) + MinIO (artifacts) + Neo4j (knowledge graph) + Qdrant (vector embeddings) MUST be managed by the StorageOrchestrationService. The consistency model follows "Write Artifacts (MinIO) → Commit Metadata (PostgreSQL)". If metadata commit fails, artifact writes MUST be rolled back via compensating transactions. The orchestrator MUST maintain an idempotency key for each operation.

**Asynchronous Reliability**: All document parsing tasks MUST execute asynchronously. The system MUST guarantee a task failure rate <1% via retry strategy (maximum 3 retries with exponential backoff: 2s, 4s, 8s). Failed tasks exceeding retry limit MUST route to Dead Letter Queues for manual intervention. Task status MUST be queryable at any time via task_id.

**Auditability**: All Agent decisions, latency metrics, and state transitions MUST be logged immutably to the `agent_logs` table. Logs MUST include: timestamp (UTC), task_id, state_from, state_to, confidence_score, latency_ms, and failure_reason (if applicable). Logs MUST be retained for minimum 90 days for continuous optimization analysis.

**Rationale**: Multi-store consistency is the hardest problem in distributed systems. The "artifacts-first, metadata-second" ordering ensures data is never orphaned. The <1% failure rate SLO ensures production reliability. Immutable audit logs are required for model performance analysis and compliance.

### IV. Performance & UX

The system MUST provide real-time feedback and leverage graph topology for intelligent evidence aggregation.

**Real-Time Feedback**: Long-running processes (document parsing, evidence extraction) MUST push progress updates to the frontend via WebSocket. Progress updates MUST include: percentage complete, current stage (parsing/extracting/validating), estimated time remaining (optional). Users shall never be left uncertain about task state. WebSocket connection failures MUST trigger automatic reconnection with exponential backoff.

**Graph-Based Aggregation**: Evidence aggregation logic MUST utilize Neo4j to identify cross-literature relationships. Evidence upgrading decisions (e.g., promoting PM-level evidence to PS-level based on corroborating studies) MUST be based on graph topology analysis rather than isolated document analysis. The graph query MUST traverse at minimum 2 hops to identify reinforcing evidence clusters.

**Rationale**: Real-time feedback transforms perceived performance and reduces user anxiety during multi-minute parsing operations. Graph-based aggregation exploits the network structure of biomedical literature to surface stronger evidence than single-document analysis, directly improving clinical decision quality.

## Governance

### Amendment Process

1. Proposed amendments MUST be documented in a Pull Request to `.specify/memory/constitution.md`
2. Amendments MUST include:
   - Version bump rationale (MAJOR/MINOR/PATCH)
   - Sync Impact Report identifying affected templates and commands
   - Migration plan for existing code/features violating new principles
3. Amendments require approval from project technical lead
4. Upon merge, version MUST increment and `LAST_AMENDED_DATE` MUST update to merge date

### Versioning Policy

- **MAJOR**: Backward-incompatible governance changes (e.g., removing a principle, redefining acceptance thresholds)
- **MINOR**: New principle additions or materially expanded guidance (e.g., adding new architectural layer)
- **PATCH**: Clarifications, wording improvements, non-semantic refinements

### Compliance Review

All Pull Requests MUST verify compliance with constitution principles:

- Architecture reviews MUST check layered flow and DTO isolation
- Code reviews MUST reject files exceeding 200 lines without decomposition justification
- Feature specifications MUST document how they satisfy Domain Integrity requirements
- Performance testing MUST validate real-time feedback and graph aggregation correctness

Complexity violations (e.g., exceeding 200-line limit due to generated code) MUST be explicitly justified in the Complexity Tracking section of implementation plans. Unjustified violations MUST be rejected.

**Constitution Version**: 1.0.0 | **Ratified**: 2026-01-30 | **Last Amended**: 2026-01-30
