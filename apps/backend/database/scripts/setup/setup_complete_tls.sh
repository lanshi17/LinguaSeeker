#!/bin/bash
# 完整的Qdrant TLS设置脚本

set -e  # 任何命令失败时退出

echo "🔐 设置 Qdrant TLS 证书和配置"
echo ""

# 检查是否以正确的目录运行
if [ ! -f ".env" ]; then
    echo "❌ 请在项目根目录中运行此脚本"
    exit 1
fi

# 检查 mkcert
echo "🔍 检查 mkcert 是否已安装..."
if ! command -v mkcert &> /dev/null; then
    echo "❌ mkcert 未安装，请先安装 mkcert"
    echo "Ubuntu/Debian: sudo apt install libnss3-tools && wget https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-v*-linux-amd64 -O mkcert && chmod +x mkcert && sudo cp mkcert /usr/local/bin/"
    echo "或者参考: https://github.com/FiloSottile/mkcert#installation"
    exit 1
fi

echo "✅ mkcert 已安装"

# 初始化本地 CA
echo "🔐 初始化本地证书颁发机构 (CA)..."
mkcert -install

# 创建证书目录
CERTS_DIR="./qdrant/certs"
mkdir -p "$CERTS_DIR"

# 检查证书是否已存在
if [ -f "$CERTS_DIR/qdrant.crt" ] && [ -f "$CERTS_DIR/qdrant.key" ]; then
    echo "⚠️  证书已存在，是否覆盖？(y/N)"
    read -r response
    if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo "跳过证书生成"
        exit 0
    fi
fi

# 生成证书
echo "📝 生成 Qdrant TLS 证书..."
mkcert -cert-file "$CERTS_DIR/qdrant.crt" -key-file "$CERTS_DIR/qdrant.key" \
    localhost \
    127.0.0.1 \
    ::1 \
    qdrant \
    acmg_qdrant \
    *.docker.internal \
    host.docker.internal

echo "✅ 证书生成完成!"

# 检查并更新 .env 文件
echo "🔧 检查 .env 配置..."
if grep -q "^QDRANT_ENABLE_TLS=" .env; then
    # 更新现有的值
    sed -i 's/^QDRANT_ENABLE_TLS=.*/QDRANT_ENABLE_TLS=true/' .env
else
    # 添加新行
    echo "QDRANT_ENABLE_TLS=true" >> .env
fi

if grep -q "^QDRANT_USE_TLS=" .env; then
    sed -i 's/^QDRANT_USE_TLS=.*/QDRANT_USE_TLS=true/' .env
else
    echo "QDRANT_USE_TLS=true" >> .env
fi

if grep -q "^QDRANT_VERIFY_SSL=" .env; then
    sed -i 's/^QDRANT_VERIFY_SSL=.*/QDRANT_VERIFY_SSL=true/' .env
else
    echo "QDRANT_VERIFY_SSL=true" >> .env
fi

echo "✅ .env 文件已更新"

# 显示证书信息
echo ""
echo "📋 证书信息:"
echo "   证书文件: $CERTS_DIR/qdrant.crt"
echo "   私钥文件: $CERTS_DIR/qdrant.key"
echo ""
echo "   有效期: $(openssl x509 -in "$CERTS_DIR/qdrant.crt" -noout -dates | head -n1)"
echo ""

# 提供下一步说明
echo "🚀 完成! 请按以下步骤操作:"
echo "   1. 检查 .env 文件中的 TLS 配置"
echo "   2. 重新启动服务: podman-compose down && podman-compose up -d"
echo "   3. 测试连接: python test_qdrant_fix.py"
echo ""
echo "💡 提示: 如果在生产环境中使用，请确保使用有效的证书而不是自签名证书"