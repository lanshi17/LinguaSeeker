# Intelligent Parsing Pipeline System - Tasks

**Feature**: 001-intelligent-parsing-pipeline
**Date**: 2026-01-31
**Generated from**: specs/001-intelligent-parsing-pipeline/

## Overview

This task list implements the Intelligent Parsing Pipeline System for automated ACMG evidence extraction from biomedical literature. The system follows a strict 4-layer architecture (Presentation → Application → Domain → Infrastructure) with components for document parsing, evidence extraction, knowledge graph aggregation, and system governance.

## Dependencies

### User Story Dependency Graph
```
US1 (P1) → US2 (P2) → US3 (P3) → US4 (P4)
```

- US2 depends on US1 (requires parsed documents and extracted evidence)
- US3 depends on US1 (requires processed documents for graph building)
- US4 depends on US1, US2, US3 (requires full system for monitoring and governance)

### Parallel Execution Opportunities
- Multiple documents can be processed in parallel during US1
- Evidence extraction for different document sections can be parallelized
- Knowledge graph updates for different variants can be parallelized

## Implementation Strategy

### MVP Scope
- US1 (P1) only: Basic document upload and evidence extraction
- Focus on core pipeline: PDF upload → MinerU parsing → Evidence extraction → Confidence scoring
- Minimal UI for testing (API endpoints only)

### Incremental Delivery
- Phase 1-2: Foundation and US1 (Core functionality)
- Phase 3: US2 (Review interface)
- Phase 4: US3 (Knowledge graph)
- Phase 5: US4 (Governance features)

---

## Phase 1: Setup Tasks

- [X] T001 Create project structure per implementation plan in apps/backend/src/
- [X] T002 [P] Set up configuration files in config/ with app_config.py, database_config.py, celery_config.py
- [X] T003 [P] Initialize requirements.txt with FastAPI, Celery, Redis, PostgreSQL, Neo4j, Qdrant, MinerU dependencies
- [X] T004 [P] Create docker-compose.yml for local development services (PostgreSQL, Redis, MinIO, Neo4j, Qdrant)
- [X] T005 Set up pyproject.toml with project metadata and build configuration
- [X] T006 Initialize git repository with .gitignore for Python project
- [X] T007 Create README.md with project overview and setup instructions
- [X] T008 Set up alembic for database migrations in apps/backend/migrations/
- [X] T009 [P] Create initial test suite structure in tests/unit/, tests/integration/, tests/contract/
- [X] T010 Create .env files for different environments (.env.development, .env.test, .env.production)

---

## Phase 2: Foundational Tasks

- [X] T011 [P] Create PostgreSQL database models in src/infrastructure/database/postgres_models.py
- [X] T012 [P] Create domain entities in src/domain/models/ (document.py, evidence_item.py, variant.py, parsing_task.py)
- [X] T013 [P] Create domain value objects in src/domain/value_objects/ (confidence_score.py, source_coordinates.py, acmg_code.py)
- [X] T014 [P] Create domain interfaces in src/domain/interfaces/ (document_repository.py, graph_repository.py, storage_client.py)
- [X] T015 [P] Create infrastructure repositories in src/infrastructure/repositories/ (postgres/document_repository_impl.py, postgres/task_repository_impl.py, postgres/audit_log_repository_impl.py)
- [X] T016 [P] Create infrastructure storage client in src/infrastructure/storage/minio_storage_client.py
- [X] T017 [P] Create infrastructure adapters in src/infrastructure/adapters/ (mineru_adapter.py, llm_adapter.py)
- [X] T018 Create domain agents infrastructure in src/domain/agents/ (agent_workflow.py, layout_agent.py, translation_agent.py, evidence_agent.py, arbitration_agent.py)
- [X] T019 Create application services in src/application/services/ (storage_orchestration_service.py, pdf_parse_service.py, data_processing_service.py)
- [X] T020 [P] Create presentation layer DTOs in src/presentation/dtos/ (request/pdf_upload_request.py, response/task_status_response.py)

---

## Phase 3: User Story 1 - Document Upload and Automated Evidence Extraction

### Story Goal
A clinical geneticist needs to extract ACMG evidence codes from a newly published research paper. They upload a PDF document to the system, which automatically parses the document, translates it if needed, and extracts structured evidence with confidence scores. The system highlights low-confidence extractions for manual review.

### Independent Test Criteria
Can be fully tested by uploading a PDF with known ACMG evidence, verifying that the system returns structured JSON with correct evidence codes and confidence scores ≥0.85, and confirming that low-confidence items are flagged for review.

