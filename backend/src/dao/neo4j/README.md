# Neo4j DAO

> Neo4j graph database data access layer. **Currently a placeholder** -- not yet implemented. Planned for knowledge graph relationships between genes, variants, diseases, and evidence.

## Status

This sub-package contains only `__init__.py`. No repository, connection, or configuration code has been implemented yet. No Neo4j configuration exists in `src.core.config`.

## Planned Purpose

When implemented, this module will provide:

- Async Neo4j driver wrapper using `neo4j` Python SDK
- Cypher query repositories for gene-variant-disease relationships
- Entity graph traversal for evidence linking
- Bulk import from standardized entity data
