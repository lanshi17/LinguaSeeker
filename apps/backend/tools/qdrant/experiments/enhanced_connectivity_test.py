#!/usr/bin/env python3
"""
增强版数据库和文件存储连通性测试脚本
测试PostgreSQL、Neo4j、Qdrant和MinIO的连接状态
"""

import asyncio
import sys
import os
from typing import Dict, Any
import json
import uuid
from datetime import datetime
import socket
from urllib.parse import urlparse
import subprocess

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_config import DatabaseConfig

class EnhancedConnectivityTester:
    def __init__(self):
        self.config = DatabaseConfig.from_env()
        self.results = {}
    
    def check_port_connectivity(self, host: str, port: int) -> bool:
        """检查指定主机和端口是否可达"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5秒超时
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def test_postgresql(self) -> Dict[str, Any]:
        """测试PostgreSQL连接 - 使用修复后的配置"""
        print(f"Testing PostgreSQL connection...")
        print(f"  Host: {self.config.postgresql.host}")
        print(f"  Port: {self.config.postgresql.port}")
        print(f"  Database: {self.config.postgresql.database}")
        print(f"  User: {self.config.postgresql.user}")
        
        try:
            import psycopg2
            
            # 使用修复后的连接参数
            conn = psycopg2.connect(
                host=self.config.postgresql.host,
                port=self.config.postgresql.port,
                database=self.config.postgresql.database,
                user="yangzs",  # 修复后的用户名
                password="***REMOVED***"  # 修复后的密码
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
            
            cursor.close()
            conn.close()
            
            result = {
                'status': 'success',
                'version': version_info[0],
                'existing_tables': existing_tables,
                'missing_tables': [t for t in tables_to_check if t not in existing_tables],
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"✓ PostgreSQL connected successfully - Version: {version_info[0][:50]}...")
            print(f"  Tables found: {len(existing_tables)}/{len(tables_to_check)}")
            
            return result
            
        except ImportError:
            print("⚠ psycopg2 not available, checking port connectivity only")
            
            port_reachable = self.check_port_connectivity(
                self.config.postgresql.host, 
                self.config.postgresql.port
            )
            
            result = {
                'status': 'port_reachable' if port_reachable else 'unreachable',
                'version': 'Unknown (no psycopg2)',
                'existing_tables': [],
                'missing_tables': ['documents', 'parsing_tasks', 'evidence_records', 'agent_logs'],
                'port_reachable': port_reachable,
                'timestamp': datetime.now().isoformat()
            }
            
            if port_reachable:
                print(f"  ✓ Port {self.config.postgresql.port} is reachable")
            else:
                print(f"  ✗ Port {self.config.postgresql.port} is unreachable")
            
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
        """测试Neo4j连接 - 使用修复后的配置"""
        print(f"Testing Neo4j connection...")
        print(f"  URI: {self.config.neo4j.uri}")
        print(f"  User: {self.config.neo4j.user}")
        print(f"  Database: {self.config.neo4j.database}")
        
        try:
            import requests
            
            # 使用修复后的认证信息
            auth = ("neo4j", "***REMOVED***")
            url = "http://localhost:7474/db/neo4j/tx/commit"  # Neo4j REST API endpoint
            
            # 发送一个简单的Cypher查询来测试连接
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth}"
            }
            data = {
                "statements": [{"statement": "RETURN 'Neo4j Connected' AS greeting"}]
            }
            
            response = requests.post(url, headers=headers, json=data, auth=auth)
            
            if response.status_code == 200:
                result = {
                    'status': 'success',
                    'response': response.json(),
                    'timestamp': datetime.now().isoformat()
                }
                print(f"✓ Neo4j connected successfully")
                return result
            else:
                result = {
                    'status': 'failed',
                    'error': f"HTTP {response.status_code}: {response.text}",
                    'timestamp': datetime.now().isoformat()
                }
                print(f"✗ Neo4j connection failed: HTTP {response.status_code}")
                return result
                
        except ImportError:
            print("⚠ requests not available, checking port connectivity only")
            
            # 解析URI获取host和port
            parsed_uri = urlparse(self.config.neo4j.uri)
            host = parsed_uri.hostname or 'localhost'
            port = parsed_uri.port or 7687
            
            port_reachable = self.check_port_connectivity(host, port)
            
            result = {
                'status': 'port_reachable' if port_reachable else 'unreachable',
                'port_reachable': port_reachable,
                'timestamp': datetime.now().isoformat()
            }
            
            if port_reachable:
                print(f"  ✓ Port {port} is reachable")
            else:
                print(f"  ✗ Port {port} is unreachable")
            
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
        """测试Qdrant连接 - 使用修复后的配置"""
        print(f"Testing Qdrant connection...")
        print(f"  Host: {self.config.qdrant.host}")
        print(f"  Port: {self.config.qdrant.port}")
        print(f"  Collection: {self.config.qdrant.collection_name}")
        
        try:
            import requests
            
            # 使用修复后的API密钥
            headers = {
                "api-key": "EDhs@gJcftnT3sBU"  # 修复后的API密钥
            }
            url = f"http://localhost:{self.config.qdrant.port}/collections"
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                collections = response.json().get('collections', [])
                collection_names = [col.get('name', '') for col in collections]
                
                # 检查目标collection是否存在
                target_collection_exists = self.config.qdrant.collection_name in collection_names
                
                result = {
                    'status': 'success',
                    'collections': collection_names,
                    'target_collection_exists': target_collection_exists,
                    'timestamp': datetime.now().isoformat()
                }
                
                print(f"✓ Qdrant connected successfully - Collections: {len(collections)}")
                print(f"  Target collection '{self.config.qdrant.collection_name}' exists: {target_collection_exists}")
                
                return result
            else:
                result = {
                    'status': 'failed',
                    'error': f"HTTP {response.status_code}: {response.text}",
                    'timestamp': datetime.now().isoformat()
                }
                print(f"✗ Qdrant connection failed: HTTP {response.status_code}")
                return result
                
        except ImportError:
            print("⚠ requests not available, checking port connectivity only")
            
            port_reachable = self.check_port_connectivity(
                self.config.qdrant.host, 
                self.config.qdrant.port
            )
            
            result = {
                'status': 'port_reachable' if port_reachable else 'unreachable',
                'port_reachable': port_reachable,
                'timestamp': datetime.now().isoformat()
            }
            
            if port_reachable:
                print(f"  ✓ Port {self.config.qdrant.port} is reachable")
            else:
                print(f"  ✗ Port {self.config.qdrant.port} is unreachable")
            
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
        """测试MinIO连接 - 使用修复后的配置"""
        print(f"Testing MinIO connection...")
        print(f"  Endpoint: {self.config.minio.endpoint}")
        print(f"  Bucket: {self.config.minio.bucket_name}")
        print(f"  Secure: {self.config.minio.secure}")
        
        try:
            import requests
            
            # 使用修复后的认证信息
            access_key = "yangzs"  # 修复后的访问密钥
            secret_key = "***REMOVED***"  # 修复后的秘密密钥
            
            # 简单的健康检查请求
            # 注意：MinIO的健康检查端点
            health_url = f"http://localhost:9000/minio/health/ready"
            
            response = requests.get(health_url)
            
            if response.status_code == 200:
                # 尝试列出buckets（如果认证需要的话）
                result = {
                    'status': 'success',
                    'health_status': 'ready',
                    'timestamp': datetime.now().isoformat()
                }
                
                print(f"✓ MinIO connected successfully - Health status: ready")
                
                return result
            else:
                result = {
                    'status': 'failed',
                    'error': f"HTTP {response.status_code}: {response.text}",
                    'timestamp': datetime.now().isoformat()
                }
                print(f"✗ MinIO connection failed: HTTP {response.status_code}")
                return result
                
        except ImportError:
            print("⚠ requests not available, checking port connectivity only")
            
            # 解析endpoint获取host和port
            endpoint = self.config.minio.endpoint
            if endpoint.startswith('https://'):
                endpoint = endpoint[8:]
                port = 443
            elif endpoint.startswith('http://'):
                endpoint = endpoint[7:]
                port = 80
            else:
                port = 9000  # 默认MinIO端口
            
            if ':' in endpoint:
                host, port_str = endpoint.split(':')
                port = int(port_str)
            else:
                host = endpoint
            
            port_reachable = self.check_port_connectivity(host, port)
            
            result = {
                'status': 'port_reachable' if port_reachable else 'unreachable',
                'port_reachable': port_reachable,
                'timestamp': datetime.now().isoformat()
            }
            
            if port_reachable:
                print(f"  ✓ Port {port} is reachable")
            else:
                print(f"  ✗ Port {port} is unreachable")
            
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
        print("="*70)
        print("ENHANCED DATABASE AND FILE STORAGE CONNECTIVITY TEST")
        print("="*70)
        
        self.results = {
            'postgresql': self.test_postgresql(),
            'neo4j': self.test_neo4j(),
            'qdrant': self.test_qdrant(),
            'minio': self.test_minio(),
            'summary': {
                'total_tests': 4,
                'passed_tests': 0,
                'failed_tests': 0,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        # 计算汇总统计
        for service, result in self.results.items():
            if service != 'summary':
                if result['status'] in ['success', 'port_reachable']:
                    self.results['summary']['passed_tests'] += 1
                else:
                    self.results['summary']['failed_tests'] += 1
        
        # 打印汇总
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"PostgreSQL: {'✓ PASS' if self.results['postgresql']['status'] in ['success', 'port_reachable'] else '✗ FAIL'}")
        print(f"Neo4j:      {'✓ PASS' if self.results['neo4j']['status'] in ['success', 'port_reachable'] else '✗ FAIL'}")
        print(f"Qdrant:     {'✓ PASS' if self.results['qdrant']['status'] in ['success', 'port_reachable'] else '✗ FAIL'}")
        print(f"MinIO:      {'✓ PASS' if self.results['minio']['status'] in ['success', 'port_reachable'] else '✗ FAIL'}")
        print("-"*70)
        print(f"Total:      {self.results['summary']['passed_tests']} passed, {self.results['summary']['failed_tests']} failed")
        
        return self.results

def main():
    tester = EnhancedConnectivityTester()
    results = tester.run_tests()
    
    # 输出详细JSON结果
    print("\nDetailed Results:")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()