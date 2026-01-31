# Quickstart Guide: Intelligent Parsing Pipeline System

**Feature**: 001-intelligent-parsing-pipeline
**Date**: 2026-01-30
**Purpose**: Developer setup guide for local development environment

## Prerequisites

- **Python**: 3.12+ with `uv` package manager
- **Docker**: 24.0+ with Docker Compose v2
- **Git**: 2.40+
- **System RAM**: 16GB minimum (32GB recommended for GPU acceleration)
- **Disk Space**: 20GB free for Docker images and data
- **GPU** (optional): NVIDIA GPU with CUDA 12+ for Qdrant acceleration

## Quick Start (5 Minutes)

### 1. Clone Repository

```bash
git clone https://github.com/your-org/acmg-intelligence-system.git
cd acmg-intelligence-system/apps/backend
```

### 2. Start Infrastructure Services

```bash
docker-compose up -d postgres redis minio neo4j qdrant
```

This starts:
- **PostgreSQL** on port 5432
- **Redis** on port 6379
- **MinIO** on port 9000 (console: 9001)
- **Neo4j** on port 7474 (Bolt: 7687)
- **Qdrant** on port 6333

### 3. Install Python Dependencies

```bash
# Using uv (recommended)
uv pip install -r requirements.txt

# OR using pip
python -m pip install -r requirements.txt
```

### 4. Initialize Database

```bash
# Run Alembic migrations
alembic upgrade head

# Seed Neo4j constraints
python scripts/init_neo4j_schema.py
```

### 5. Start Development Servers

```bash
# Terminal 1: FastAPI server
uvicorn app:app --reload --port 8000

# Terminal 2: Celery worker
celery -A src.infrastructure.tasks.celery_tasks worker --loglevel=info

# Terminal 3: Celery Beat (optional, for scheduled tasks)
celery -A src.infrastructure.tasks.celery_tasks beat --loglevel=info
```

### 6. Verify Setup

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "services": {"postgres": "up", "redis": "up", "minio": "up", "neo4j": "up", "qdrant": "up"}}
```

## Detailed Setup

### Environment Configuration

Create `.env` file in project root:

```bash
# Application
APP_NAME="ACMG-PS3 Intelligence System"
APP_VERSION="1.0.0"
APP_ENV="development"
LOG_LEVEL="DEBUG"

# Server
HOST="0.0.0.0"
PORT=8000

# Database - PostgreSQL
DATABASE_URL="postgresql+asyncpg://acmg_user:acmg_pass@localhost:5432/acmg_db"
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Redis
REDIS_URL="redis://localhost:6379/0"
REDIS_BROKER_URL="redis://localhost:6379/1"  # Celery broker
REDIS_RESULT_BACKEND="redis://localhost:6379/2"  # Celery results

# MinIO
MINIO_ENDPOINT="localhost:9000"
MINIO_ACCESS_KEY="minioadmin"
MINIO_SECRET_KEY="minioadmin"
MINIO_BUCKET_NAME="acmg-documents"
MINIO_USE_SSL=false

# Neo4j
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="neo4j_pass"

# Qdrant
QDRANT_URL="http://localhost:6333"
QDRANT_COLLECTION_NAME="acmg_embeddings"
QDRANT_VECTOR_SIZE=768

# LLM Provider (choose one)
LLM_PROVIDER="openai"  # Options: openai, anthropic, local
OPENAI_API_KEY="sk-..."
# ANTHROPIC_API_KEY="sk-ant-..."
# LOCAL_LLM_ENDPOINT="http://localhost:11434"

# MinerU
MINERU_TIMEOUT=300  # 5 minutes max per PDF
MINERU_MAX_FILE_SIZE=104857600  # 100MB

# Agent Configuration
AGENT_CONFIDENCE_THRESHOLD=0.85
AGENT_CACHE_TTL_DAYS=30
AGENT_MAX_RETRIES=3
AGENT_RETRY_BACKOFF_BASE=2  # seconds

# Task Queue
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_TIME_LIMIT=600  # 10 minutes hard limit
CELERY_TASK_SOFT_TIME_LIMIT=540  # 9 minutes warning

