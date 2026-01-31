# ACMG Intelligence System - Backend

Automated ACMG evidence extraction from biomedical literature using intelligent multi-agent workflows.

## Overview

The Intelligent Parsing Pipeline System automates the extraction of ACMG (American College of Medical Genetics) evidence criteria from biomedical research papers. It uses MinerU for PDF parsing, multi-agent workflows for evidence extraction, and knowledge graph aggregation for cross-document intelligence.

### Key Features

- **Automated PDF Processing**: Upload PDFs or fetch via PMID/DOI for automatic parsing
- **Multi-Agent Workflow**: Layout analysis → Translation → Evidence extraction → Arbitration
- **Confidence Scoring**: 0.85 threshold with human-in-the-loop review for low-confidence items
- **Knowledge Graph**: Neo4j-powered evidence aggregation across documents
- **Real-Time Updates**: WebSocket progress tracking for long-running tasks
- **Audit Trail**: Complete logging of agent decisions for debugging and optimization

## Architecture

```
┌─────────────────┐
│  Presentation   │  FastAPI controllers, WebSocket handlers, DTOs
├─────────────────┤
│  Application    │  Services, use cases, orchestration logic
├─────────────────┤
│     Domain      │  Agents, entities, value objects, interfaces
├─────────────────┤
│ Infrastructure  │  Repositories, adapters (MinerU, LLM), Celery tasks
└─────────────────┘
```

**4-layer architecture** enforcing strict separation of concerns.

## Quick Start

### Prerequisites

- Python 3.12+
- Docker 24.0+ with Docker Compose v2
- 16GB RAM minimum (32GB recommended)
- 20GB disk space

### 1. Start Infrastructure Services

```bash
docker-compose up -d
```

### 2. Install Dependencies

```bash
uv pip install -r requirements.txt
```

### 3. Initialize Database

```bash
alembic upgrade head
python scripts/init_neo4j_schema.py
```

### 4. Start Services

```bash
# Terminal 1: FastAPI server
uvicorn app:app --reload --port 8000

# Terminal 2: Celery worker
celery -A src.infrastructure.tasks.celery_tasks worker --loglevel=info
```

## Documentation

- [Architecture Plan](design_docs/plan.md)
- [Data Model](design_docs/data-model.md)
- [API Contracts](design_docs/contracts/openapi.yaml)
- [Quickstart Guide](design_docs/quickstart.md)

## License

MIT License
