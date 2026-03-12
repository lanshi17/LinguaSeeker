#!/bin/bash
# 生成Qdrant TLS证书的脚本
# 使用mkcert生成本地信任的证书

set -e  # 遫车模式：任何命令失败时退出

echo "🔍 检查 mkcert 是否已安装..."

if ! command -v mkcert &> /dev/null; then
    echo "❌ mkcert 未安装，正在安装..."
    
    # 检测操作系统
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux 安装
        if command -v apt-get &> /dev/null; then
            sudo apt update && sudo apt install -y libnss3-tools mkcert
        elif command -v yum &> /dev/null; then
            sudo yum install -y mkcert
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y mkcert
        elif command -v pacman &> /dev/null; then
            sudo pacman -S mkcert
        else
            echo "❌ 无法自动安装 mkcert，请手动安装"
            echo "Ubuntu/Debian: sudo apt install mkcert"
            echo "CentOS/RHEL/Fedora: sudo dnf install mkcert 或 sudo yum install mkcert"
            echo "Arch Linux: sudo pacman -S mkcert"
            exit 1
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS 安装
        if command -v brew &> /dev/null; then
            brew install mkcert
        else
            echo "❌ 请先安装 Homebrew 或手动安装 mkcert"
            exit 1
        fi
    else
        echo "❌ 不支持的操作系统，请手动安装 mkcert"
        exit 1
    fi
fi

echo "✅ mkcert 已安装"

# 初始化本地 CA
echo "🔐 初始化本地证书颁发机构 (CA)..."
mkcert -install

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="$SCRIPT_DIR/../qdrant/certs"

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
    *.docker.internal

echo "✅ 证书生成完成!"
echo ""
echo "📁 生成的文件:"
echo "   - $CERTS_DIR/qdrant.crt (证书文件)"
echo "   - $CERTS_DIR/qdrant.key (私钥文件)"
echo ""
echo "🔐 本地 CA 已安装到系统信任库，证书将在浏览器中显示为可信"
echo ""
echo "🔧 要在 Qdrant 中使用这些证书，请确保在配置中启用 TLS 并指向这些文件路径"
echo ""
echo "🔄 如需撤销证书，请运行: mkcert -uninstall"