# WebSocket
WS_HEARTBEAT_INTERVAL=10  # seconds
WS_MESSAGE_BUFFER_SIZE=10
WS_MAX_CONNECTIONS=1000

# Security
JWT_SECRET_KEY="your-secret-key-here-change-in-production"
JWT_ALGORITHM="HS256"
JWT_EXPIRATION_MINUTES=60

# Logging
LOG_FORMAT="json"  # or "text"
LOG_OUTPUT="stdout"  # or "file"
LOG_FILE_PATH="logs/app.log"
```

### Docker Compose Configuration

The `docker-compose.yml` is pre-configured for local development:

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:18-alpine
    environment:
      POSTGRES_USER: acmg_user
      POSTGRES_PASSWORD: acmg_pass
      POSTGRES_DB: acmg_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U acmg_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:8-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3

  neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/neo4j_pass
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p neo4j_pass 'RETURN 1'"]
      interval: 20s
      timeout: 10s
      retries: 5

  qdrant:
    image: qdrant/qdrant:v1.16.0-unprivileged  # Use gpu-nvidia variant if GPU available
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 15s
      timeout: 5s
      retries: 3

volumes:
  postgres_data:
  redis_data:
  minio_data:
  neo4j_data:
  qdrant_data:
```

### Database Migrations

#### Create New Migration

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new column to evidence_items"

# OR manually create empty migration
alembic revision -m "Custom migration"
```

#### Apply Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade to specific revision
alembic upgrade abc123

# Downgrade one revision
alembic downgrade -1

# View current revision
alembic current

# View migration history
alembic history
```

### Neo4j Schema Initialization

Run this once after Neo4j startup:

```bash
python scripts/init_neo4j_schema.py
```

This creates:
- Unique constraints on variant HGVS notation, phenotype HPO codes
- Indexes on frequently queried properties
- Example data for testing (optional)

## Development Workflow

### 1. Running Tests

```bash
# All tests
pytest

# Unit tests only (fast)
pytest tests/unit/

# Integration tests (requires Docker services)
pytest tests/integration/

# With coverage report
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/unit/domain/agents/test_evidence_agent.py -v
```

### 2. Code Quality Checks

```bash
# Linting
ruff check src/ tests/

# Formatting
ruff format src/ tests/

# Type checking
mypy src/
```

### 3. API Documentation

Once FastAPI is running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 4. Monitoring Celery Tasks

```bash
# Celery Flower (web-based monitoring)
celery -A src.infrastructure.tasks.celery_tasks flower --port=5555
```

Access Flower UI at http://localhost:5555

### 5. Database Exploration

```bash
# PostgreSQL via psql
psql postgresql://acmg_user:acmg_pass@localhost:5432/acmg_db

# Neo4j via Cypher Shell
cypher-shell -u neo4j -p neo4j_pass

# MinIO via mc CLI
mc alias set local http://localhost:9000 minioadmin minioadmin
mc ls local/acmg-documents
```

## Testing the Pipeline

### Upload a Test PDF

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer your-jwt-token" \
  -F "file=@test_data/sample_paper.pdf" \
  -F "priority=5"
```

**Response**:
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "document_id": "doc-uuid-1234",
  "status": "PENDING",
  "websocket_url": "ws://localhost:8000/ws/task/a1b2c3d4-e5f6-7890-abcd-ef1234567890/progress"
}
```

### Monitor Progress via WebSocket

```bash
# Using websocat CLI
websocat "ws://localhost:8000/ws/task/a1b2c3d4-e5f6-7890-abcd-ef1234567890/progress?token=your-jwt-token"
```

### Check Task Status

```bash
curl http://localhost:8000/api/v1/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer your-jwt-token"
```

### Retrieve Extracted Evidence

```bash
curl http://localhost:8000/api/v1/documents/doc-uuid-1234/evidence \
  -H "Authorization: Bearer your-jwt-token"
```

## Troubleshooting

### PostgreSQL Connection Issues

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# View PostgreSQL logs
docker logs acmg-postgres

# Test connection
psql postgresql://acmg_user:acmg_pass@localhost:5432/acmg_db -c "SELECT 1"
```

### Redis Connection Issues

```bash
# Test Redis connection
redis-cli ping
# Expected: PONG

