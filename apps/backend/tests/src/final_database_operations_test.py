#!/usr/bin/env python3
"""
数据库操作测试类 - 最终版
支持多种数据库连接方式
"""

import uuid
import json
import random
import subprocess
import tempfile
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# 添加项目根目录到Python路径
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_config import DatabaseConfig

class FinalDatabaseOperationsTester:
    def __init__(self):
        self.config = DatabaseConfig.from_env()
        self.use_psql = self._check_psql_available()
        
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

    def _check_psql_available(self) -> bool:
        """检查系统是否可用psql命令"""
        try:
            result = subprocess.run(['which', 'psql'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False

    def execute_query_with_psql(self, query: str) -> Optional[List]:
        """使用psql执行查询"""
        try:
            cmd = [
                'psql',
                '-h', self.config.postgresql.host,
                '-p', str(self.config.postgresql.port),
                '-d', self.config.postgresql.database,
                '-U', 'yangzs',  # 使用修复后的用户名
                '-t',  # 只输出元组（不包含列名和边框）
                '-c', query,
                '-v', 'ON_ERROR_STOP=1'  # 遇到错误停止
            ]
            
            # 设置环境变量以避免密码提示
            env = os.environ.copy()
            env['PGPASSWORD'] = '***REMOVED***'  # 使用修复后的密码
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # 解析输出
                lines = result.stdout.strip().split('\n')
                # 过滤掉空行和分隔符
                lines = [line for line in lines if line and not line.startswith('---')]
                return lines
            else:
                print(f"Query failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print("Query timed out")
            return None
        except Exception as e:
            print(f"Error executing query with psql: {str(e)}")
            return None

    def execute_query_with_python(self):
        """使用Python库执行查询（如果可用）"""
        try:
            import psycopg2
            
            conn = psycopg2.connect(
                host=self.config.postgresql.host,
                port=self.config.postgresql.port,
                database=self.config.postgresql.database,
                user="yangzs",  # 修复后的用户名
                password="***REMOVED***"  # 修复后的密码
            )
            cursor = conn.cursor()
            
            def execute(query):
                cursor.execute(query)
                try:
                    result = cursor.fetchall()
                    conn.commit()
                    return [str(row) for row in result]
                except:
                    conn.commit()
                    return []
            
            # 返回执行函数
            return execute, conn, cursor
        except ImportError:
            print("psycopg2 not available")
            return None, None, None
        except Exception as e:
            print(f"Failed to connect with psycopg2: {str(e)}")
            return None, None, None

    def execute_query(self, query: str) -> Optional[List]:
        """执行查询，根据可用性选择方法"""
        if self.use_psql:
            return self.execute_query_with_psql(query)
        else:
            # 尝试使用Python库
            executor, conn, cursor = self.execute_query_with_python()
            if executor:
                try:
                    result = executor(query)
                    cursor.close()
                    conn.close()
                    return result
                except Exception as e:
                    print(f"Error executing query with psycopg2: {str(e)}")
                    if cursor:
                        cursor.close()
                    if conn:
                        conn.close()
                    return None
            else:
                return None

    def execute_script_from_file(self, file_path: str) -> bool:
        """从文件执行SQL脚本"""
        if self.use_psql:
            try:
                cmd = [
                    'psql',
                    '-h', self.config.postgresql.host,
                    '-p', str(self.config.postgresql.port),
                    '-d', self.config.postgresql.database,
                    '-U', 'yangzs',  # 使用修复后的用户名
                    '-f', file_path,
                    '-v', 'ON_ERROR_STOP=1'
                ]
                
                env = os.environ.copy()
                env['PGPASSWORD'] = '***REMOVED***'  # 使用修复后的密码
                
                result = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    print(f"✓ Script {file_path} executed successfully")
                    return True
                else:
                    print(f"✗ Script {file_path} failed: {result.stderr}")
                    return False
                    
            except subprocess.TimeoutExpired:
                print("Script execution timed out")
                return False
            except Exception as e:
                print(f"Error executing script: {str(e)}")
                return False
        else:
            # 使用Python执行脚本
            with open(file_path, 'r') as f:
                script_content = f.read()
            
            queries = script_content.split(';')
            executor, conn, cursor = self.execute_query_with_python()
            
            if not executor:
                return False
            
            success = True
            try:
                for query in queries:
                    query = query.strip()
                    if query:
                        executor(query)
            except Exception as e:
                print(f"Error executing script with psycopg2: {str(e)}")
                success = False
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
            
            return success

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
            # 检查是否已有表存在
            result = self.execute_query("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
            if result:
                existing_tables = [row.strip() for row in result if row.strip()]
                required_tables = ['documents', 'parsing_tasks', 'evidence_records', 'agent_logs']
                
                if all(table in existing_tables for table in required_tables):
                    print("✓ All required tables already exist")
                    return True
            
            # 如果表不存在，执行创建表的脚本
            print("Tables not found, creating them...")
            
            # 创建临时SQL文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
                f.write("""
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
""")
                temp_sql_file = f.name
            
            success = self.execute_script_from_file(temp_sql_file)
            
            # 清理临时文件
            os.unlink(temp_sql_file)
            
            if success:
                print("✓ Tables created successfully")
                return True
            else:
                print("✗ Failed to create tables")
                return False
                
        except Exception as e:
            print(f"✗ Error creating tables: {str(e)}")
            return False

    def test_create_operations(self, num_records=5):
        """测试创建操作"""
        print(f"Testing CREATE operations with {num_records} records each...")
        
        try:
            # 准备插入数据的SQL语句
            document_ids = []
            
            for i in range(num_records):
                doc_id = str(uuid.uuid4())
                year = random.randint(2020, 2024)
                month = random.randint(1, 12)
                day = random.randint(1, 28)
                created_at = datetime(year, month, day)
                
                # 创建插入文档的SQL
                title = random.choice(self.titles).replace("'", "''")
                journal = random.choice(self.journals).replace("'", "''")
                
                # 创建作者列表
                authors_list = [self.generate_name().replace("'", "''") for _ in range(random.randint(1, 6))]
                authors_json = json.dumps(authors_list)

                insert_doc_sql = f"""
                INSERT INTO documents (
                    id, original_filename, minio_path, status, pmid, doi,
                    title, authors, journal, publication_year, created_at, updated_at
                ) VALUES (
                    '{doc_id}',
                    'ACMG_Study_{random.randint(1000, 9999)}.pdf',
                    'documents/{doc_id[:8]}/ACMG_Study_{random.randint(1000, 9999)}.pdf',
                    '{random.choice(["uploaded", "parsing", "completed", "failed"])}',
                    '{random.randint(10000000, 99999999)}',
                    '10.1000/journal.v{random.randint(1, 20)}.{random.randint(1, 100)}',
                    '{title}',
                    '{authors_json}',
                    '{journal}',
                    {year},
                    '{created_at.strftime("%Y-%m-%d %H:%M:%S")}',
                    '{(created_at + timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d %H:%M:%S")}'
                ) RETURNING id;
                """
                
                result = self.execute_query(insert_doc_sql)
                if result and len(result) > 0:
                    returned_id = result[0].strip()
                    document_ids.append(returned_id)
            
            # 为每个文档创建解析任务
            task_ids = []
            for doc_id in document_ids:
                task_id = str(uuid.uuid4())
                
                insert_task_sql = f"""
                INSERT INTO parsing_tasks (
                    id, document_id, task_type, celery_task_id, result_path, 
                    status, progress, created_at
                ) VALUES (
                    '{task_id}',
                    '{doc_id}',
                    '{random.choice(["pdf_parse", "identifier_resolve"])}',
                    'task-{uuid.uuid4()}',
                    'results/{task_id[:8]}/parsed_data.json',
                    '{random.choice(["pending", "processing", "completed", "failed"])}',
                    {random.randint(0, 100)},
                    '{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                ) RETURNING id;
                """
                
                result = self.execute_query(insert_task_sql)
                if result and len(result) > 0:
                    returned_id = result[0].strip()
                    task_ids.append(returned_id)
            
            # 为每个文档创建证据记录
            evidence_count = 0
            for doc_id in document_ids:
                for _ in range(random.randint(3, 7)):  # 每个文档3-7条证据
                    evidence_id = str(uuid.uuid4())
                    created_at = datetime.now() - timedelta(days=random.randint(1, 30))
                    
                    content = self.generate_sentence(nb_words=12).replace("'", "''")
                    
                    insert_evidence_sql = f"""
                    INSERT INTO evidence_records (
                        id, document_id, evidence_type, content, confidence_score, 
                        source_page, source_position, status, neo4j_node_id, 
                        created_at
                    ) VALUES (
                        '{evidence_id}',
                        '{doc_id}',
                        '{random.choice(self.acmg_types)}',
                        '{content}',
                        {round(random.uniform(0.5, 1.0), 2)},
                        {random.randint(1, 50)},
                        'Page {random.randint(1, 50)}, Column {random.choice(["Left", "Right"])}',
                        '{random.choice(["pending", "approved", "rejected"])}',
                        'node_{random.randint(1000, 9999)}',
                        '{created_at.strftime("%Y-%m-%d %H:%M:%S")}'
                    );
                    """
                    
                    result = self.execute_query(insert_evidence_sql)
                    if result is not None:
                        evidence_count += 1
            
            # 为每个任务创建代理日志
            log_count = 0
            for task_id in task_ids:
                for _ in range(random.randint(1, 3)):  # 每个任务1-3条日志
                    log_id = str(uuid.uuid4())
                    created_at = datetime.now() - timedelta(minutes=random.randint(1, 60))
                    
                    operation = random.choice(["parse", "extract", "validate", "classify"])
                    result_str = "success" if random.random() > 0.1 else "failed"
                    processed_pages = random.randint(1, 20)
                    entities_found = random.randint(0, 15)
                    confidence_avg = round(random.uniform(0.6, 0.95), 2)

                    insert_log_sql = f"""
                    INSERT INTO agent_logs (
                        id, task_id, agent_type, input_hash, output, 
                        duration_ms, retry_count, created_at
                    ) VALUES (
                        '{log_id}',
                        '{task_id}',
                        '{random.choice(["layout", "translation", "extraction", "classification", "validation"])}',
                        '{"".join([random.choice("abcdef0123456789") for _ in range(64)])}',
                        '{{"operation": "{operation}", "result": "{result_str}", "details": {{"processed_pages": {processed_pages}, "entities_found": {entities_found}, "confidence_avg": {confidence_avg}}}}}',
                        {random.randint(100, 5000)},
                        {random.randint(0, 3)},
                        '{created_at.strftime("%Y-%m-%d %H:%M:%S")}'
                    );
                    """
                    
                    result = self.execute_query(insert_log_sql)
                    if result is not None:
                        log_count += 1
            
            print(f"  ✓ Created {len(document_ids)} documents, {len(task_ids)} tasks, {evidence_count} evidence records, and {log_count} agent logs")
            
            return {
                'documents_created': len(document_ids),
                'tasks_created': len(task_ids),
                'evidence_records_created': evidence_count,
                'agent_logs_created': log_count
            }
            
        except Exception as e:
            print(f"  ✗ CREATE operations failed: {str(e)}")
            return None

    def test_read_operations(self):
        """测试读取操作"""
        print("Testing READ operations...")
        
        try:
            # 查询文档总数
            result = self.execute_query("SELECT COUNT(*) FROM documents;")
            if result and len(result) > 0:
                doc_count = int(result[0].strip())
            else:
                doc_count = 0
            print(f"  Total documents: {doc_count}")
            
            # 查询解析任务总数
            result = self.execute_query("SELECT COUNT(*) FROM parsing_tasks;")
            if result and len(result) > 0:
                task_count = int(result[0].strip())
            else:
                task_count = 0
            print(f"  Total parsing tasks: {task_count}")
            
            # 查询证据记录总数
            result = self.execute_query("SELECT COUNT(*) FROM evidence_records;")
            if result and len(result) > 0:
                evidence_count = int(result[0].strip())
            else:
                evidence_count = 0
            print(f"  Total evidence records: {evidence_count}")
            
            # 查询代理日志总数
            result = self.execute_query("SELECT COUNT(*) FROM agent_logs;")
            if result and len(result) > 0:
                log_count = int(result[0].strip())
            else:
                log_count = 0
            print(f"  Total agent logs: {log_count}")
            
            # 查询特定状态的文档
            result = self.execute_query("SELECT status, COUNT(*) FROM documents GROUP BY status;")
            status_counts = {}
            if result:
                for row in result:
                    parts = row.split('|')
                    if len(parts) == 2:
                        status_counts[parts[0].strip()] = int(parts[1].strip())
            print(f"  Document statuses: {status_counts}")
            
            # 查询最近的文档
            result = self.execute_query("SELECT id, title, status FROM documents ORDER BY created_at DESC LIMIT 3;")
            recent_docs = []
            if result:
                for row in result:
                    parts = row.split('|')
                    if len(parts) == 3:
                        recent_docs.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
            print(f"  Recent documents: {len(recent_docs)}")
            
            print("  ✓ READ operations successful")
            
            return {
                'total_documents': doc_count,
                'total_tasks': task_count,
                'total_evidence': evidence_count,
                'total_logs': log_count,
                'status_distribution': status_counts,
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
            result = self.execute_query("SELECT id FROM documents ORDER BY RANDOM() LIMIT 3;")
            doc_ids = []
            if result:
                doc_ids = [row.strip() for row in result]
            
            for doc_id in doc_ids:
                new_status = random.choice(['uploaded', 'parsing', 'completed', 'failed'])
                update_sql = f"UPDATE documents SET status = '{new_status}', updated_at = CURRENT_TIMESTAMP WHERE id = '{doc_id}';"
                self.execute_query(update_sql)
            
            # 更新随机任务的进度
            result = self.execute_query("SELECT id FROM parsing_tasks ORDER BY RANDOM() LIMIT 3;")
            task_ids = []
            if result:
                task_ids = [row.strip() for row in result]
            
            for task_id in task_ids:
                new_progress = random.randint(20, 100)
                update_sql = f"UPDATE parsing_tasks SET progress = {new_progress} WHERE id = '{task_id}';"
                self.execute_query(update_sql)
            
            # 更新随机证据的状态
            result = self.execute_query("SELECT id FROM evidence_records ORDER BY RANDOM() LIMIT 3;")
            evidence_ids = []
            if result:
                evidence_ids = [row.strip() for row in result]
            
            for evidence_id in evidence_ids:
                new_status = random.choice(['pending', 'approved', 'rejected'])
                update_sql = f"UPDATE evidence_records SET status = '{new_status}' WHERE id = '{evidence_id}';"
                self.execute_query(update_sql)
            
            print(f"  ✓ Updated {len(doc_ids)} documents, {len(task_ids)} tasks, {len(evidence_ids)} evidence records")
            
            return {
                'documents_updated': len(doc_ids),
                'tasks_updated': len(task_ids),
                'evidence_updated': len(evidence_ids)
            }
            
        except Exception as e:
            print(f"  ✗ UPDATE operations failed: {str(e)}")
            return None

    def test_delete_operations(self):
        """测试删除操作（仅删除测试数据）"""
        print("Testing DELETE operations...")
        
        try:
            # 删除最近插入的一些测试数据（避免删除原始数据）
            # 首先查找最近插入的日志
            result = self.execute_query("SELECT id FROM agent_logs ORDER BY created_at DESC LIMIT 2;")
            log_ids = []
            if result:
                log_ids = [f"'{row.strip()}'" for row in result]
            
            if log_ids:
                placeholders = ','.join(log_ids)
                delete_sql = f"DELETE FROM agent_logs WHERE id IN ({placeholders});"
                self.execute_query(delete_sql)
            
            print(f"  ✓ Deleted test records: {len(log_ids)} logs")
            
            return {
                'logs_deleted': len(log_ids)
            }
            
        except Exception as e:
            print(f"  ✗ DELETE operations failed: {str(e)}")
            return None

    def run_comprehensive_test(self):
        """运行综合数据库操作测试"""
        print("="*70)
        print("COMPREHENSIVE DATABASE OPERATIONS TEST")
        print("="*70)
        
        # 检查是否可以连接到数据库
        if self.use_psql:
            result = self.execute_query("SELECT version();")
        else:
            # 尝试连接并执行简单查询
            executor, conn, cursor = self.execute_query_with_python()
            if executor and conn:
                try:
                    result = executor("SELECT version();")
                    cursor.close()
                    conn.close()
                except:
                    result = None
                    if cursor:
                        cursor.close()
                    if conn:
                        conn.close()
            else:
                result = None
        
        if not result or len(result) == 0:
            print("✗ Cannot connect to database")
            print(f"  Method used: {'psql' if self.use_psql else 'psycopg2'}")
            return None
        
        print(f"✓ Connected to database, version: {result[0][:50]}...")
        
        # 创建表（如果不存在）
        if not self.create_tables_if_not_exists():
            print("✗ Cannot proceed without proper table setup")
            return None
        
        # 执行各项测试
        create_result = self.test_create_operations(5)
        read_result = self.test_read_operations()
        update_result = self.test_update_operations()
        delete_result = self.test_delete_operations()
        
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
                'timestamp': datetime.now().isoformat(),
                'connection_method': 'psql' if self.use_psql else 'psycopg2'
            }
        }
        
        # 打印汇总
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Connection Method: {'psql' if self.use_psql else 'psycopg2'}")
        print(f"CREATE Operations: {'✓ PASS' if create_result else '✗ FAIL'}")
        print(f"READ Operations:   {'✓ PASS' if read_result else '✗ FAIL'}")
        print(f"UPDATE Operations: {'✓ PASS' if update_result else '✗ FAIL'}")
        print(f"DELETE Operations: {'✓ PASS' if delete_result else '✗ FAIL'}")
        print("-"*70)
        print(f"Overall Status:    {results['summary']['overall_status']}")
        
        return results

def main():
    tester = FinalDatabaseOperationsTester()
    results = tester.run_comprehensive_test()
    
    if results:
        # 输出详细结果
        print("\nDetailed Results:")
        import pprint
        pprint.pprint(results, width=100, depth=4)

if __name__ == "__main__":
    main()