- [X] T021 [US1] Create PDF upload endpoint in src/presentation/controllers/pdf_parse_controller.py
- [X] T022 [US1] Implement PDF validation logic in src/application/services/pdf_parse_service.py
- [X] T023 [US1] Create MinIO storage integration in src/infrastructure/storage/minio_storage_client.py
- [X] T024 [US1] Create document entity with processing status in src/domain/models/document.py
- [X] T025 [US1] Implement document repository in src/infrastructure/repositories/postgres/document_repository_impl.py
- [X] T026 [US1] Create task management service in src/application/services/task_management_service.py
- [X] T027 [US1] Create parsing task entity in src/domain/models/parsing_task.py
- [X] T028 [US1] Implement parsing task repository in src/infrastructure/repositories/postgres/task_repository_impl.py
- [X] T029 [US1] Create Celery task for PDF parsing in src/infrastructure/tasks/celery_tasks.py
- [X] T030 [US1] Integrate MinerU adapter for PDF parsing in src/infrastructure/adapters/mineru_adapter.py
- [X] T031 [US1] Create layout agent for document structure parsing in src/domain/agents/layout_agent.py
- [X] T032 [US1] Create translation agent for bilingual text generation in src/domain/agents/translation_agent.py
- [X] T033 [US1] Create evidence agent for ACMG evidence extraction in src/domain/agents/evidence_agent.py
- [X] T034 [US1] Create arbitration agent for confidence scoring in src/domain/agents/arbitration_agent.py
- [X] T035 [US1] Implement state machine for agent workflow in src/domain/agents/agent_workflow.py
- [X] T036 [US1] Create evidence item entity in src/domain/models/evidence_item.py
- [X] T037 [US1] Create evidence repository in src/infrastructure/repositories/postgres/evidence_repository_impl.py
- [X] T038 [US1] Implement confidence threshold logic (0.85) in arbitration_agent.py
- [X] T039 [US1] Create audit logging service in src/infrastructure/repositories/postgres/audit_log_repository_impl.py
- [X] T040 [US1] Implement storage orchestration service in src/application/services/storage_orchestration_service.py
- [X] T041 [US1] Create task status endpoint in src/presentation/controllers/task_controller.py
- [X] T042 [US1] Implement progress tracking with WebSocket integration in src/presentation/websocket/progress_handler.py
- [X] T043 [US1] Create translation pair entity in src/domain/models/translation_pair.py
- [X] T044 [US1] Implement source coordinate tracking in evidence items
- [X] T045 [US1] Add support for PMID/DOI fetching in src/presentation/controllers/pdf_parse_controller.py
- [X] T046 [US1] Create evidence item DTOs in src/presentation/dtos/response/evidence_list_response.py
- [X] T047 [US1] Implement retry logic for failed tasks in src/infrastructure/tasks/celery_tasks.py
- [X] T048 [US1] Add dead letter queue configuration for failed tasks in celery_config.py
- [X] T049 [US1] Create agent cache for performance in src/infrastructure/repositories/postgres/agent_cache_repository_impl.py
- [X] T050 [US1] Write unit tests for domain agents in tests/unit/domain/agents/
- [X] T051 [US1] Write integration tests for PDF parsing pipeline in tests/integration/test_pdf_parsing_pipeline.py
- [X] T052 [US1] Write API contract tests for upload endpoints in tests/contract/test_api_contracts.py

---

## Phase 4: User Story 2 - Interactive Three-Screen Review and Editing

### Story Goal
After automated extraction, a clinical researcher needs to verify the extracted evidence by reviewing the original source context. They use a unified dashboard showing the original PDF, translated/parsed text, and extracted evidence list side-by-side. Clicking any evidence item auto-scrolls all three views to the exact source location, and they can edit or approve the evidence directly.

### Independent Test Criteria
Can be tested by loading a previously parsed document, clicking evidence items to verify all three screens synchronize correctly, editing an evidence entry, and confirming changes persist.

- [ ] T053 [US2] Create evidence review endpoint in src/presentation/controllers/evidence_controller.py
- [ ] T054 [US2] Implement evidence CRUD operations in src/application/services/evidence_aggregation_service.py
- [ ] T055 [US2] Create evidence edit request DTO in src/presentation/dtos/request/evidence_edit_request.py
- [ ] T056 [US2] Add evidence editing functionality to evidence_controller.py
- [ ] T057 [US2] Create evidence synchronization logic for three-screen view
- [ ] T058 [US2] Implement source coordinate navigation in PDF viewer component
- [ ] T059 [US2] Add visual indicators for low-confidence items in evidence list
- [ ] T060 [US2] Create evidence review status tracking in evidence_item.py
- [ ] T061 [US2] Implement human review functionality in src/application/use_cases/process_document_use_case.py
- [ ] T062 [US2] Create review dashboard controller in src/presentation/controllers/evidence_controller.py
- [ ] T063 [US2] Add note-taking functionality for reviewers in evidence_item.py
- [ ] T064 [US2] Create evidence comparison utilities in src/application/services/evidence_aggregation_service.py
- [ ] T065 [US2] Implement evidence validation after human edits
- [ ] T066 [US2] Add real-time synchronization between panels
- [ ] T067 [US2] Write unit tests for evidence review functionality in tests/unit/services/
- [ ] T068 [US2] Write integration tests for review dashboard in tests/integration/test_storage_orchestration.py
- [ ] T069 [US2] Create evidence approval workflow in src/domain/agents/arbitration_agent.py

---

## Phase 5: User Story 3 - Knowledge Graph Aggregation and Evidence Stacking

