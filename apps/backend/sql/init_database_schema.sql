-- Database schema initialization script

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 2. documents
CREATE TABLE IF NOT EXISTS documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500),
    pmid VARCHAR(64),
    local_path TEXT,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 3. tasks
CREATE TABLE IF NOT EXISTS tasks (
    task_id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    progress DOUBLE PRECISION,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    workflow_status VARCHAR(80),
    processing_steps JSONB,
    file_size_bytes BIGINT,
    processing_duration_seconds DOUBLE PRECISION,
    error_details JSONB
);

-- 3b. task_logs
CREATE TABLE IF NOT EXISTS task_logs (
    log_id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(task_id) ON DELETE SET NULL,
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL,
    category VARCHAR(100),
    payload JSONB,
    missing_fields_detail JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 3c. task_requests
CREATE TABLE IF NOT EXISTS task_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_form_text TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'queued' NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_task_requests_status ON task_requests (status);

-- 3d. paper_tasks
CREATE TABLE IF NOT EXISTS paper_tasks (
    paper_task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES task_requests(request_id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(document_id) ON DELETE SET NULL,
    original_filename VARCHAR(500),
    file_hash VARCHAR(64),
    status VARCHAR(50) DEFAULT 'queued' NOT NULL,
    error_code VARCHAR(50),
    duplicate_of UUID REFERENCES paper_tasks(paper_task_id) ON DELETE SET NULL,
    celery_task_id VARCHAR(100),
    fulltext_unavailable VARCHAR(10) DEFAULT 'false' NOT NULL,
    warning_codes JSONB,
    node_trace JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    workflow_status VARCHAR(80),
    processing_steps JSONB,
    file_size_bytes BIGINT,
    processing_duration_seconds DOUBLE PRECISION,
    error_details JSONB
);

CREATE INDEX IF NOT EXISTS ix_paper_tasks_request_id ON paper_tasks (request_id);
CREATE INDEX IF NOT EXISTS ix_paper_tasks_status ON paper_tasks (status);
CREATE INDEX IF NOT EXISTS ix_paper_tasks_file_hash ON paper_tasks (file_hash);
CREATE INDEX IF NOT EXISTS ix_paper_tasks_celery_task_id ON paper_tasks (celery_task_id);
CREATE INDEX IF NOT EXISTS ix_paper_tasks_workflow_status ON paper_tasks (workflow_status);
CREATE INDEX IF NOT EXISTS ix_tasks_workflow_status ON tasks (workflow_status);

-- 3e. paper_task_logs
CREATE TABLE IF NOT EXISTS paper_task_logs (
    log_id SERIAL PRIMARY KEY,
    paper_task_id UUID NOT NULL REFERENCES paper_tasks(paper_task_id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL,
    node VARCHAR(50),
    error_code VARCHAR(50),
    message TEXT,
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_paper_task_logs_paper_task_id ON paper_task_logs (paper_task_id);
CREATE INDEX IF NOT EXISTS ix_paper_task_logs_status ON paper_task_logs (status);

-- 3f. sentence_alignments
CREATE TABLE IF NOT EXISTS sentence_alignments (
    alignment_id SERIAL PRIMARY KEY,
    paper_task_id UUID NOT NULL REFERENCES paper_tasks(paper_task_id) ON DELETE CASCADE,
    source_sentence TEXT NOT NULL,
    en_sentence TEXT NOT NULL,
    source_start INTEGER,
    source_end INTEGER,
    en_start INTEGER,
    en_end INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_sentence_alignments_paper_task_id ON sentence_alignments (paper_task_id);

-- 4. entities
CREATE TABLE IF NOT EXISTS entities (
    entity_id SERIAL PRIMARY KEY,
    type VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    standardized_name VARCHAR(255),
    metadata JSONB
);

-- 5. entity_document_mapping
CREATE TABLE IF NOT EXISTS entity_document_mapping (
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    confidence_score DOUBLE PRECISION,
    mentions JSONB,
    PRIMARY KEY (document_id, entity_id)
);

-- 6. graph_nodes_cache
CREATE TABLE IF NOT EXISTS graph_nodes_cache (
    cache_id SERIAL PRIMARY KEY,
    node_type VARCHAR(100) NOT NULL,
    neo4j_node_id INTEGER NOT NULL,
    name VARCHAR(255),
    description TEXT,
    properties JSONB
);

-- 7. graph_edges_cache
CREATE TABLE IF NOT EXISTS graph_edges_cache (
    cache_id SERIAL PRIMARY KEY,
    neo4j_relationship_id INTEGER NOT NULL,
    start_node_id INTEGER NOT NULL,
    end_node_id INTEGER NOT NULL,
    relationship_type VARCHAR(100) NOT NULL,
    properties JSONB
);

-- 8. clinvar_variations (ClinVar 基础变异表)
CREATE TABLE IF NOT EXISTS clinvar_variations (
    variation_id BIGINT PRIMARY KEY,
    preferred_name VARCHAR(1000),
    primary_hgvs VARCHAR(1000),
    gene_symbol VARCHAR(100),
    transcript_id VARCHAR(100),
    clinvar_accession VARCHAR(32),
    review_status VARCHAR(200),
    clinical_significance VARCHAR(200),
    last_evaluated_at TIMESTAMP WITH TIME ZONE,
    synonyms JSONB,
    hgvs_list JSONB,
    trait_names JSONB,
    attributes JSONB,
    citations_synced_at TIMESTAMP WITH TIME ZONE,
    scorecards_synced_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 9. variation_citations (ClinVar/内部文献映射)
CREATE TABLE IF NOT EXISTS variation_citations (
    citation_id SERIAL PRIMARY KEY,
    variation_id BIGINT NOT NULL REFERENCES clinvar_variations(variation_id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL,
    pmid VARCHAR(32),
    document_id UUID REFERENCES documents(document_id) ON DELETE CASCADE,
    evidence_strength VARCHAR(100),
    notes TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 10. clingen_evidence_profiles (ClinGen EviRepo 评分表)
CREATE TABLE IF NOT EXISTS clingen_evidence_profiles (
    profile_id SERIAL PRIMARY KEY,
    variation_id BIGINT NOT NULL REFERENCES clinvar_variations(variation_id) ON DELETE CASCADE,
    assertion_id VARCHAR(200) NOT NULL,
    disease_label VARCHAR(500),
    disease_mondo VARCHAR(100),
    expert_panel VARCHAR(255),
    classification VARCHAR(100),
    published_at DATE,
    evidence_codes JSONB,
    guideline_label VARCHAR(500),
    score_breakdown JSONB,
    raw_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    UNIQUE (variation_id, assertion_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_pmid ON documents(pmid);
CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_document_id ON tasks(document_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_document_id ON task_logs(document_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_status ON task_logs(status);

CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type_name ON entities(type, name);

CREATE INDEX IF NOT EXISTS idx_entity_doc_mapping_document_id ON entity_document_mapping(document_id);
CREATE INDEX IF NOT EXISTS idx_entity_doc_mapping_entity_id ON entity_document_mapping(entity_id);

CREATE INDEX IF NOT EXISTS idx_graph_nodes_cache_node_type ON graph_nodes_cache(node_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_nodes_cache_neo4j_node_id ON graph_nodes_cache(neo4j_node_id);

CREATE INDEX IF NOT EXISTS idx_graph_edges_cache_relationship_type ON graph_edges_cache(relationship_type);
CREATE INDEX IF NOT EXISTS idx_graph_edges_cache_start_node_id ON graph_edges_cache(start_node_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_cache_end_node_id ON graph_edges_cache(end_node_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_edges_cache_neo4j_rel_id ON graph_edges_cache(neo4j_relationship_id);

CREATE INDEX IF NOT EXISTS idx_clinvar_variations_gene_symbol ON clinvar_variations(gene_symbol);
CREATE INDEX IF NOT EXISTS idx_clinvar_variations_primary_hgvs ON clinvar_variations(primary_hgvs);
CREATE INDEX IF NOT EXISTS idx_variation_citations_variation ON variation_citations(variation_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_variation_citations_pmid ON variation_citations(variation_id, source, pmid) WHERE pmid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_variation_citations_document ON variation_citations(variation_id, source, document_id) WHERE document_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_clingen_profiles_variation ON clingen_evidence_profiles(variation_id);
CREATE INDEX IF NOT EXISTS idx_clingen_profiles_disease ON clingen_evidence_profiles(disease_mondo);

-- 8. evidence_records (证据强度分类表)
CREATE TABLE IF NOT EXISTS evidence_records (
    evidence_id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    gene_symbol VARCHAR(100),
    variant_hgvs_c VARCHAR(500),
    variant_hgvs_p VARCHAR(500),
    protein_change VARCHAR(500),
    clinvar_variation_id BIGINT REFERENCES clinvar_variations(variation_id),
    transcript_id VARCHAR(100),
    reference_genome VARCHAR(50),
    disease_name VARCHAR(500),
    icd10_code VARCHAR(50),
    species VARCHAR(100),
    phenotype TEXT,
    evidence_strength VARCHAR(50),
    evidence_classification VARCHAR(100),
    overall_confidence DOUBLE PRECISION,
    arbitration_score DOUBLE PRECISION,
    is_valid VARCHAR(10) DEFAULT 'false',
    acmg_levels JSONB,
    extracted_fields JSONB,
    ps3_evidence JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Evidence records indexes for Variation/Gene/Protein Change retrieval
CREATE INDEX IF NOT EXISTS idx_evidence_gene_symbol ON evidence_records(gene_symbol);
CREATE INDEX IF NOT EXISTS idx_evidence_variant_hgvs_c ON evidence_records(variant_hgvs_c);
CREATE INDEX IF NOT EXISTS idx_evidence_variant_hgvs_p ON evidence_records(variant_hgvs_p);
CREATE INDEX IF NOT EXISTS idx_evidence_protein_change ON evidence_records(protein_change);
CREATE INDEX IF NOT EXISTS idx_evidence_clinvar_variation ON evidence_records(clinvar_variation_id);
CREATE INDEX IF NOT EXISTS idx_evidence_disease_name ON evidence_records(disease_name);
CREATE INDEX IF NOT EXISTS idx_evidence_icd10_code ON evidence_records(icd10_code);
CREATE INDEX IF NOT EXISTS idx_evidence_strength ON evidence_records(evidence_strength);
CREATE INDEX IF NOT EXISTS idx_evidence_classification ON evidence_records(evidence_classification);
CREATE INDEX IF NOT EXISTS idx_evidence_document_id ON evidence_records(document_id);
-- Composite indexes for efficient gene+variant and gene+protein_change retrieval
CREATE INDEX IF NOT EXISTS idx_evidence_gene_variant ON evidence_records(gene_symbol, variant_hgvs_c);
CREATE INDEX IF NOT EXISTS idx_evidence_gene_protein ON evidence_records(gene_symbol, protein_change);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_evidence_records_updated_at BEFORE UPDATE ON evidence_records
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_clinvar_variations_updated_at BEFORE UPDATE ON clinvar_variations
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_clingen_profiles_updated_at BEFORE UPDATE ON clingen_evidence_profiles
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- View: document task status
CREATE OR REPLACE VIEW document_task_status AS
SELECT
    d.document_id,
    d.title,
    d.status as document_status,
    t.type as task_type,
    t.status as task_status,
    t.progress,
    t.created_at as task_created_at
FROM documents d
LEFT JOIN tasks t ON d.document_id = t.document_id;

-- View: evidence summary with document info
CREATE OR REPLACE VIEW evidence_summary AS
SELECT
    er.evidence_id,
    er.gene_symbol,
    er.variant_hgvs_c,
    er.variant_hgvs_p,
    er.protein_change,
    er.clinvar_variation_id,
    er.disease_name,
    er.evidence_strength,
    er.evidence_classification,
    er.overall_confidence,
    er.arbitration_score,
    er.is_valid,
    er.acmg_levels,
    d.title AS document_title,
    d.pmid,
    d.file_hash,
    er.created_at
FROM evidence_records er
JOIN documents d ON er.document_id = d.document_id;

-- View: multi-document evidence for gene/variant retrieval
CREATE OR REPLACE VIEW multi_document_evidence AS
SELECT
    er.gene_symbol,
    er.variant_hgvs_c,
    er.clinvar_variation_id,
    er.protein_change,
    COUNT(DISTINCT er.document_id) AS document_count,
    array_agg(DISTINCT d.title) AS document_titles,
    array_agg(DISTINCT er.evidence_strength) AS evidence_strengths,
    MAX(er.overall_confidence) AS max_confidence,
    bool_or(er.is_valid = 'true') AS has_valid_evidence
FROM evidence_records er
JOIN documents d ON er.document_id = d.document_id
WHERE er.gene_symbol IS NOT NULL
GROUP BY er.gene_symbol, er.variant_hgvs_c, er.clinvar_variation_id, er.protein_change;

SELECT 'Database schema initialized successfully!' AS message;
