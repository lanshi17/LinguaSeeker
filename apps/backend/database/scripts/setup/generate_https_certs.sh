#!/bin/bash
# 为Qdrant服务创建SSL证书以便使用HTTPS访问
# 使用mkcert生成本地信任的证书

set -e  # 任何命令失败时退出

echo "🔐 为Qdrant服务创建SSL证书以支持HTTPS访问"
echo ""

# 检查是否在正确的目录中
if [ ! -f ".env" ]; then
    echo "❌ 请在项目根目录中运行此脚本"
    exit 1
fi

# 检查mkcert是否已安装
echo "🔍 检查 mkcert 是否已安装..."
if ! command -v mkcert &> /dev/null; then
    echo "❌ mkcert 未安装，正在安装..."

    if command -v apt-get &> /dev/null; then
        # Ubuntu/Debian
        sudo apt update
        sudo apt install -y libnss3-tools wget curl
        MKCERT_URL=$(curl -s https://api.github.com/repos/FiloSottile/mkcert/releases/latest | grep browser_download_url | grep linux-amd64 | cut -d '"' -f 4)
        wget $MKCERT_URL -O mkcert
        chmod +x mkcert
        sudo mv mkcert /usr/local/bin/mkcert
    elif command -v dnf &> /dev/null; then
        # Fedora/RHEL
        sudo dnf install -y mkcert
    elif command -v pacman &> /dev/null; then
        # Arch Linux
        sudo pacman -S mkcert
    elif command -v brew &> /dev/null; then
        # macOS with Homebrew
        brew install mkcert
    else
        echo "❌ 无法自动安装 mkcert，请手动安装"
        echo "Ubuntu/Debian: sudo apt install libnss3-tools && curl -L https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-*_linux_amd64 -o mkcert && chmod +x mkcert && sudo mv mkcert /usr/local/bin/"
        exit 1
    fi
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

# 生成证书 - 包括常见的主机名以便HTTPS访问
echo "📝 生成 Qdrant HTTPS 证书..."
mkcert -cert-file "$CERTS_DIR/qdrant.crt" -key-file "$CERTS_DIR/qdrant.key" \
    localhost \
    127.0.0.1 \
    ::1 \
    qdrant \
    acmg_qdrant \
    *.docker.internal \
    host.docker.internal \
    acmg.local \
    qdrant.acmg.local

echo "✅ 证书生成完成!"

# 显示证书信息
echo ""
echo "📋 证书信息:"
echo "   证书文件: $CERTS_DIR/qdrant.crt"
echo "   私钥文件: $CERTS_DIR/qdrant.key"
echo ""
echo "   有效期: $(openssl x509 -in "$CERTS_DIR/qdrant.crt" -noout -dates | head -n1)"
echo ""

# 更新环境变量配置
echo "🔧 更新环境变量配置..."
if grep -q "^QDRANT_ENABLE_TLS=" .env; then
    sed -i 's/^QDRANT_ENABLE_TLS=.*/QDRANT_ENABLE_TLS=true/' .env
else
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

# 更新Podman Compose配置
echo "🔧 更新 Podman Compose 配置..."

# 备份原文件
cp podman-compose.yml podman-compose.yml.backup

# 更新配置
sed -i 's/QDRANT__SERVICE__ENABLE_TLS: ${QDRANT_ENABLE_TLS:-"false"}/QDRANT__SERVICE__ENABLE_TLS: ${QDRANT_ENABLE_TLS:-"true"}/' podman-compose.yml

echo "✅ 配置已更新"

# 提供访问说明
echo ""
echo "🌐 HTTPS 访问说明:"
echo "   1. Qdrant HTTP 端点: https://localhost:6333"
echo "   2. Qdrant gRPC 端点: grpcs://localhost:6334"
echo ""
echo "   由于使用的是本地信任的证书，浏览器将不会显示安全警告"
echo ""
echo "🚀 完成! 请按以下步骤操作:"
echo "   1. 检查 .env 文件中的 TLS 配置"
echo "   2. 重新启动服务: podman-compose down && podman-compose up -d"
echo "   3. 测试 HTTPS 连接: curl -k https://localhost:6333/healthz"
echo ""
echo "💡 提示: 在生产环境中，请使用有效的CA签发的证书而不是自签名证书"