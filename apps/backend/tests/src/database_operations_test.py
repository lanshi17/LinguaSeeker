#!/usr/bin/env python3
"""
数据库操作测试类
提供对PostgreSQL数据库的CRUD操作测试功能
"""

import uuid
import json
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_config import DatabaseConfig

class DatabaseOperationsTester:
    def __init__(self):
        self.config = DatabaseConfig.from_env()
        self.connection = None
        self.cursor = None
        
        # ACMG证据类型列表
        self.acmg_types = [
            'PS1', 'PS2', 'PS3', 'PS4', 'PM1', 'PM2', 'PM3', 'PM4', 'PM5', 'PM6',
            'PP1', 'PP2', 'PP3', 'PP4', 'PP5', 'BA1', 'BS1', 'BS2', 'BS3', 'BS4',
            'BP1', 'BP2', 'BP3', 'BP4', 'BP5', 'BP6', 'BP7'
        ]
        
        # 模拟数据
        self.first_names = ['James', 'Mary', 'John', 'Patricia', 'Robert', 'Jennifer', 'Michael', 'Linda', 'William', 'Elizabeth']
        self.last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
        self.journals = [
            'Nature Genetics', 'New England Journal of Medicine', 
            'American Journal of Human Genetics', 'Genetics in Medicine',
            'Human Mutation', 'Clinical Genetics', 'European Journal of Human Genetics',
            'Journal of Medical Genetics', 'Genetic Medicine', 'BMC Medical Genetics'
        ]
        self.titles = [
            'Novel Variants in BRCA1 Associated with Hereditary Breast Cancer',
            'Genetic Analysis of Lynch Syndrome Families',
            'Whole Exome Sequencing Identifies Pathogenic Mutations in Cardiomyopathy',
            'ACMG Recommendations for Variant Classification in Clinical Practice',
            'Systematic Review of Genetic Testing Guidelines for Rare Diseases',
            'Phenotype-Genotype Correlations in Neurofibromatosis Type 1',
            'Functional Validation of Uncertain Significance Variants in COL1A1',
            'Population-Specific Allele Frequencies in Genetic Disease Screening',
            'Clinical Utility of Multi-Gene Panel Testing for Hereditary Cancer',
            'Evidence-Based Approach to ACMG Secondary Findings Implementation'
        ]
        self.sentences = [
            'The study identified a novel pathogenic variant in the tested gene.',
            'Statistical analysis confirmed significant association with disease phenotype.',
            'Functional studies demonstrated loss of protein function consistent with pathogenicity.',
            'Segregation analysis supports co-occurrence of variant with disease in affected family members.',
            'Computational predictions suggest deleterious effect on protein structure and function.',
            'Literature review revealed similar variants previously classified as pathogenic.',
            'Case-control studies showed enrichment of variant in cases versus controls.',
            'Gene-specific criteria were applied to support classification of variant of uncertain significance.',
            'Clinical correlation supports pathogenic role of identified genetic alteration.',
            'Family history strongly supports genetic etiology of observed phenotype.'
        ]

    def connect_db(self):
        """连接到数据库"""
        try:
            import psycopg2
            
            # 使用修复后的连接参数
            self.connection = psycopg2.connect(
                host=self.config.postgresql.host,
                port=self.config.postgresql.port,
                database=self.config.postgresql.database,
                user="yangzs",  # 修复后的用户名
                password="***REMOVED***"  # 修复后的密码
            )
            self.cursor = self.connection.cursor()
            print("✓ Connected to PostgreSQL database")
            return True
        except ImportError:
            print("⚠ psycopg2 not available")
            return False
        except Exception as e:
            print(f"✗ Failed to connect to database: {str(e)}")
            return False

    def disconnect_db(self):
        """断开数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        print("✓ Disconnected from database")

    def generate_sentence(self, nb_words=8):
        """生成模拟句子"""
        words = []
        for _ in range(nb_words):
            words.append(random.choice(self.sentences).split()[0])
        return ' '.join(words) + '.'

    def generate_name(self):
        """生成模拟姓名"""
        return f"{random.choice(self.first_names)} {random.choice(self.last_names)}"

    def create_tables_if_not_exists(self):
        """创建表（如果不存在）"""
        print("Checking and creating tables if needed...")
        
        try:
            # 读取创建表的SQL脚本
            with open('src/create_tables.sql', 'r') as f:
                sql_script = f.read()
            
            # 执行SQL脚本
            self.cursor.execute(sql_script)
            self.connection.commit()
            print("✓ Tables checked/created successfully")
            return True
        except FileNotFoundError:
            print("⚠ create_tables.sql not found, using inline SQL")
            # 内联创建表的SQL
            create_sql = """
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
            """
            
            self.cursor.execute(create_sql)
            self.connection.commit()
            print("✓ Tables created successfully with inline SQL")
            return True
        except Exception as e:
            print(f"✗ Error creating tables: {str(e)}")
            return False

    def test_create_operations(self, num_records=5):
        """测试创建操作"""
        print(f"Testing CREATE operations with {num_records} records each...")
        
        try:
            # 插入文档记录
            print("  Inserting documents...")
            document_ids = []
            for i in range(num_records):
                doc_id = str(uuid.uuid4())
                year = random.randint(2020, 2024)
                month = random.randint(1, 12)
                day = random.randint(1, 28)
                created_at = datetime(year, month, day)
                
                self.cursor.execute("""
                    INSERT INTO documents (
                        id, original_filename, minio_path, status, pmid, doi, 
                        title, authors, journal, publication_year, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    doc_id,
                    f"ACMG_Study_{random.randint(1000, 9999)}.pdf",
                    f"documents/{doc_id[:8]}/{f'ACMG_Study_{random.randint(1000, 9999)}.pdf'}",
                    random.choice(['uploaded', 'parsing', 'completed', 'failed']),
                    f"{random.randint(10000000, 99999999)}",
                    f"10.1000/journal.v{random.randint(1, 20)}.{random.randint(1, 100)}",
                    random.choice(self.titles),
                    json.dumps([self.generate_name() for _ in range(random.randint(1, 6))]),
                    random.choice(self.journals),
                    year,
                    created_at,
                    created_at + timedelta(days=random.randint(1, 30))
                ))
                
                inserted_id = self.cursor.fetchone()[0]
                document_ids.append(inserted_id)
            
            # 为每个文档创建解析任务
            print("  Inserting parsing tasks...")
            task_ids = []
            for doc_id in document_ids:
                task_id = str(uuid.uuid4())
                
                self.cursor.execute("""
                    INSERT INTO parsing_tasks (
                        id, document_id, task_type, celery_task_id, result_path, 
                        status, progress, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    task_id,
                    doc_id,
                    random.choice(['pdf_parse', 'identifier_resolve']),
                    f"task-{uuid.uuid4()}",
                    f"results/{task_id[:8]}/parsed_data.json",
                    random.choice(['pending', 'processing', 'completed', 'failed']),
                    random.randint(0, 100),
                    datetime.now()
                ))
                
                inserted_id = self.cursor.fetchone()[0]
                task_ids.append(inserted_id)
            
            # 为每个文档创建证据记录
            print("  Inserting evidence records...")
            for doc_id in document_ids:
                for _ in range(random.randint(3, 7)):  # 每个文档3-7条证据
                    evidence_id = str(uuid.uuid4())
                    created_at = datetime.now() - timedelta(days=random.randint(1, 30))
                    
                    self.cursor.execute("""
                        INSERT INTO evidence_records (
                            id, document_id, evidence_type, content, confidence_score, 
                            source_page, source_position, status, neo4j_node_id, 
                            created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        evidence_id,
                        doc_id,
                        random.choice(self.acmg_types),
                        self.generate_sentence(nb_words=12),
                        round(random.uniform(0.5, 1.0), 2),
                        random.randint(1, 50),
                        f"Page {random.randint(1, 50)}, Column {random.choice(['Left', 'Right'])}",
                        random.choice(['pending', 'approved', 'rejected']),
                        f"node_{random.randint(1000, 9999)}",
                        created_at
                    ))
            
            # 为每个任务创建代理日志
            print("  Inserting agent logs...")
            for task_id in task_ids:
                for _ in range(random.randint(1, 3)):  # 每个任务1-3条日志
                    log_id = str(uuid.uuid4())
                    created_at = datetime.now() - timedelta(minutes=random.randint(1, 60))
                    
                    self.cursor.execute("""
                        INSERT INTO agent_logs (
                            id, task_id, agent_type, input_hash, output, 
                            duration_ms, retry_count, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        log_id,
                        task_id,
                        random.choice(['layout', 'translation', 'extraction', 'classification', 'validation']),
                        ''.join([random.choice('abcdef0123456789') for _ in range(64)]),
                        json.dumps({
                            'operation': random.choice(['parse', 'extract', 'validate', 'classify']),
                            'result': 'success' if random.random() > 0.1 else 'failed',
                            'details': {
                                'processed_pages': random.randint(1, 20),
                                'entities_found': random.randint(0, 15),
                                'confidence_avg': round(random.uniform(0.6, 0.95), 2)
                            }
                        }),
                        random.randint(100, 5000),
                        random.randint(0, 3),
                        created_at
                    ))
            
            # 提交事务
            self.connection.commit()
            print(f"  ✓ Created {num_records} documents, {len(task_ids)} tasks, {num_records*(4)} evidence records, and {len(task_ids)*(2)} agent logs")
            
            return {
                'documents_created': num_records,
                'tasks_created': len(task_ids),
                'evidence_records_created': num_records * 5,  # 平均5条每文档
                'agent_logs_created': len(task_ids) * 2  # 平均2条每任务
            }
            
        except Exception as e:
            print(f"  ✗ CREATE operations failed: {str(e)}")
            self.connection.rollback()
            return None

    def test_read_operations(self):
        """测试读取操作"""
        print("Testing READ operations...")
        
        try:
            # 查询文档总数
            self.cursor.execute("SELECT COUNT(*) FROM documents;")
            doc_count = self.cursor.fetchone()[0]
            print(f"  Total documents: {doc_count}")
            
            # 查询解析任务总数
            self.cursor.execute("SELECT COUNT(*) FROM parsing_tasks;")
            task_count = self.cursor.fetchone()[0]
            print(f"  Total parsing tasks: {task_count}")
            
            # 查询证据记录总数
            self.cursor.execute("SELECT COUNT(*) FROM evidence_records;")
            evidence_count = self.cursor.fetchone()[0]
            print(f"  Total evidence records: {evidence_count}")
            
            # 查询代理日志总数
            self.cursor.execute("SELECT COUNT(*) FROM agent_logs;")
            log_count = self.cursor.fetchone()[0]
            print(f"  Total agent logs: {log_count}")
            
            # 查询特定状态的文档
            self.cursor.execute("SELECT status, COUNT(*) FROM documents GROUP BY status;")
            status_counts = self.cursor.fetchall()
            print(f"  Document statuses: {dict(status_counts)}")
            
            # 查询最近的文档
            self.cursor.execute("SELECT id, title, status FROM documents ORDER BY created_at DESC LIMIT 3;")
            recent_docs = self.cursor.fetchall()
            print(f"  Recent documents: {len(recent_docs)}")
            
            print("  ✓ READ operations successful")
            
            return {
                'total_documents': doc_count,
                'total_tasks': task_count,
                'total_evidence': evidence_count,
                'total_logs': log_count,
                'status_distribution': dict(status_counts),
                'recent_docs_sample': recent_docs
            }
            
        except Exception as e:
            print(f"  ✗ READ operations failed: {str(e)}")
            return None

    def test_update_operations(self):
        """测试更新操作"""
        print("Testing UPDATE operations...")
        
        try:
            # 更新随机文档的状态
            self.cursor.execute("SELECT id FROM documents ORDER BY RANDOM() LIMIT 3;")
            doc_ids = [row[0] for row in self.cursor.fetchall()]
            
            for doc_id in doc_ids:
                new_status = random.choice(['uploaded', 'parsing', 'completed', 'failed'])
                self.cursor.execute(
                    "UPDATE documents SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;",
                    (new_status, doc_id)
                )
            
            # 更新随机任务的进度
            self.cursor.execute("SELECT id FROM parsing_tasks ORDER BY RANDOM() LIMIT 3;")
            task_ids = [row[0] for row in self.cursor.fetchall()]
            
            for task_id in task_ids:
                new_progress = random.randint(20, 100)
                self.cursor.execute(
                    "UPDATE parsing_tasks SET progress = %s WHERE id = %s;",
                    (new_progress, task_id)
                )
            
            # 更新随机证据的状态
            self.cursor.execute("SELECT id FROM evidence_records ORDER BY RANDOM() LIMIT 3;")
            evidence_ids = [row[0] for row in self.cursor.fetchall()]
            
            for evidence_id in evidence_ids:
                new_status = random.choice(['pending', 'approved', 'rejected'])
                self.cursor.execute(
                    "UPDATE evidence_records SET status = %s WHERE id = %s;",
                    (new_status, evidence_id)
                )
            
            # 提交更新
            self.connection.commit()
            print(f"  ✓ Updated {len(doc_ids)} documents, {len(task_ids)} tasks, {len(evidence_ids)} evidence records")
            
            return {
                'documents_updated': len(doc_ids),
                'tasks_updated': len(task_ids),
                'evidence_updated': len(evidence_ids)
            }
            
        except Exception as e:
            print(f"  ✗ UPDATE operations failed: {str(e)}")
            self.connection.rollback()
            return None

    def test_delete_operations(self):
        """测试删除操作（仅删除测试数据）"""
        print("Testing DELETE operations...")
        
        try:
            # 删除最近插入的一些测试数据（避免删除原始数据）
            # 首先查找最近插入的日志
            self.cursor.execute("SELECT id FROM agent_logs ORDER BY created_at DESC LIMIT 2;")
            log_ids = [row[0] for row in self.cursor.fetchall()]
            
            if log_ids:
                placeholders = ','.join(['%s'] * len(log_ids))
                self.cursor.execute(f"DELETE FROM agent_logs WHERE id IN ({placeholders});", log_ids)
            
            # 删除对应的任务（如果有）
            if log_ids:
                self.cursor.execute("SELECT DISTINCT task_id FROM agent_logs WHERE id IN %s;", (tuple(log_ids),))
                task_ids = [row[0] for row in self.cursor.fetchall()]
                if task_ids:
                    placeholders = ','.join(['%s'] * len(task_ids))
                    self.cursor.execute(f"DELETE FROM parsing_tasks WHERE id IN ({placeholders});", task_ids)
            
            self.connection.commit()
            print(f"  ✓ Deleted test records: {len(log_ids)} logs")
            
            return {
                'logs_deleted': len(log_ids)
            }
            
        except Exception as e:
            print(f"  ✗ DELETE operations failed: {str(e)}")
            self.connection.rollback()
            return None

    def run_comprehensive_test(self):
        """运行综合数据库操作测试"""
        print("="*70)
        print("COMPREHENSIVE DATABASE OPERATIONS TEST")
        print("="*70)
        
        # 连接数据库
        if not self.connect_db():
            print("Cannot proceed without database connection")
            return None
        
        # 创建表（如果不存在）
        if not self.create_tables_if_not_exists():
            print("Cannot proceed without proper table setup")
            self.disconnect_db()
            return None
        
        # 执行各项测试
        create_result = self.test_create_operations(5)
        read_result = self.test_read_operations()
        update_result = self.test_update_operations()
        delete_result = self.test_delete_operations()
        
        # 断开连接
        self.disconnect_db()
        
        # 汇总结果
        results = {
            'create_operations': create_result,
            'read_operations': read_result,
            'update_operations': update_result,
            'delete_operations': delete_result,
            'summary': {
                'overall_status': 'success' if all([
                    create_result is not None,
                    read_result is not None,
                    update_result is not None,
                    delete_result is not None
                ]) else 'failure',
                'timestamp': datetime.now().isoformat()
            }
        }
        
        # 打印汇总
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"CREATE Operations: {'✓ PASS' if create_result else '✗ FAIL'}")
        print(f"READ Operations:   {'✓ PASS' if read_result else '✗ FAIL'}")
        print(f"UPDATE Operations: {'✓ PASS' if update_result else '✗ FAIL'}")
        print(f"DELETE Operations: {'✓ PASS' if delete_result else '✗ FAIL'}")
        print("-"*70)
        print(f"Overall Status:    {results['summary']['overall_status']}")
        
        return results

def main():
    tester = DatabaseOperationsTester()
    results = tester.run_comprehensive_test()
    
    if results:
        # 输出详细结果
        print("\nDetailed Results:")
        import pprint
        pprint.pprint(results, width=100, depth=4)

if __name__ == "__main__":
    main()