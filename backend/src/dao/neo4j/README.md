# Neo4j DAO

> Neo4j graph database data access layer. **Currently a placeholder** — not yet implemented. Planned for knowledge graph relationships between genes, variants, diseases, and evidence.

## Status

This sub-package contains only `__init__.py`. No repository or connection code has been implemented yet.

## Planned Purpose

When implemented, this module will provide:
- Async Neo4j driver wrapper using `neo4j` Python SDK
- Cypher query repositories for gene-variant-disease relationships
- Entity graph traversal for evidence linking
- Bulk import from standardized entity data

## Configuration

Neo4j connection settings are defined in `src.core.config`:

| Env Var | Default | Description |
|---------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Bolt protocol endpoint |
| `NEO4J_USER` | `neo4j` | Username |
| `NEO4J_PASSWORD` | `""` | Password |
| `NEO4J_DATABASE` | `neo4j` | Database name |
| `NEO4J_MAX_CONNECTION_LIFETIME` | `3600` | Connection lifetime (seconds) |
| `NEO4J_MAX_CONNECTION_POOL_SIZE` | `50` | Pool size |

Access via `from src.core.config import get_config; cfg = get_config().neo4j`.
