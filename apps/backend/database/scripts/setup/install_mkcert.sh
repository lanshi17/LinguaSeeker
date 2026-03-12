#!/bin/bash
# 安装mkcert工具

set -e  # 任何命令失败时退出

echo "🔧 安装 mkcert 工具..."

# 检测系统架构
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        MKCERT_ARCH="linux-amd64"
        ;;
    aarch64|arm64)
        MKCERT_ARCH="linux-arm64"
        ;;
    *)
        echo "❌ 不支持的架构: $ARCH"
        exit 1
        ;;
esac

echo "📦 检测到架构: $ARCH"

# 下载mkcert
echo "⬇️  下载 mkcert..."
MKCERT_URL="https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-$(uname -s)-$(uname -m)"

# 尝试下载mkcert二进制文件
if command -v curl &> /dev/null; then
    curl -L -o mkcert "$MKCERT_URL"
elif command -v wget &> /dev/null; then
    wget "$MKCERT_URL" -O mkcert
else
    echo "❌ 未找到 curl 或 wget"
    exit 1
fi

# 设置执行权限
chmod +x mkcert

# 移动到系统路径
sudo mv mkcert /usr/local/bin/

echo "✅ mkcert 安装完成！"

# 验证安装
mkcert -version

echo ""
echo "🔐 初始化本地证书颁发机构..."
mkcert -install

echo ""
echo "✅ mkcert 准备就绪！"