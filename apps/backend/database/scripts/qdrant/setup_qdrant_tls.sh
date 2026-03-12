#!/bin/bash
# 为Qdrant生成TLS证书的脚本
# 使用mkcert生成本地信任的证书

set -e  # 任何命令失败时退出

echo "🔍 检查 mkcert 是否已安装..."

if ! command -v mkcert &> /dev/null; then
    echo "❌ mkcert 未安装，正在安装..."

    # 检测操作系统并安装mkcert
    if command -v apt-get &> /dev/null; then
        # Ubuntu/Debian
        sudo apt update
        sudo apt install -y libnss3-tools wget
        # 下载并安装mkcert
        wget https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-v*-linux-amd64
        chmod +x mkcert-v*-linux-amd64
        sudo mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert
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
        echo "参考: https://github.com/FiloSottile/mkcert#installation"
        exit 1
    fi
fi

echo "✅ mkcert 已安装"

# 初始化本地 CA
echo "🔐 初始化本地证书颁发机构 (CA)..."
mkcert -install

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="$SCRIPT_DIR/qdrant/certs"

echo "📂 证书目录: $CERTS_DIR"

# 创建证书目录
mkdir -p "$CERTS_DIR"

# 生成证书 - 包括常见的主机名
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
echo ""
echo "📁 生成的文件:"
echo "   - $CERTS_DIR/qdrant.crt (证书文件)"
echo "   - $CERTS_DIR/qdrant.key (私钥文件)"
echo ""
echo "🔐 本地 CA 已安装到系统信任库，证书将在浏览器中显示为可信"
echo ""
echo "🔧 要在 Qdrant 中使用这些证书，请确保:"
echo "   1. 在 .env 文件中设置 QDRANT_ENABLE_TLS=true"
echo "   2. 重新启动 Qdrant 服务以加载新证书"
echo ""
echo "🔄 如需撤销证书，请运行: mkcert -uninstall"