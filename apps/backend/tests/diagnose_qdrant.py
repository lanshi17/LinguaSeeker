#!/usr/bin/env python3
"""
Qdrant服务详细诊断脚本
"""
import sys
import os
import socket
import requests
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

def check_qdrant_api(host, port, api_key=None, use_https=False):
    """检查Qdrant API端点"""
    try:
        protocol = "https" if use_https else "http"
        base_url = f"{protocol}://{host}:{port}"
        
        headers = {}
        if api_key:
            headers["api-key"] = api_key
            headers["X-Qdrant-Api-Key"] = api_key
            
        # 尝试访问健康检查端点
        health_url = urljoin(base_url, "/healthz")
        print(f"🔍 尝试访问: {health_url}")
        
        response = requests.get(health_url, headers=headers, timeout=10, verify=False)
        print(f"   状态码: {response.status_code}")
        print(f"   响应头: {dict(response.headers)}")
        print(f"   响应内容: {response.text[:200]}...")
        
        return response.status_code == 200
    except requests.exceptions.SSLError as e:
        print(f"   SSL错误: {e}")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"   连接错误: {e}")
        return False
    except Exception as e:
        print(f"   其他错误: {e}")
        return False

def diagnose_qdrant_service():
    """全面诊断Qdrant服务"""
    print("🔍 开始Qdrant服务诊断...")
    
    # 从配置加载信息
    try:
        from src.database_config import DatabaseConfig
        config = DatabaseConfig.from_env()
        print(f"✅ 加载配置成功")
        print(f"   Host: {config.qdrant.host}")
        print(f"   Port: {config.qdrant.port}")
        print(f"   API Key: {'*' * len(config.qdrant.api_key) if config.qdrant.api_key else '未设置'}")
        print(f"   Use TLS: {config.qdrant.use_tls}")
        print(f"   Verify SSL: {config.qdrant.verify_ssl}")
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        return
    
    # 检查端口是否开放
    print(f"\n🔌 检查端口 {config.qdrant.host}:{config.qdrant.port} 是否开放...")
    port_open = check_port_open(config.qdrant.host, config.qdrant.port)
    print(f"   结果: {'✅ 开放' if port_open else '❌ 关闭或被防火墙阻止'}")
    
    if not port_open:
        print("⚠️  端口未开放，可能是Qdrant服务未启动")
        return
    
    # 尝试不同的连接方式
    print(f"\n🌐 尝试不同协议访问...")
    
    # 1. HTTP without TLS
    print("\n1. 尝试HTTP（无TLS）...")
    http_success = check_qdrant_api(config.qdrant.host, config.qdrant.port, config.qdrant.api_key, use_https=False)
    
    # 2. HTTPS with TLS (if enabled in config)
    if config.qdrant.use_tls:
        print("\n2. 尝试HTTPS（启用TLS）...")
        https_success = check_qdrant_api(config.qdrant.host, config.qdrant.port, config.qdrant.api_key, use_https=True)
    else:
        print("\n2. TLS未在配置中启用，跳过HTTPS测试")
        https_success = False
    
    # 总结
    print(f"\n📋 诊断总结:")
    print(f"   端口开放: {'✅ 是' if port_open else '❌ 否'}")
    print(f"   HTTP访问: {'✅ 成功' if http_success else '❌ 失败'}")
    print(f"   HTTPS访问: {'✅ 成功' if https_success else '❌ 失败' if config.qdrant.use_tls else '⏭️  跳过'}")
    
    if http_success or https_success:
        print(f"\n🎉 Qdrant服务可访问！")
    else:
        print(f"\n💥 Qdrant服务似乎配置有问题或正在代理后面")
        print(f"💡 建议检查:")
        print(f"   - Qdrant服务是否真的在运行")
        print(f"   - 是否有反向代理（如nginx）在端口{config.qdrant.port}上运行")
        print(f"   - TLS/SSL配置是否正确")

if __name__ == "__main__":
    print("="*70)
    print("Qdrant服务详细诊断")
    print("="*70)
    
    diagnose_qdrant_service()
    
    print("="*70)