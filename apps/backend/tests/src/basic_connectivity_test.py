#!/usr/bin/env python3
"""
数据库和文件存储连通性测试脚本（基础版）
验证配置和环境变量设置
"""

import sys
import os
from typing import Dict, Any
import json
from datetime import datetime
import socket
from urllib.parse import urlparse

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_config import DatabaseConfig

class BasicConnectivityTester:
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
    
    def test_postgresql_config(self) -> Dict[str, Any]:
        """测试PostgreSQL配置和连通性"""
        print(f"Testing PostgreSQL configuration...")
        print(f"  Host: {self.config.postgresql.host}")
        print(f"  Port: {self.config.postgresql.port}")
        print(f"  Database: {self.config.postgresql.database}")
        print(f"  User: {self.config.postgresql.user}")
        
        # 检查端口连通性
        port_reachable = self.check_port_connectivity(
            self.config.postgresql.host, 
            self.config.postgresql.port
        )
        
        result = {
            'status': 'reachable' if port_reachable else 'unreachable',
            'config': {
                'host': self.config.postgresql.host,
                'port': self.config.postgresql.port,
                'database': self.config.postgresql.database,
                'user': self.config.postgresql.user
            },
            'port_reachable': port_reachable,
            'timestamp': datetime.now().isoformat()
        }
        
        if port_reachable:
            print(f"  ✓ Port {self.config.postgresql.port} is reachable")
        else:
            print(f"  ✗ Port {self.config.postgresql.port} is unreachable")
        
        return result
    
    def test_neo4j_config(self) -> Dict[str, Any]:
        """测试Neo4j配置和连通性"""
        print(f"Testing Neo4j configuration...")
        print(f"  URI: {self.config.neo4j.uri}")
        print(f"  User: {self.config.neo4j.user}")
        print(f"  Database: {self.config.neo4j.database}")
        
        # 解析URI获取host和port
        parsed_uri = urlparse(self.config.neo4j.uri)
        host = parsed_uri.hostname or 'localhost'
        port = parsed_uri.port or 7687
        
        # 检查端口连通性
        port_reachable = self.check_port_connectivity(host, port)
        
        result = {
            'status': 'reachable' if port_reachable else 'unreachable',
            'config': {
                'uri': self.config.neo4j.uri,
                'user': self.config.neo4j.user,
                'database': self.config.neo4j.database
            },
            'port_reachable': port_reachable,
            'timestamp': datetime.now().isoformat()
        }
        
        if port_reachable:
            print(f"  ✓ Port {port} is reachable")
        else:
            print(f"  ✗ Port {port} is unreachable")
        
        return result
    
    def test_qdrant_config(self) -> Dict[str, Any]:
        """测试Qdrant配置和连通性"""
        print(f"Testing Qdrant configuration...")
        print(f"  Host: {self.config.qdrant.host}")
        print(f"  Port: {self.config.qdrant.port}")
        print(f"  Collection: {self.config.qdrant.collection_name}")
        
        # 检查端口连通性
        port_reachable = self.check_port_connectivity(
            self.config.qdrant.host, 
            self.config.qdrant.port
        )
        
        result = {
            'status': 'reachable' if port_reachable else 'unreachable',
            'config': {
                'host': self.config.qdrant.host,
                'port': self.config.qdrant.port,
                'collection_name': self.config.qdrant.collection_name
            },
            'port_reachable': port_reachable,
            'timestamp': datetime.now().isoformat()
        }
        
        if port_reachable:
            print(f"  ✓ Port {self.config.qdrant.port} is reachable")
        else:
            print(f"  ✗ Port {self.config.qdrant.port} is unreachable")
        
        return result
    
    def test_minio_config(self) -> Dict[str, Any]:
        """测试MinIO配置和连通性"""
        print(f"Testing MinIO configuration...")
        print(f"  Endpoint: {self.config.minio.endpoint}")
        print(f"  Bucket: {self.config.minio.bucket_name}")
        print(f"  Secure: {self.config.minio.secure}")
        
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
        
        # 检查端口连通性
        port_reachable = self.check_port_connectivity(host, port)
        
        result = {
            'status': 'reachable' if port_reachable else 'unreachable',
            'config': {
                'endpoint': self.config.minio.endpoint,
                'bucket_name': self.config.minio.bucket_name,
                'secure': self.config.minio.secure
            },
            'port_reachable': port_reachable,
            'timestamp': datetime.now().isoformat()
        }
        
        if port_reachable:
            print(f"  ✓ Port {port} is reachable")
        else:
            print(f"  ✗ Port {port} is unreachable")
        
        return result
    
    def test_environment_variables(self) -> Dict[str, Any]:
        """测试关键环境变量是否存在"""
        print("Testing environment variables...")
        
        required_vars = [
            'POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 'POSTGRES_USER',
            'NEO4J_URI', 'NEO4J_USER',
            'QDRANT_HOST', 'QDRANT_PORT',
            'MINIO_ENDPOINT', 'MINIO_BUCKET_NAME'
        ]
        
        found_vars = {}
        missing_vars = []
        
        for var in required_vars:
            value = os.environ.get(var)
            if value:
                found_vars[var] = value
            else:
                missing_vars.append(var)
        
        result = {
            'found_vars': list(found_vars.keys()),
            'missing_vars': missing_vars,
            'total_required': len(required_vars),
            'found_count': len(found_vars),
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"  Found: {len(found_vars)}/{len(required_vars)} variables")
        if missing_vars:
            print(f"  Missing: {missing_vars}")
        
        return result
    
    def run_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("="*60)
        print("DATABASE AND FILE STORAGE CONFIGURATION TEST")
        print("="*60)
        
        env_result = self.test_environment_variables()
        
        print("\nTesting service connectivity:")
        self.results = {
            'environment': env_result,
            'postgresql': self.test_postgresql_config(),
            'neo4j': self.test_neo4j_config(),
            'qdrant': self.test_qdrant_config(),
            'minio': self.test_minio_config(),
            'summary': {
                'total_services': 4,
                'reachable_services': 0,
                'unreachable_services': 0,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        # 计算服务连通性统计
        for service in ['postgresql', 'neo4j', 'qdrant', 'minio']:
            if self.results[service]['port_reachable']:
                self.results['summary']['reachable_services'] += 1
            else:
                self.results['summary']['unreachable_services'] += 1
        
        # 打印汇总
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Environment vars: {env_result['found_count']}/{env_result['total_required']} found")
        print(f"PostgreSQL: {'✓ REACHABLE' if self.results['postgresql']['port_reachable'] else '✗ UNREACHABLE'}")
        print(f"Neo4j:      {'✓ REACHABLE' if self.results['neo4j']['port_reachable'] else '✗ UNREACHABLE'}")
        print(f"Qdrant:     {'✓ REACHABLE' if self.results['qdrant']['port_reachable'] else '✗ UNREACHABLE'}")
        print(f"MinIO:      {'✓ REACHABLE' if self.results['minio']['port_reachable'] else '✗ UNREACHABLE'}")
        print("-"*60)
        print(f"Services:   {self.results['summary']['reachable_services']} reachable, {self.results['summary']['unreachable_services']} unreachable")
        
        return self.results

def main():
    tester = BasicConnectivityTester()
    results = tester.run_tests()
    
    # 输出详细JSON结果
    print("\nDetailed Results:")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()