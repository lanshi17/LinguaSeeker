#!/bin/bash
# 设置Podman系统级代理配置以绕过本地代理

set -e  # 任何命令失败时退出

echo "🔧 配置Podman以绕过本地代理..."

# 创建Podman配置目录（如果不存在）
CONFIG_DIR="$HOME/.config/containers"
mkdir -p "$CONFIG_DIR"

# 复制配置文件到正确的位置
cp ./containers.conf "$CONFIG_DIR/"

echo "✅ Podman代理配置已更新"
echo ""
echo "📝 配置详情:"
echo "   - 已设置 no_proxy 以绕过本地地址"
echo "   - 配置文件位置: $CONFIG_DIR/containers.conf"
echo ""
echo "🔄 要使配置生效，您可能需要重启正在运行的容器"
echo "   podman-compose down && podman-compose up -d"