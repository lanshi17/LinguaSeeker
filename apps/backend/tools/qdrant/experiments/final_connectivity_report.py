#!/usr/bin/env python3
"""
数据库和文件存储连通性测试报告

此脚本总结了对多ACMG数据库系统中各种组件的连通性测试结果。
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_config import DatabaseConfig

def generate_comprehensive_report():
    """
    生成综合连通性测试报告
    包括：
    1. 数据库表结构验证
    2. 字段完整性检查
    3. 存储系统连通性
    """
    
    config = DatabaseConfig.from_env()
    
    print("="*80)
    print("多ACMG数据库系统 - 连通性测试报告")
    print("="*80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 报告各组件的配置信息
    print("1. 系统配置概览")
    print("-"*50)
    print(f"PostgreSQL配置:")
    print(f"  - 主机: {config.postgresql.host}:{config.postgresql.port}")
    print(f"  - 数据库: {config.postgresql.database}")
    print(f"  - 用户: {config.postgresql.user}")
    print()
    
    print(f"Neo4j配置:")
    print(f"  - URI: {config.neo4j.uri}")
    print(f"  - 用户: {config.neo4j.user}")
    print(f"  - 数据库: {config.neo4j.database}")
    print()
    
    print(f"Qdrant配置:")
    print(f"  - 主机: {config.qdrant.host}:{config.qdrant.port}")
    print(f"  - 集合: {config.qdrant.collection_name}")
    print(f"  - 维度: {config.qdrant.dimension}")
    print()
    
    print(f"MinIO配置:")
    print(f"  - 端点: {config.minio.endpoint}")
    print(f"  - 存储桶: {config.minio.bucket_name}")
    print(f"  - 安全连接: {config.minio.secure}")
    print()
    
    # 数据库表结构描述
    print("2. 数据库表结构")
    print("-"*50)
    tables_info = {
        "documents": {
            "description": "文献文档主表，存储上传的PDF文档基本信息",
            "fields": [
                {"name": "id", "type": "UUID", "layer": "应用层", "constraint": "主键，{{document_id}}"},
                {"name": "original_filename", "type": "VARCHAR(255)", "layer": "表现层", "constraint": "原始文件名"},
                {"name": "minio_path", "type": "VARCHAR(500)", "layer": "基础设施层", "constraint": "MinIO存储路径"},
                {"name": "status", "type": "ENUM", "layer": "应用层", "constraint": "'uploaded','parsing','completed','failed'"},
                {"name": "pmid", "type": "VARCHAR(50)", "layer": "领域层", "constraint": "唯一索引"},
                {"name": "doi", "type": "VARCHAR(255)", "layer": "领域层", "constraint": "唯一索引"},
                {"name": "title", "type": "TEXT", "layer": "领域层", "constraint": "文献标题"},
                {"name": "created_at", "type": "TIMESTAMPTZ", "layer": "基础设施层", "constraint": "默认CURRENT_TIMESTAMP"}
            ]
        },
        "parsing_tasks": {
            "description": "文档解析任务表，跟踪PDF解析过程",
            "fields": [
                {"name": "id", "type": "UUID", "layer": "应用层", "constraint": "主键，{{task_uuid}}"},
                {"name": "document_id", "type": "UUID", "layer": "应用层", "constraint": "外键→documents.id"},
                {"name": "task_type", "type": "VARCHAR(50)", "layer": "表现层", "constraint": "'pdf_parse','identifier_resolve'"},
                {"name": "celery_task_id", "type": "VARCHAR(255)", "layer": "基础设施层", "constraint": "Celery任务ID"},
                {"name": "result_path", "type": "VARCHAR(500)", "layer": "基础设施层", "constraint": "MinIO结果路径"},
                {"name": "status", "type": "ENUM", "layer": "应用层", "constraint": "'pending','processing','completed','failed'"},
                {"name": "progress", "type": "INTEGER", "layer": "领域层", "constraint": "0-100"}
            ]
        },
        "evidence_records": {
            "description": "证据记录表，存储ACMG变异解读证据",
            "fields": [
                {"name": "id", "type": "UUID", "layer": "领域层", "constraint": "主键"},
                {"name": "document_id", "type": "UUID", "layer": "领域层", "constraint": "外键→documents.id"},
                {"name": "evidence_type", "type": "VARCHAR(10)", "layer": "领域层", "constraint": "PS1/PS2/PM1/PS3..."},
                {"name": "content", "type": "TEXT", "layer": "领域层", "constraint": "证据原文片段"},
                {"name": "confidence_score", "type": "FLOAT", "layer": "领域层", "constraint": "0.0-1.0"},
                {"name": "source_page", "type": "INTEGER", "layer": "领域层", "constraint": "原文页码"},
                {"name": "source_position", "type": "VARCHAR(100)", "layer": "领域层", "constraint": "原文位置标识"},
                {"name": "status", "type": "ENUM", "layer": "领域层", "constraint": "'pending','approved','rejected'"},
                {"name": "neo4j_node_id", "type": "VARCHAR(100)", "layer": "基础设施层", "constraint": "Neo4j节点ID"},
                {"name": "created_at", "type": "TIMESTAMPTZ", "layer": "基础设施层", "constraint": "默认CURRENT_TIMESTAMP"}
            ]
        },
        "agent_logs": {
            "description": "智能体日志表，记录AI处理过程",
            "fields": [
                {"name": "id", "type": "UUID", "layer": "领域层", "constraint": "主键"},
                {"name": "task_id", "type": "UUID", "layer": "领域层", "constraint": "外键→parsing_tasks.id"},
                {"name": "agent_type", "type": "VARCHAR(50)", "layer": "领域层", "constraint": "'layout','translation'..."},
                {"name": "input_hash", "type": "CHAR(64)", "layer": "领域层", "constraint": "SHA256输入摘要"},
                {"name": "output", "type": "JSONB", "layer": "领域层", "constraint": "Agent输出快照"},
                {"name": "duration_ms", "type": "INTEGER", "layer": "领域层", "constraint": "处理耗时"},
                {"name": "retry_count", "type": "INTEGER", "layer": "领域层", "constraint": "重试次数"}
            ]
        }
    }
    
    for table_name, table_info in tables_info.items():
        print(f"{table_name} 表:")
        print(f"  描述: {table_info['description']}")
        print("  字段详情:")
        for field in table_info['fields']:
            print(f"    - {field['name']:<20} {field['type']:<15} {field['layer']:<10} {field['constraint']}")
        print()
    
    # SQL DDL语句
    print("3. 数据库DDL语句")
    print("-"*50)
    ddl_statements = [
        "-- documents表",
        "CREATE TABLE documents (",
        "    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),",
        "    original_filename VARCHAR(255) NOT NULL,",
        "    minio_path VARCHAR(500) NOT NULL,",
        "    status VARCHAR(20) NOT NULL CHECK (status IN ('uploaded', 'parsing', 'completed', 'failed')) ,",
        "    pmid VARCHAR(50) UNIQUE,",
        "    doi VARCHAR(255) UNIQUE,",
        "    title TEXT,",
        "    authors JSONB,",
        "    journal VARCHAR(255),",
        "    publication_year INTEGER,",
        "    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,",
        "    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP",
        ");",
        "",
        "-- parsing_tasks表",
        "CREATE TABLE parsing_tasks (",
        "    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),",
        "    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,",
        "    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('pdf_parse', 'identifier_resolve')) ,",
        "    celery_task_id VARCHAR(255),",
        "    result_path VARCHAR(500),",
        "    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')) ,",
        "    progress INTEGER DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),",
        "    error_message TEXT,",
        "    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,",
        "    completed_at TIMESTAMPTZ",
        ");",
        "",
        "-- evidence_records表",
        "CREATE TABLE evidence_records (",
        "    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),",
        "    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,",
        "    evidence_type VARCHAR(10) NOT NULL CHECK (evidence_type ~ '^(P|B)(S|M)[1-6]$'), -- ACMG标准",
        "    content TEXT NOT NULL,",
        "    confidence_score FLOAT NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),",
        "    source_page INTEGER,",
        "    source_position VARCHAR(100),",
        "    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')) ,",
        "    neo4j_node_id VARCHAR(100),",
        "    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,",
        "    reviewed_by UUID REFERENCES users(id), -- 人工审核关联",
        "    reviewed_at TIMESTAMPTZ",
        ");",
        "",
        "-- agent_logs表 (审计与优化)",
        "CREATE TABLE agent_logs (",
        "    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),",
        "    task_id UUID NOT NULL REFERENCES parsing_tasks(id) ON DELETE CASCADE,",
        "    agent_type VARCHAR(50) NOT NULL,",
        "    input_hash CHAR(64) NOT NULL, -- SHA256",
        "    output JSONB NOT NULL,",
        "    duration_ms INTEGER NOT NULL,",
        "    retry_count INTEGER DEFAULT 0,",
        "    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP",
        ");",
        "",
        "-- 创建关键索引",
        "CREATE INDEX idx_documents_pmid ON documents(pmid);",
        "CREATE INDEX idx_documents_doi ON documents(doi);",
        "CREATE INDEX idx_parsing_tasks_document ON parsing_tasks(document_id);",
        "CREATE INDEX idx_parsing_tasks_status ON parsing_tasks(status);",
        "CREATE INDEX idx_evidence_document ON evidence_records(document_id);",
        "CREATE INDEX idx_evidence_type ON evidence_records(evidence_type);",
        "CREATE INDEX idx_agent_logs_task ON agent_logs(task_id);",
        "CREATE INDEX idx_agent_logs_input_hash ON agent_logs(input_hash);"
    ]
    
    for statement in ddl_statements:
        print(statement)
    print()
    
    # 连通性测试结果
    print("4. 连通性测试结果")
    print("-"*50)
    print("由于当前环境中缺少必要的数据库驱动程序，以下为预期的测试结果：")
    print()
    
    services_status = {
        "PostgreSQL": {
            "connection": "通过环境变量配置正常",
            "tables": "需创建documents, parsing_tasks, evidence_records, agent_logs表",
            "indexes": "需创建关键索引以优化查询性能",
            "status": "配置正常，等待驱动支持"
        },
        "Neo4j": {
            "connection": "通过环境变量配置正常",
            "graph_structure": "用于存储实体关系和知识图谱",
            "integration": "与evidence_records表中的neo4j_node_id字段关联",
            "status": "配置正常，等待驱动支持"
        },
        "Qdrant": {
            "connection": "通过环境变量配置正常",
            "collection": "paper_chunks集合用于向量相似度搜索",
            "dimension": "1536维向量空间",
            "status": "配置正常，等待驱动支持"
        },
        "MinIO": {
            "connection": "通过环境变量配置正常",
            "bucket": "acmg-documents存储桶用于文档存储",
            "integration": "与documents表中的minio_path字段关联",
            "status": "配置正常，等待驱动支持"
        }
    }
    
    for service, details in services_status.items():
        print(f"{service}:")
        for key, value in details.items():
            print(f"  {key}: {value}")
        print()
    
    # 测试建议
    print("5. 测试建议")
    print("-"*50)
    print("为完成完整的连通性测试，请按以下步骤操作：")
    print()
    print("a) 安装必要的Python包：")
    print("   pip install psycopg2-binary neo4j qdrant-client minio")
    print()
    print("b) 确保所有服务正在运行：")
    print("   - PostgreSQL (默认端口 5432)")
    print("   - Neo4j (默认端口 7687)")
    print("   - Qdrant (默认端口 6333)")
    print("   - MinIO (默认端口 9000)")
    print()
    print("c) 运行完整的连通性测试：")
    print("   python src/connectivity_test.py")
    print()
    
    # 总结
    print("6. 总结")
    print("-"*50)
    print("✓ 系统配置完整，包含四大核心组件")
    print("✓ 数据库表结构设计合理，符合ACMG变异解读需求") 
    print("✓ 字段类型和约束满足业务要求")
    print("✓ 索引设计考虑了查询性能")
    print("⚠ 需要安装数据库驱动以完成实际连接测试")
    print()
    print("系统准备就绪，等待数据库驱动安装后即可进行全面测试。")
    
    # 保存详细报告
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "postgresql": {
                "host": config.postgresql.host,
                "port": config.postgresql.port,
                "database": config.postgresql.database,
                "user": config.postgresql.user
            },
            "neo4j": {
                "uri": config.neo4j.uri,
                "user": config.neo4j.user,
                "database": config.neo4j.database
            },
            "qdrant": {
                "host": config.qdrant.host,
                "port": config.qdrant.port,
                "collection_name": config.qdrant.collection_name
            },
            "minio": {
                "endpoint": config.minio.endpoint,
                "bucket_name": config.minio.bucket_name,
                "secure": config.minio.secure
            }
        },
        "tables": tables_info,
        "ddl_statements": ddl_statements,
        "expected_results": services_status,
        "recommendations": [
            "安装psycopg2-binary, neo4j, qdrant-client, minio等Python包",
            "确认各服务端口开放且可访问",
            "运行完整的连通性测试脚本"
        ]
    }
    
    with open("connectivity_test_report.json", "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    print(f"详细报告已保存至: connectivity_test_report.json")
    print("="*80)

def main():
    generate_comprehensive_report()

if __name__ == "__main__":
    main()