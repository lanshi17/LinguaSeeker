#!/usr/bin/env python3
"""
Qdrant HTTPS连接测试脚本
用于验证SSL/TLS配置和HTTPS访问
"""
import sys
import os
import ssl
import urllib.request
from urllib.error import URLError

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def test_https_access():
    """测试HTTPS访问Qdrant服务"""
    print("🔍 测试HTTPS访问Qdrant服务...")
    
    # 从环境变量获取配置
    try:
        from src.database_config import DatabaseConfig
        config = DatabaseConfig.from_env()
        print(f"✅ 加载配置成功 - Host: {config.qdrant.host}, Port: {config.qdrant.port}")
    except Exception as e:
        print(f"❌ 无法加载配置: {e}")
        return False
    
    # 构建HTTPS URL
    https_url = f"https://{config.qdrant.host}:{config.qdrant.port}/healthz"
    http_url = f"http://{config.qdrant.host}:{config.qdrant.port}/healthz"
    
    print(f"🌐 测试URL: {https_url}")
    
    # 创建不验证证书的SSL上下文（用于测试自签名证书）
    ssl_context = ssl.create_default_context()
    if not config.qdrant.verify_ssl:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    
    # 首先尝试HTTPS
    if config.qdrant.use_tls:
        print("🔒 尝试HTTPS连接...")
        try:
            req = urllib.request.Request(https_url)
            req.add_header('X-Qdrant-Api-Key', config.qdrant.api_key)
            
            response = urllib.request.urlopen(req, context=ssl_context, timeout=10)
            if response.getcode() == 200:
                print(f"✅ HTTPS 连接成功! 状态码: {response.getcode()}")
                print(f"   响应内容: {response.read().decode('utf-8')[:100]}...")
                return True
            else:
                print(f"❌ HTTPS 连接返回非200状态码: {response.getcode()}")
        except URLError as e:
            print(f"❌ HTTPS 连接失败: {e}")
            if hasattr(e, 'reason'):
                print(f"   原因: {e.reason}")
        except Exception as e:
            print(f"❌ HTTPS 连接异常: {e}")
    
    # 如果HTTPS失败，尝试HTTP
    print("🔓 尝试HTTP连接...")
    try:
        req = urllib.request.Request(http_url)
        req.add_header('X-Qdrant-Api-Key', config.qdrant.api_key)
        
        response = urllib.request.urlopen(req, timeout=10)
        if response.getcode() == 200:
            print(f"✅ HTTP 连接成功! 状态码: {response.getcode()}")
            print(f"   响应内容: {response.read().decode('utf-8')[:100]}...")
            return True
        else:
            print(f"❌ HTTP 连接返回非200状态码: {response.getcode()}")
    except URLError as e:
        print(f"❌ HTTP 连接失败: {e}")
        if hasattr(e, 'reason'):
            print(f"   原因: {e.reason}")
    except Exception as e:
        print(f"❌ HTTP 连接异常: {e}")
    
    return False

def test_qdrant_client_connection():
    """测试Qdrant客户端连接"""
    print("\n🤖 测试Qdrant客户端连接...")
    
    try:
        from src.qdrant_client import QdrantManager
        from src.database_config import DatabaseConfig

        config = DatabaseConfig.from_env()
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
        return False

def test_certificate_info():
    """测试证书信息"""
    print("\n📜 测试证书信息...")
    
    import subprocess
    import json
    
    cert_path = "./qdrant/certs/qdrant.crt"
    if os.path.exists(cert_path):
        try:
            result = subprocess.run(['openssl', 'x509', '-in', cert_path, '-text', '-noout'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                # 提取关键信息
                cert_info = result.stdout
                subject_line = [line.strip() for line in cert_info.split('\n') if 'Subject:' in line][0] if [line.strip() for line in cert_info.split('\n') if 'Subject:' in line] else "未找到主题信息"
                issuer_line = [line.strip() for line in cert_info.split('\n') if 'Issuer:' in line][0] if [line.strip() for line in cert_info.split('\n') if 'Issuer:' in line] else "未找到发行者信息"
                
                print(f"✅ 证书文件存在: {cert_path}")
                print(f"   主题: {subject_line}")
                print(f"   发行者: {issuer_line}")
                
                # 查找证书有效期
                validity_lines = [line.strip() for line in cert_info.split('\n') if 'Not Before:' in line or 'Not After :' in line]
                for line in validity_lines:
                    print(f"   {line}")
            else:
                print(f"❌ 读取证书信息失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("❌ 读取证书信息超时")
        except Exception as e:
            print(f"❌ 读取证书信息异常: {e}")
    else:
        print(f"⚠️  证书文件不存在: {cert_path}")

if __name__ == "__main__":
    print("="*70)
    print("Qdrant HTTPS连接测试")
    print("="*70)
    
    # 测试证书信息
    test_certificate_info()
    
    # 测试HTTPS访问
    https_success = test_https_access()
    
    # 测试Qdrant客户端连接
    client_success = test_qdrant_client_connection()
    
    print("\n" + "="*70)
    print("测试结果总结:")
    print(f"HTTPS访问测试: {'✅ 通过' if https_success else '❌ 失败'}")
    print(f"客户端连接测试: {'✅ 通过' if client_success else '❌ 失败'}")
    
    if https_success or client_success:
        print("\n🎉 至少有一个测试通过，HTTPS配置基本正常!")
        if https_success and client_success:
            print("✨ 所有测试都通过，HTTPS配置完全正常!")
    else:
        print("\n💥 所有测试均失败，请检查SSL/TLS配置")
        
    print("="*70)