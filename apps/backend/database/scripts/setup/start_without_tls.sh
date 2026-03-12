#!/bin/bash
# 启动服务而不使用TLS，直到证书生成

set -e  # 任何命令失败时退出

echo "🚀 启动Multi-ACMG数据库服务（无TLS）"
echo ""

# 确保当前目录中有必要的文件
if [ ! -f "podman-compose.yml" ]; then
    echo "❌ 未找到 podman-compose.yml 文件"
    exit 1
fi

echo "🔄 停止现有服务..."
podman-compose down || true

echo "⚙️  设置环境变量以禁用TLS..."
export QDRANT_ENABLE_TLS=false
export QDRANT_USE_TLS=false
export QDRANT_VERIFY_SSL=false

echo "🐳 启动服务..."
podman-compose up -d

echo "⏳ 等待服务启动..."
sleep 15

echo "🔍 检查服务状态..."
podman-compose ps

echo ""
echo "✅ 服务已启动！"
echo ""
echo "💡 现在您可以："
echo "   1. 安装mkcert并生成证书"
echo "   2. 使用 ./generate_https_certs.sh 生成证书"
echo "   3. 重新启动服务以启用TLS"