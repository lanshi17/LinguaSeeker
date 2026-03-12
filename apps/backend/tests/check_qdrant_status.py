#!/usr/bin/env python3
"""
检查Qdrant服务状态的脚本
"""
import os
import sys
import subprocess
import time
import socket

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

def check_qdrant_health():
    """检查Qdrant健康状态"""
    try:
        # 设置环境变量以绕过代理
        env = os.environ.copy()
        env.pop('http_proxy', None)
        env.pop('https_proxy', None)
        
        # 使用curl命令检查健康状态（绕过代理）
        result = subprocess.run([
            'curl', '--noproxy', 'localhost', 
            '-s', 'http://localhost:6333/healthz'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            print(f"✅ Qdrant健康检查成功: {result.stdout}")
            return True
        else:
            print(f"❌ Qdrant健康检查失败: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Qdrant健康检查超时")
        return False
    except Exception as e:
        print(f"❌ Qdrant健康检查异常: {e}")
        return False

def main():
    print("="*60)
    print("Qdrant服务状态检查")
    print("="*60)
    
    print(f"🔍 检查端口 localhost:6333 是否开放...")
    port_open = check_port_open('localhost', 6333)
    print(f"   端口状态: {'✅ 开放' if port_open else '❌ 关闭'}")
    
    if port_open:
        print(f"\n🏥 检查Qdrant健康状态...")
        health_ok = check_qdrant_health()
        print(f"   健康状态: {'✅ 正常' if health_ok else '❌ 异常'}")
    else:
        print(f"\n⚠️  端口未开放，无法检查健康状态")
    
    print(f"\n📋 检查完成")
    print(f"   端口开放: {'✅' if port_open else '❌'}")
    print(f"   服务健康: {'✅' if (port_open and check_qdrant_health()) else '❌'}")
    
    if port_open:
        print(f"\n💡 建议: 如果端口开放但健康检查失败，")
        print(f"   可能是端口上运行的不是Qdrant服务。")
    else:
        print(f"\n💡 建议: 启动Qdrant服务。")
    
    print("="*60)

if __name__ == "__main__":
    main()