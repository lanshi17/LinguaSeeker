-- Cleanup orphan records to reduce inconsistencies

-- Remove entity-document links with missing parent records
DELETE FROM entity_document_mapping edm
WHERE NOT EXISTS (
    SELECT 1 FROM documents d WHERE d.document_id = edm.document_id
) OR NOT EXISTS (
    SELECT 1 FROM entities e WHERE e.entity_id = edm.entity_id
);

-- Remove tasks with missing documents
DELETE FROM tasks t
WHERE NOT EXISTS (
    SELECT 1 FROM documents d WHERE d.document_id = t.document_id
);

-- Remove graph cache nodes with missing names (optional cleanup)
DELETE FROM graph_nodes_cache
WHERE name IS NULL AND description IS NULL;

-- Remove graph cache edges with missing endpoints (optional cleanup)
DELETE FROM graph_edges_cache
WHERE start_node_id IS NULL OR end_node_id IS NULL;