# Check Redis info
redis-cli info

# Monitor Redis commands
redis-cli monitor
```

### Celery Worker Not Processing Tasks

```bash
# Check worker status
celery -A src.infrastructure.tasks.celery_tasks inspect active

# Check registered tasks
celery -A src.infrastructure.tasks.celery_tasks inspect registered

# Purge all pending tasks
celery -A src.infrastructure.tasks.celery_tasks purge

# Restart worker with verbose logging
celery -A src.infrastructure.tasks.celery_tasks worker --loglevel=debug
```

### MinerU Parsing Failures

```bash
# Check MinerU installation
python -c "import mineru; print(mineru.__version__)"

# Test MinerU directly
python -c "from src.infrastructure.adapters.mineru_adapter import MinerUAdapter; adapter = MinerUAdapter(); print(adapter.parse_pdf('test.pdf'))"

# Check PDF file permissions
ls -la test_data/sample_paper.pdf
```

### Neo4j Connection Issues

```bash
# Check Neo4j status
docker exec -it acmg-neo4j cypher-shell -u neo4j -p neo4j_pass "RETURN 1"

# View Neo4j logs
docker logs acmg-neo4j

# Check APOC plugin installation
docker exec -it acmg-neo4j cypher-shell -u neo4j -p neo4j_pass "CALL apoc.help('all')"
```

## Performance Tuning

### PostgreSQL Connection Pool

Adjust in `.env`:
```bash
DB_POOL_SIZE=50  # Increase for high concurrency
DB_MAX_OVERFLOW=20
```

### Celery Worker Concurrency

```bash
# Increase worker processes
CELERY_WORKER_CONCURRENCY=8

# OR use autoscale
celery -A src.infrastructure.tasks.celery_tasks worker --autoscale=10,3
```

### Redis Memory Limits

Add to `docker-compose.yml`:
```yaml
redis:
  command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

### Qdrant GPU Acceleration

Use GPU-enabled image in `docker-compose.yml`:
```yaml
qdrant:
  image: qdrant/qdrant:v1.16.0-gpu-nvidia
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

## Debugging Tips

### Enable SQL Query Logging

In `.env`:
```bash
SQLALCHEMY_ECHO=true
```

### Enable Agent Input/Output Logging

In `.env`:
```bash
AGENT_DEBUG_MODE=true
```

This logs full prompts and responses to `logs/agent_debug.log`.

### Celery Task Debugging

```python
# Add breakpoints in tasks
from celery import Task

class DebugTask(Task):
    def __call__(self, *args, **kwargs):
        import pdb; pdb.set_trace()
        return super().__call__(*args, **kwargs)

@celery_app.task(base=DebugTask)
def my_task():
    pass
```

## Next Steps

1. **Read Architecture Docs**: Review [plan.md](plan.md) for system architecture
2. **Explore Data Model**: See [data-model.md](data-model.md) for entity relationships
3. **API Contracts**: Study [contracts/openapi.yaml](contracts/openapi.yaml) for endpoint specifications
4. **Run Tests**: Execute `pytest` to verify setup
5. **Start Development**: Pick a task from [tasks.md](tasks.md) (generated by `/speckit.tasks`)

## Useful Commands Reference

```bash
# Start all services
docker-compose up -d && uvicorn app:app --reload & celery -A src.infrastructure.tasks.celery_tasks worker &

# Stop all services
docker-compose down && pkill -f uvicorn && pkill -f celery

# Reset database
docker-compose down -v && docker-compose up -d postgres && alembic upgrade head

# View logs
docker-compose logs -f  # All services
docker logs -f acmg-postgres  # Specific service

# Database backup
pg_dump postgresql://acmg_user:acmg_pass@localhost:5432/acmg_db > backup.sql

# Database restore
psql postgresql://acmg_user:acmg_pass@localhost:5432/acmg_db < backup.sql
```

## Support

- **Issues**: https://github.com/your-org/acmg-intelligence-system/issues
- **Slack**: #acmg-dev channel
- **Docs**: https://docs.acmg-system.example.com
