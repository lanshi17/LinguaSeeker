#!/usr/bin/env python3
"""
ACMG数据库模拟数据生成器（离线版本）
生成documents, parsing_tasks, evidence_records, agent_logs表的模拟数据并保存到文件
"""

import uuid
import random
import json
from datetime import datetime, timedelta
import sys
import os
from typing import List, Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_config import DatabaseConfig

class MockDataGenerator:
    def __init__(self):
        self.config = DatabaseConfig.from_env()
        
        # 模拟数据生成函数
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
        self.documents = []
        self.parsing_tasks = []
        self.evidence_records = []
        self.agent_logs = []
        
        # ACMG证据类型列表
        self.common_acmg_types = [
            'PS1', 'PS2', 'PS3', 'PS4', 'PM1', 'PM2', 'PM3', 'PM4', 'PM5', 'PM6',
            'PP1', 'PP2', 'PP3', 'PP4', 'PP5', 'BA1', 'BS1', 'BS2', 'BS3', 'BS4',
            'BP1', 'BP2', 'BP3', 'BP4', 'BP5', 'BP6', 'BP7'
        ]

    def generate_sentence(self, nb_words=8):
        """生成模拟句子"""
        words = []
        for _ in range(nb_words):
            words.append(random.choice(self.sentences).split()[0])
        return ' '.join(words) + '.'

    def generate_name(self):
        """生成模拟姓名"""
        return f"{random.choice(self.first_names)} {random.choice(self.last_names)}"

    def generate_documents(self, count=50):
        """生成documents表的模拟数据"""
        print(f"Generating {count} document records...")
        
        for i in range(count):
            doc_id = str(uuid.uuid4())
            year = random.randint(2020, 2024)
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            created_at = datetime(year, month, day)
            
            document = {
                'id': doc_id,
                'original_filename': f"ACMG_Study_{random.randint(1000, 9999)}.pdf",
                'minio_path': f"documents/{doc_id[:8]}/{f'ACMG_Study_{random.randint(1000, 9999)}.pdf'}",
                'status': random.choice(['uploaded', 'parsing', 'completed', 'failed']),
                'pmid': f"{random.randint(10000000, 99999999)}",
                'doi': f"10.1000/journal.v{random.randint(1, 20)}.{random.randint(1, 100)}",
                'title': random.choice(self.titles),
                'authors': json.dumps([self.generate_name() for _ in range(random.randint(1, 6))]),
                'journal': random.choice(self.journals),
                'publication_year': year,
                'created_at': created_at,
                'updated_at': created_at + timedelta(days=random.randint(1, 30))
            }
            self.documents.append(document)
        
        print(f"✓ Generated {len(self.documents)} document records")
        return self.documents

    def generate_parsing_tasks(self, count_per_doc=1):
        """为每个文档生成parsing_tasks记录"""
        print(f"Generating {len(self.documents) * count_per_doc} parsing task records...")
        
        for doc in self.documents:
            for _ in range(count_per_doc):
                task_id = str(uuid.uuid4())
                created_at = doc['created_at'] + timedelta(hours=random.randint(1, 24))
                
                task = {
                    'id': task_id,
                    'document_id': doc['id'],
                    'task_type': random.choice(['pdf_parse', 'identifier_resolve']),
                    'celery_task_id': f"task-{uuid.uuid4()}",
                    'result_path': f"results/{task_id[:8]}/parsed_data.json",
                    'status': random.choice(['pending', 'processing', 'completed', 'failed']),
                    'progress': random.randint(0, 100),
                    'error_message': self.generate_sentence(nb_words=6) if random.random() < 0.1 else None,
                    'created_at': created_at,
                    'completed_at': created_at + timedelta(minutes=random.randint(1, 120)) if random.random() > 0.2 else None
                }
                self.parsing_tasks.append(task)
        
        print(f"✓ Generated {len(self.parsing_tasks)} parsing task records")
        return self.parsing_tasks

    def generate_evidence_records(self, count_per_doc=5):
        """为每个文档生成evidence_records记录"""
        print(f"Generating {len(self.documents) * count_per_doc} evidence record records...")
        
        for doc in self.documents:
            for _ in range(count_per_doc):
                evidence_id = str(uuid.uuid4())
                created_at = doc['created_at'] + timedelta(days=random.randint(1, 30))
                
                evidence = {
                    'id': evidence_id,
                    'document_id': doc['id'],
                    'evidence_type': random.choice(self.common_acmg_types),
                    'content': self.generate_sentence(nb_words=12),
                    'confidence_score': round(random.uniform(0.5, 1.0), 2),
                    'source_page': random.randint(1, 50),
                    'source_position': f"Page {random.randint(1, 50)}, Column {random.choice(['Left', 'Right'])}",
                    'status': random.choice(['pending', 'approved', 'rejected']),
                    'neo4j_node_id': f"node_{random.randint(1000, 9999)}",
                    'created_at': created_at,
                    'reviewed_by': str(uuid.uuid4()) if random.random() > 0.7 else None,
                    'reviewed_at': created_at + timedelta(days=random.randint(1, 7)) if random.random() > 0.7 else None
                }
                self.evidence_records.append(evidence)
        
        print(f"✓ Generated {len(self.evidence_records)} evidence record records")
        return self.evidence_records

    def generate_agent_logs(self, count_per_task=2):
        """为每个解析任务生成agent_logs记录"""
        print(f"Generating {len(self.parsing_tasks) * count_per_task} agent log records...")
        
        for task in self.parsing_tasks:
            for _ in range(count_per_task):
                log_id = str(uuid.uuid4())
                created_at = task['created_at'] + timedelta(minutes=random.randint(1, 60))
                
                agent_log = {
                    'id': log_id,
                    'task_id': task['id'],
                    'agent_type': random.choice(['layout', 'translation', 'extraction', 'classification', 'validation']),
                    'input_hash': ''.join([random.choice('abcdef0123456789') for _ in range(64)]),
                    'output': json.dumps({
                        'operation': random.choice(['parse', 'extract', 'validate', 'classify']),
                        'result': 'success' if random.random() > 0.1 else 'failed',
                        'details': {
                            'processed_pages': random.randint(1, 20),
                            'entities_found': random.randint(0, 15),
                            'confidence_avg': round(random.uniform(0.6, 0.95), 2)
                        }
                    }),
                    'duration_ms': random.randint(100, 5000),
                    'retry_count': random.randint(0, 3),
                    'created_at': created_at
                }
                self.agent_logs.append(agent_log)
        
        print(f"✓ Generated {len(self.agent_logs)} agent log records")
        return self.agent_logs

    def save_data_to_files(self):
        """将生成的数据保存到JSON文件"""
        print("\nSaving generated data to files...")
        
        # 创建data目录
        os.makedirs('data', exist_ok=True)
        
        # 保存各个表的数据
        with open('data/documents.json', 'w', encoding='utf-8') as f:
            json.dump(self.documents, f, indent=2, default=str)
        
        with open('data/parsing_tasks.json', 'w', encoding='utf-8') as f:
            json.dump(self.parsing_tasks, f, indent=2, default=str)
        
        with open('data/evidence_records.json', 'w', encoding='utf-8') as f:
            json.dump(self.evidence_records, f, indent=2, default=str)
        
        with open('data/agent_logs.json', 'w', encoding='utf-8') as f:
            json.dump(self.agent_logs, f, indent=2, default=str)
        
        print("✓ Data saved to data/ directory")
        print(f"  - documents.json: {len(self.documents)} records")
        print(f"  - parsing_tasks.json: {len(self.parsing_tasks)} records")
        print(f"  - evidence_records.json: {len(self.evidence_records)} records")
        print(f"  - agent_logs.json: {len(self.agent_logs)} records")

    def generate_insert_sql(self):
        """生成INSERT SQL语句"""
        print("\nGenerating INSERT SQL statements...")
        
        sql_statements = []
        
        # Generate INSERT statements for documents
        for doc in self.documents:
            sql = f"""
INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('{doc['id']}', '{doc['original_filename']}', '{doc['minio_path']}', '{doc['status']}', '{doc['pmid']}', '{doc['doi']}', '{doc['title']}', '{doc['authors']}', '{doc['journal']}', {doc['publication_year']}, '{doc['created_at']}', '{doc['updated_at']}')
ON CONFLICT (pmid) DO NOTHING;"""
            sql_statements.append(sql)
        
        # Generate INSERT statements for parsing_tasks
        for task in self.parsing_tasks:
            completed_at = f"'{task['completed_at']}'" if task['completed_at'] else 'NULL'
            error_msg = f"'{task['error_message']}'" if task['error_message'] else 'NULL'
            
            sql = f"""
INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('{task['id']}', '{task['document_id']}', '{task['task_type']}', '{task['celery_task_id']}', '{task['result_path']}', '{task['status']}', {task['progress']}, {error_msg}, '{task['created_at']}', {completed_at})
ON CONFLICT (id) DO NOTHING;"""
            sql_statements.append(sql)
        
        # Generate INSERT statements for evidence_records
        for evidence in self.evidence_records:
            reviewed_by = f"'{evidence['reviewed_by']}'" if evidence['reviewed_by'] else 'NULL'
            reviewed_at = f"'{evidence['reviewed_at']}'" if evidence['reviewed_at'] else 'NULL'
            
            sql = f"""
INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('{evidence['id']}', '{evidence['document_id']}', '{evidence['evidence_type']}', '{evidence['content']}', {evidence['confidence_score']}, {evidence['source_page']}, '{evidence['source_position']}', '{evidence['status']}', '{evidence['neo4j_node_id']}', '{evidence['created_at']}', {reviewed_by}, {reviewed_at})
ON CONFLICT (id) DO NOTHING;"""
            sql_statements.append(sql)
        
        # Generate INSERT statements for agent_logs
        for log in self.agent_logs:
            sql = f"""
INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('{log['id']}', '{log['task_id']}', '{log['agent_type']}', '{log['input_hash']}', '{log['output']}', {log['duration_ms']}, {log['retry_count']}, '{log['created_at']}')
ON CONFLICT (id) DO NOTHING;"""
            sql_statements.append(sql)
        
        # Save SQL statements to file
        with open('data/insert_statements.sql', 'w', encoding='utf-8') as f:
            f.write("-- Generated INSERT statements for ACMG database\n\n")
            for stmt in sql_statements:
                f.write(stmt + "\n")
        
        print(f"✓ Generated {len(sql_statements)} INSERT statements in data/insert_statements.sql")

    def generate_all_data(self):
        """生成所有类型的模拟数据"""
        print("="*60)
        print("GENERATING MOCK DATA FOR ACMG DATABASE")
        print("="*60)
        
        # 生成数据
        self.generate_documents(50)  # 生成50个文档
        self.generate_parsing_tasks(1)  # 每个文档1个解析任务
        self.generate_evidence_records(5)  # 每个文档5条证据记录
        self.generate_agent_logs(2)  # 每个任务2条日志记录
        
        print("\nData generation completed!")
        print(f"- Documents: {len(self.documents)} records")
        print(f"- Parsing Tasks: {len(self.parsing_tasks)} records")
        print(f"- Evidence Records: {len(self.evidence_records)} records")
        print(f"- Agent Logs: {len(self.agent_logs)} records")
        print("-" * 60)
        
        # 保存数据到文件
        self.save_data_to_files()
        
        # 生成SQL插入语句
        self.generate_insert_sql()
        
        print("\nMock data generation completed!")
        print("Files generated:")
        print("  - data/documents.json")
        print("  - data/parsing_tasks.json") 
        print("  - data/evidence_records.json")
        print("  - data/agent_logs.json")
        print("  - data/insert_statements.sql")


def main():
    generator = MockDataGenerator()
    generator.generate_all_data()


if __name__ == "__main__":
    main()