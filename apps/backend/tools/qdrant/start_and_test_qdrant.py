#!/usr/bin/env python3
"""
Qdrant服务启动和连接测试脚本
"""
import sys
import os
import subprocess
import time
import socket
from urllib.parse import urljoin

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def check_port_open(host, port):
    """检查端口是否开放"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def start_qdrant_docker():
    """尝试使用Docker启动Qdrant服务"""
    print("🐳 尝试使用Docker启动Qdrant...")
    
    # 检查docker是否安装
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Docker未安装或不可用")
            return False
        print("✅ Docker已安装")
    except FileNotFoundError:
        print("❌ Docker命令未找到")
        return False
    
    # 检查Qdrant容器是否已在运行
    result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
    if 'qdrant' in result.stdout.lower():
        print("⚠️  Qdrant容器似乎已在运行")
        return True
    
    # 尝试停止旧的Qdrant容器
    print("🧹 清理旧的Qdrant容器...")
    subprocess.run(['docker', 'stop', 'qdrant'], capture_output=True)
    subprocess.run(['docker', 'rm', 'qdrant'], capture_output=True)
    
    # 启动Qdrant容器
    print("🚀 启动Qdrant容器...")
    cmd = [
        'docker', 'run', '-d', 
        '--name', 'qdrant',
        '-p', '6333:6333',
        '-p', '6334:6334',
        'qdrant/qdrant:latest'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ 启动Qdrant容器失败: {result.stderr}")
        return False
    
    print("⏳ 等待Qdrant服务启动...")
    time.sleep(10)  # 等待服务启动
    
    # 检查服务是否启动成功
    if check_port_open('localhost', 6333):
        print("✅ Qdrant服务已成功启动")
        return True
    else:
        print("❌ Qdrant服务启动后端口仍不可访问")
        return False

def test_qdrant_connection():
    """测试Qdrant连接"""
    print("🔍 测试Qdrant连接...")
    
    try:
        from src.database_config import DatabaseConfig
        config = DatabaseConfig.from_env()
        print(f"✅ 加载配置成功 - Host: {config.qdrant.host}, Port: {config.qdrant.port}")
        
        # 临时修改配置以进行测试
        config.qdrant.use_tls = False
        config.qdrant.verify_ssl = False
        
        from src.qdrant_client import QdrantManager
        manager = QdrantManager(config)
        
        success = manager.connect()
        if success:
            print("✅ Qdrant客户端连接成功!")
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
        print(f"❌ 连接测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*70)
    print("Qdrant服务启动和连接测试")
    print("="*70)
    
    # 检查当前端口状态
    print(f"🔍 检查端口 6333 当前状态...")
    if check_port_open('localhost', 6333):
        print("⚠️  端口6333当前处于开放状态")
    else:
        print("ℹ️  端口6333当前处于关闭状态")
    
    # 尝试启动Qdrant
    if not check_port_open('localhost', 6333):
        success = start_qdrant_docker()
        if not success:
            print("💥 无法启动Qdrant服务")
            return
    else:
        print("ℹ️  端口6333已开放，跳过启动步骤")
    
    # 等待一段时间确保服务完全启动
    print("⏳ 等待服务稳定...")
    time.sleep(5)
    
    # 测试连接
    connection_success = test_qdrant_connection()
    
    print("\n" + "="*70)
    print("最终测试结果:")
    print(f"Qdrant服务: {'✅ 运行中' if check_port_open('localhost', 6333) else '❌ 未运行'}")
    print(f"客户端连接: {'✅ 成功' if connection_success else '❌ 失败'}")
    
    if connection_success:
        print("\n🎉 Qdrant服务配置和连接测试全部成功!")
    else:
        print("\n⚠️  Qdrant服务可能仍在启动中或配置有问题")
        print("💡 您可以稍等片刻再重试，或检查Docker容器日志")
    
    print("="*70)

if __name__ == "__main__":
    main()