#!/usr/bin/env python3
"""
数据库和文件存储连通性测试脚本（简化版）
测试Neo4j、Qdrant和MinIO的连接状态
"""

import sys
import os
from typing import Dict, Any
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_config import DatabaseConfig

class ConnectivityTester:
    def __init__(self):
        self.config = DatabaseConfig.from_env()
        self.results = {}
    
    def test_postgresql_with_sqlite_fallback(self) -> Dict[str, Any]:
        """测试PostgreSQL连接，如果失败则使用SQLite作为备选"""
        print("Testing PostgreSQL connection...")
        
        try:
            import psycopg2
            
            # 使用psycopg2进行基本连接测试
            conn = psycopg2.connect(
                host=self.config.postgresql.host,
                port=self.config.postgresql.port,
                database=self.config.postgresql.database,
                user=self.config.postgresql.user,
                password=self.config.postgresql.password
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version_info = cursor.fetchone()
            
            # 检查所需的表是否存在
            tables_to_check = ['documents', 'parsing_tasks', 'evidence_records', 'agent_logs']
            existing_tables = []
            
            for table in tables_to_check:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                    );
                """, (table,))
                
                if cursor.fetchone()[0]:
                    existing_tables.append(table)
            
            # 检查关键字段
            fields_to_check = {
                'documents': ['id', 'original_filename', 'minio_path', 'status', 'pmid', 'doi', 'title', 'created_at'],
                'parsing_tasks': ['id', 'document_id', 'task_type', 'celery_task_id', 'result_path', 'status', 'progress'],
                'evidence_records': ['id', 'document_id', 'evidence_type', 'content', 'confidence_score', 'source_page', 'source_position', 'status', 'neo4j_node_id', 'created_at'],
                'agent_logs': ['id', 'task_id', 'agent_type', 'input_hash', 'output', 'duration_ms', 'retry_count']
            }
            
            existing_fields = {}
            for table, fields in fields_to_check.items():
                existing_fields[table] = []
                for field in fields:
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns 
                            WHERE table_name = %s 
                            AND column_name = %s
                        );
                    """, (table, field))
                    
                    if cursor.fetchone()[0]:
                        existing_fields[table].append(field)
            
            cursor.close()
            conn.close()
            
            result = {
                'status': 'success',
                'version': version_info[0],
                'existing_tables': existing_tables,
                'missing_tables': [t for t in tables_to_check if t not in existing_tables],
                'existing_fields': existing_fields,
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"✓ PostgreSQL connected successfully - Version: {version_info[0][:50]}...")
            print(f"  Tables found: {len(existing_tables)}/{len(tables_to_check)}")
            print(f"  Missing tables: {result['missing_tables']}")
            
            return result
            
        except ImportError:
            print("⚠ psycopg2 not available, skipping PostgreSQL test")
            result = {
                'status': 'skipped',
                'error': 'psycopg2 module not available',
                'timestamp': datetime.now().isoformat()
            }
            return result
        except Exception as e:
            result = {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            print(f"✗ PostgreSQL connection failed: {str(e)}")
            return result
    
    def test_neo4j(self) -> Dict[str, Any]:
        """测试Neo4j连接"""
        print("Testing Neo4j connection...")
        
        try:
            from neo4j import GraphDatabase
            
            driver = GraphDatabase.driver(
                self.config.neo4j.uri,
                auth=(self.config.neo4j.user, self.config.neo4j.password)
            )
            
            # 测试连接
            with driver.session(database=self.config.neo4j.database) as session:
                result = session.run("RETURN 'Neo4j Connected' AS greeting")
                greeting = result.single()[0]
                
                # 尝试获取数据库信息
                info_result = session.run("CALL db.info() YIELD name, address RETURN name, address")
                info = info_result.single()
                
            driver.close()
            
            result = {
                'status': 'success',
                'greeting': greeting,
                'info': {'name': info[0], 'address': info[1]} if info else {},
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"✓ Neo4j connected successfully - {greeting}")
            return result
            
        except ImportError:
            print("⚠ neo4j module not available, skipping Neo4j test")
            result = {
                'status': 'skipped',
                'error': 'neo4j module not available',
                'timestamp': datetime.now().isoformat()
            }
            return result
        except Exception as e:
            result = {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            print(f"✗ Neo4j connection failed: {str(e)}")
            return result
    
    def test_qdrant(self) -> Dict[str, Any]:
        """测试Qdrant连接"""
        print("Testing Qdrant connection...")

        try:
            from src.qdrant_client import QdrantManager

            # 使用新的QdrantManager类进行连接测试
            qdrant_manager = QdrantManager(self.config)
            
            # 测试连接
            if qdrant_manager.connect():
                # 获取collections列表
                collections = qdrant_manager.client.get_collections()

                # 检查目标collection是否存在
                target_collection_exists = any(
                    col.name == self.config.qdrant.collection_name
                    for col in collections.collections
                )

                result = {
                    'status': 'success',
                    'collections': [col.name for col in collections.collections],
                    'target_collection_exists': target_collection_exists,
                    'use_tls': self.config.qdrant.use_tls,
                    'verify_ssl': self.config.qdrant.verify_ssl,
                    'timestamp': datetime.now().isoformat()
                }

                print(f"✓ Qdrant connected successfully - Collections: {len(collections.collections)}")
                print(f"  Target collection '{self.config.qdrant.collection_name}' exists: {target_collection_exists}")
                print(f"  TLS enabled: {self.config.qdrant.use_tls}, SSL verification: {self.config.qdrant.verify_ssl}")

                return result
            else:
                result = {
                    'status': 'failed',
                    'error': 'Connection to Qdrant failed',
                    'timestamp': datetime.now().isoformat()
                }
                print(f"✗ Qdrant connection failed")
                return result

        except ImportError:
            print("⚠ qdrant-client module not available, skipping Qdrant test")
            result = {
                'status': 'skipped',
                'error': 'qdrant-client module not available',
                'timestamp': datetime.now().isoformat()
            }
            return result
        except Exception as e:
            result = {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            print(f"✗ Qdrant connection failed: {str(e)}")
            return result
    
    def test_minio(self) -> Dict[str, Any]:
        """测试MinIO连接"""
        print("Testing MinIO connection...")
        
        try:
            from minio import Minio
            from minio.error import S3Error
            
            # 创建MinIO客户端
            client = Minio(
                self.config.minio.endpoint.replace('https://', '').replace('http://', ''),
                access_key=self.config.minio.access_key,
                secret_key=self.config.minio.secret_key,
                secure=self.config.minio.secure
            )
            
            # 测试连接 - 列出所有buckets
            buckets = client.list_buckets()
            bucket_names = [bucket.name for bucket in buckets]
            
            # 检查目标bucket是否存在
            target_bucket_exists = self.config.minio.bucket_name in bucket_names
            
            # 如果目标bucket不存在，尝试创建它
            if not target_bucket_exists:
                try:
                    client.make_bucket(self.config.minio.bucket_name)
                    target_bucket_created = True
                    target_bucket_exists = True
                except S3Error as s3_err:
                    if s3_err.code == "BucketAlreadyOwnedByYou":
                        target_bucket_exists = True
                        target_bucket_created = False
                    else:
                        raise s3_err
            else:
                target_bucket_created = False
            
            result = {
                'status': 'success',
                'buckets': bucket_names,
                'target_bucket_exists': target_bucket_exists,
                'target_bucket_created': target_bucket_created,
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"✓ MinIO connected successfully - Buckets: {len(bucket_names)}")
            print(f"  Target bucket '{self.config.minio.bucket_name}' exists: {target_bucket_exists}")
            if target_bucket_created:
                print(f"  Target bucket was created: {target_bucket_created}")
            
            return result
            
        except ImportError:
            print("⚠ minio module not available, skipping MinIO test")
            result = {
                'status': 'skipped',
                'error': 'minio module not available',
                'timestamp': datetime.now().isoformat()
            }
            return result
        except Exception as e:
            result = {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            print(f"✗ MinIO connection failed: {str(e)}")
            return result
    
    def run_tests(self) -> Dict[str, Any]:
        """运行所有连接测试"""
        print("="*60)
        print("DATABASE AND FILE STORAGE CONNECTIVITY TEST")
        print("="*60)
        
        self.results = {
            'postgresql': self.test_postgresql_with_sqlite_fallback(),
            'neo4j': self.test_neo4j(),
            'qdrant': self.test_qdrant(),
            'minio': self.test_minio(),
            'summary': {
                'total_tests': 4,
                'passed_tests': 0,
                'failed_tests': 0,
                'skipped_tests': 0,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        # 计算汇总统计
        for service, result in self.results.items():
            if service != 'summary':
                if result['status'] == 'success':
                    self.results['summary']['passed_tests'] += 1
                elif result['status'] == 'failed':
                    self.results['summary']['failed_tests'] += 1
                elif result['status'] == 'skipped':
                    self.results['summary']['skipped_tests'] += 1
        
        # 打印汇总
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"PostgreSQL: {'✓ PASS' if self.results['postgresql']['status'] == 'success' else '✗ FAIL' if self.results['postgresql']['status'] == 'failed' else '- SKIP'}")
        print(f"Neo4j:      {'✓ PASS' if self.results['neo4j']['status'] == 'success' else '✗ FAIL' if self.results['neo4j']['status'] == 'failed' else '- SKIP'}")
        print(f"Qdrant:     {'✓ PASS' if self.results['qdrant']['status'] == 'success' else '✗ FAIL' if self.results['qdrant']['status'] == 'failed' else '- SKIP'}")
        print(f"MinIO:      {'✓ PASS' if self.results['minio']['status'] == 'success' else '✗ FAIL' if self.results['minio']['status'] == 'failed' else '- SKIP'}")
        print("-"*60)
        print(f"Total:      {self.results['summary']['passed_tests']} passed, {self.results['summary']['failed_tests']} failed, {self.results['summary']['skipped_tests']} skipped")
        
        return self.results

def main():
    tester = ConnectivityTester()
    results = tester.run_tests()
    
    # 输出详细JSON结果
    print("\nDetailed Results:")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()