### Story Goal
As multiple papers are processed, a research coordinator wants to see aggregated evidence across the entire literature corpus. The system builds a knowledge graph connecting variants, phenotypes, and evidence across documents. When reviewing a variant, the system automatically identifies "evidence stacking" - where multiple papers provide supporting evidence that elevates a variant's pathogenicity classification.

### Independent Test Criteria
Can be tested by processing multiple documents containing the same variant, verifying that the knowledge graph shows connections between them, and confirming that the system suggests evidence upgrades based on cross-document analysis.

- [ ] T070 [US3] Create Neo4j graph repository implementation in src/infrastructure/repositories/neo4j/graph_repository_impl.py
- [ ] T071 [US3] Define Neo4j node and relationship schemas in src/infrastructure/repositories/neo4j/graph_repository_impl.py
- [ ] T072 [US3] Create variant entity in src/domain/models/variant.py
- [ ] T073 [US3] Create phenotype entity in src/domain/models/phenotype.py
- [ ] T074 [US3] Implement variant repository in src/infrastructure/repositories/neo4j/graph_repository_impl.py
- [ ] T075 [US3] Create evidence aggregation service in src/application/services/evidence_aggregation_service.py
- [ ] T076 [US3] Implement graph synchronization logic between PostgreSQL and Neo4j
- [ ] T077 [US3] Create cross-document evidence matching algorithm
- [ ] T078 [US3] Implement evidence stacking detection logic
- [ ] T079 [US3] Create graph query endpoints in src/presentation/controllers/literature_graph_controller.py
- [ ] T080 [US3] Add variant detail endpoint with aggregated evidence in src/presentation/controllers/literature_graph_controller.py
- [ ] T081 [US3] Implement 2-hop traversal algorithms for evidence stacking
- [ ] T082 [US3] Create evidence upgrade suggestion logic
- [ ] T083 [US3] Add graph visualization response DTOs in src/presentation/dtos/response/graph_viz_response.py
- [ ] T084 [US3] Implement graph backup and sync mechanisms
- [ ] T085 [US3] Write integration tests for Neo4j integration in tests/integration/test_graph_aggregation.py
- [ ] T086 [US3] Create graph index optimization routines
- [ ] T087 [US3] Implement graph-based recommendation algorithms

---

## Phase 6: User Story 4 - Task Management and System Governance

### Story Goal
A lab manager needs to monitor the document processing pipeline, prioritize urgent papers, handle failed parsing tasks, and audit the system's extraction decisions. They access a management dashboard showing all parsing queues, task statuses, failure reasons, and complete audit trails of Agent inputs/outputs for debugging low-confidence extractions.

### Independent Test Criteria
Can be tested by submitting multiple documents, viewing the queue status, manually prioritizing one task, forcing a failure scenario, and verifying the audit trail shows complete Agent decision history.

- [ ] T088 [US4] Enhance task management service with priority controls in src/application/services/task_management_service.py
- [ ] T089 [US4] Create task prioritization endpoint in src/presentation/controllers/task_controller.py
- [ ] T090 [US4] Implement audit trail endpoint in src/presentation/controllers/task_controller.py
- [ ] T091 [US4] Create audit log entity in src/domain/models/audit_log_entry.py
- [ ] T092 [US4] Enhance audit logging with complete agent decision history
- [ ] T093 [US4] Add task failure analysis tools in src/application/services/task_management_service.py
- [ ] T094 [US4] Create task retry functionality in src/presentation/controllers/task_controller.py
- [ ] T095 [US4] Implement task queue monitoring in src/presentation/controllers/task_controller.py
- [ ] T096 [US4] Add comprehensive logging for debugging in src/infrastructure/repositories/postgres/audit_log_repository_impl.py
- [ ] T097 [US4] Create system health monitoring endpoint
- [ ] T098 [US4] Implement alerting for task failure rates >1%
- [ ] T099 [US4] Add performance metrics collection and reporting
- [ ] T100 [US4] Create admin dashboard backend in src/presentation/controllers/task_controller.py
- [ ] T101 [US4] Write tests for task management functionality in tests/unit/services/
- [ ] T102 [US4] Create SLA monitoring tools for processing time requirements

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T103 Implement comprehensive error handling and user-friendly error messages
- [ ] T104 Add request validation and sanitization across all endpoints
- [ ] T105 Implement authentication and authorization with JWT tokens
- [ ] T106 Add rate limiting to prevent abuse of API endpoints
- [ ] T107 Create comprehensive API documentation with OpenAPI/Swagger
- [ ] T108 Implement logging throughout the application with structured logging
- [ ] T109 Add metrics collection for monitoring and observability
- [ ] T110 Perform security review and penetration testing preparation
- [ ] T111 Optimize database queries and add appropriate indexes
- [ ] T112 Create deployment configurations for production environment
- [ ] T113 Implement backup and disaster recovery procedures
- [ ] T114 Conduct performance testing and optimization
- [ ] T115 Add end-to-end tests covering complete user workflows
- [ ] T116 Create comprehensive user documentation and guides
- [ ] T117 Perform final integration testing across all components
- [ ] T118 Prepare release notes and deployment checklist