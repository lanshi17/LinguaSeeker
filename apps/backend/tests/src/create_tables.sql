-- 创建ACMG数据库表结构
-- 包含documents, parsing_tasks, evidence_records, agent_logs表

-- 创建documents表
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_filename VARCHAR(255) NOT NULL,
    minio_path VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('uploaded', 'parsing', 'completed', 'failed')),
    pmid VARCHAR(50) UNIQUE,
    doi VARCHAR(255) UNIQUE,
    title TEXT,
    authors JSONB,
    journal VARCHAR(255),
    publication_year INTEGER,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 创建parsing_tasks表
CREATE TABLE IF NOT EXISTS parsing_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('pdf_parse', 'identifier_resolve')),
    celery_task_id VARCHAR(255),
    result_path VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    progress INTEGER DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

-- 创建evidence_records表
CREATE TABLE IF NOT EXISTS evidence_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    evidence_type VARCHAR(10) NOT NULL CHECK (evidence_type ~ '^(P|B)(S|M)[1-6]$'), -- ACMG标准
    content TEXT NOT NULL,
    confidence_score FLOAT NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
    source_page INTEGER,
    source_position VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    neo4j_node_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    reviewed_by UUID REFERENCES users(id), -- 人工审核关联
    reviewed_at TIMESTAMPTZ
);

-- 创建agent_logs表 (审计与优化)
CREATE TABLE IF NOT EXISTS agent_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES parsing_tasks(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL,
    input_hash CHAR(64) NOT NULL, -- SHA256
    output JSONB NOT NULL,
    duration_ms INTEGER NOT NULL,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 创建关键索引
CREATE INDEX IF NOT EXISTS idx_documents_pmid ON documents(pmid);
CREATE INDEX IF NOT EXISTS idx_documents_doi ON documents(doi);
CREATE INDEX IF NOT EXISTS idx_parsing_tasks_document ON parsing_tasks(document_id);
CREATE INDEX IF NOT EXISTS idx_parsing_tasks_status ON parsing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_evidence_document ON evidence_records(document_id);
CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence_records(evidence_type);
CREATE INDEX IF NOT EXISTS idx_agent_logs_task ON agent_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_agent_logs_input_hash ON agent_logs(input_hash);

-- 插入示例数据
-- 文档记录
INSERT INTO documents (original_filename, minio_path, status, pmid, doi, title, publication_year) VALUES
('sample1.pdf', 'documents/sample1.pdf', 'completed', '12345678', '10.1000/journal.v1.123', 'Sample Research Paper 1', 2023),
('sample2.pdf', 'documents/sample2.pdf', 'parsing', '12345679', '10.1000/journal.v1.124', 'Sample Research Paper 2', 2024);

-- 解析任务记录
INSERT INTO parsing_tasks (document_id, task_type, status, progress) VALUES
((SELECT id FROM documents WHERE pmid='12345678'), 'pdf_parse', 'completed', 100),
((SELECT id FROM documents WHERE pmid='12345679'), 'identifier_resolve', 'processing', 75);

-- 证据记录
INSERT INTO evidence_records (document_id, evidence_type, content, confidence_score, source_page, status) VALUES
((SELECT id FROM documents WHERE pmid='12345678'), 'PS1', 'Pathogenic variant found in BRCA1 gene', 0.95, 15, 'approved'),
((SELECT id FROM documents WHERE pmid='12345678'), 'PM2', 'Variant absent from controls in gnomAD database', 0.85, 16, 'pending');

-- 代理日志记录
INSERT INTO agent_logs (task_id, agent_type, input_hash, output, duration_ms) VALUES
((SELECT id FROM parsing_tasks WHERE document_id = (SELECT id FROM documents WHERE pmid='12345678')), 'layout', 'a1b2c3d4e5f67890', '{"pages": 20, "tables": 5}', 1200);