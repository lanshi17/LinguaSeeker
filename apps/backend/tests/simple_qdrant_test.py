#!/usr/bin/env python3
"""
简化版Qdrant连接测试脚本
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def test_basic_qdrant_connection():
    """测试基本的Qdrant连接"""
    print("🔍 测试基本Qdrant连接...")
    
    try:
        from src.database_config import DatabaseConfig
        config = DatabaseConfig.from_env()
        print(f"✅ 加载配置成功 - Host: {config.qdrant.host}, Port: {config.qdrant.port}")
        print(f"   API Key: {'*' * len(config.qdrant.api_key) if config.qdrant.api_key else '未设置'}")
        print(f"   TLS: {config.qdrant.use_tls}, Verify SSL: {config.qdrant.verify_ssl}")
        
        # 检查Qdrant是否正在运行
        import socket
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5秒超时
        result = sock.connect_ex((config.qdrant.host, config.qdrant.port))
        sock.close()
        
        if result == 0:
            print(f"✅ Qdrant服务在 {config.qdrant.host}:{config.qdrant.port} 上运行")
            return True
        else:
            print(f"❌ Qdrant服务在 {config.qdrant.host}:{config.qdrant.port} 上不可达")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False

def test_qdrant_client_simple():
    """使用简单配置测试Qdrant客户端"""
    print("\n🤖 测试Qdrant客户端连接（简化）...")
    
    try:
        from src.qdrant_client import QdrantManager
        from src.database_config import DatabaseConfig

        # 使用基本配置，不启用TLS
        config = DatabaseConfig.from_env()
        # 强制禁用TLS以进行基本连接测试
        config.qdrant.use_tls = False
        config.qdrant.verify_ssl = False
        
        print(f"🔧 临时禁用TLS以进行基本连接测试...")
        
        manager = QdrantManager(config)

        success = manager.connect()
        if success:
            print("✅ Qdrant客户端连接成功!")
            # 尝试获取集合信息
            try:
                collections = manager.client.get_collections()
                print(f"📊 可用集合数量: {len(collections.collections)}")
                for collection in collections.collections:
                    print(f"   - {collection.name}")
            except Exception as e:
                print(f"⚠️  获取集合信息时出错: {e}")
            return True
        else:
            print("❌ Qdrant客户端连接失败!")
            return False

    except Exception as e:
        print(f"❌ Qdrant客户端测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("="*70)
    print("简化版Qdrant连接测试")
    print("="*70)

    # 测试基本连接
    basic_success = test_basic_qdrant_connection()

    # 测试Qdrant客户端
    if basic_success:
        client_success = test_qdrant_client_simple()
    else:
        print("\n⚠️  由于服务不可达，跳过客户端连接测试")
        client_success = False

    print("\n" + "="*70)
    print("测试结果总结:")
    print(f"基本连接测试: {'✅ 通过' if basic_success else '❌ 失败'}")
    print(f"客户端连接测试: {'✅ 通过' if client_success else '❌ 失败'}")

    if basic_success and client_success:
        print("\n🎉 所有测试都通过!")
    elif basic_success:
        print("\n⚠️  基本连接正常，但客户端连接存在问题")
    else:
        print("\n💥 服务似乎未运行，请确保Qdrant服务已启动")

    print("="*70)