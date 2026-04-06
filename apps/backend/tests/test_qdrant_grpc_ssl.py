#!/usr/bin/env python3
"""
专门的Qdrant连接测试脚本
用于解决gRPC SSL版本不匹配问题
"""
import sys
import os
import logging

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_qdrant_connection_detailed():
    """详细测试Qdrant连接，包含多层回退机制"""
    print("🔍 开始详细测试Qdrant连接...")
    
    try:
        # 尝试导入QdrantClient
        from qdrant_client import QdrantClient
        print("✅ 成功导入 QdrantClient")
    except ImportError as e:
        print(f"❌ 无法导入 QdrantClient: {e}")
        return False

    try:
        # 从环境变量获取配置
        from tests.src.database_config import DatabaseConfig
        config = DatabaseConfig.from_env()
        print(f"✅ 成功加载配置 - Host: {config.qdrant.host}, Port: {config.qdrant.port}")
    except Exception as e:
        print(f"❌ 无法加载配置: {e}")
        return False

    # 定义多个连接尝试策略
    connection_strategies = [
        {
            "name": "Basic HTTP (no SSL)",
            "kwargs": {
                "host": config.qdrant.host,
                "port": config.qdrant.port,
                "api_key": config.qdrant.api_key,
                "prefer_grpc": False,
                "timeout": 30.0
            }
        },
        {
            "name": "HTTP with SSL disabled",
            "kwargs": {
                "host": config.qdrant.host,
                "port": config.qdrant.port,
                "api_key": config.qdrant.api_key,
                "prefer_grpc": False,
                "timeout": 30.0,
                "https": False,
                "verify": False
            }
        },
        {
            "name": "gRPC without SSL params",
            "kwargs": {
                "host": config.qdrant.host,
                "port": config.qdrant.port,
                "grpc_port": config.qdrant.grpc_port,
                "api_key": config.qdrant.api_key,
                "prefer_grpc": True,
                "timeout": 30.0
            }
        }
    ]

    # 尝试每种连接策略
    for i, strategy in enumerate(connection_strategies, 1):
        print(f"\n尝试连接策略 {i}/{len(connection_strategies)}: {strategy['name']}")
        
        try:
            client = QdrantClient(**strategy['kwargs'])
            # 测试连接
            collections = client.get_collections()
            print(f"✅ {strategy['name']} 连接成功! 可用集合数: {len(collections.collections)}")
            
            # 尝试获取一些额外信息
            try:
                info = client.info()
                print(f"📊 Qdrant 信息: {info}")
            except Exception:
                print("ℹ️  无法获取详细信息，但基本连接成功")
            
            return True
            
        except Exception as e:
            print(f"❌ {strategy['name']} 连接失败: {str(e)}")
            # 检查是否是SSL相关错误
            error_str = str(e).lower()
            if "ssl" in error_str or "tls" in error_str or "version" in error_str:
                print(f"⚠️  检测到SSL/TLS相关错误: {e}")
    
    print("\n❌ 所有连接策略均失败")
    return False

def quick_ping_test():
    """快速ping测试"""
    print("\n📡 执行快速ping测试...")
    try:
        from tests.src.qdrant_client import ping
        result = ping()
        if result:
            print("✅ 快速ping测试成功!")
            return True
        else:
            print("❌ 快速ping测试失败")
            return False
    except Exception as e:
        print(f"❌ 快速ping测试异常: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("Qdrant gRPC SSL版本不匹配问题诊断工具")
    print("="*60)
    
    # 执行详细连接测试
    detailed_success = test_qdrant_connection_detailed()
    
    # 执行快速ping测试
    quick_success = quick_ping_test()
    
    print("\n" + "="*60)
    print("测试结果总结:")
    print(f"详细连接测试: {'✅ 通过' if detailed_success else '❌ 失败'}")
    print(f"快速ping测试: {'✅ 通过' if quick_success else '❌ 失败'}")
    
    if detailed_success or quick_success:
        print("\n🎉 至少有一个测试通过，Qdrant连接应该可用!")
    else:
        print("\n💥 所有测试均失败，需要进一步排查SSL/TLS配置")
        
    print("="*60)
