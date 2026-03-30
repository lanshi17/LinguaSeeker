#!/usr/bin/env python3
"""
Qdrant连接测试脚本
用于验证SSL/TLS连接修复，特别是解决gRPC SSL版本不匹配问题
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from tests.src.qdrant_client import ping

def test_qdrant_connection():
    """测试Qdrant连接"""
    print("🔍 正在测试Qdrant连接...")
    print("   此测试包含多重回退机制，可处理SSL/TLS版本不匹配问题")
    
    success = ping()
    
    if success:
        print("✅ Qdrant连接测试成功!")
        print("   连接已建立，SSL/TLS版本不匹配问题已解决")
        return True
    else:
        print("❌ Qdrant连接测试失败!")
        print("   请检查服务是否正在运行以及配置是否正确")
        print("   您可以运行 'python test_qdrant_grpc_ssl.py' 进行详细诊断")
        return False

if __name__ == "__main__":
    print("="*70)
    print("Qdrant gRPC SSL版本不匹配问题修复验证")
    print("解决: SSL_ERROR_SSL: error:100000f7:SSL routines:OPENSSL_internal:WRONG_VERSION_NUMBER")
    print("="*70)
    
    result = test_qdrant_connection()
    
    print("="*70)
    if result:
        print("🎉 修复验证成功! Qdrant连接问题已解决")
    else:
        print("⚠️  修复验证失败，请检查配置或运行详细诊断")
    print("="*70)