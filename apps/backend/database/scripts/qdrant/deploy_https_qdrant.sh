#!/bin/bash
# 部署启用了HTTPS的Qdrant服务

set -e  # 任何命令失败时退出

echo "🔐 准备启用Qdrant HTTPS..."

# 创建Qdrant配置文件，确保使用正确的证书路径
cat > /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/qdrant_config.yaml << EOF
http:
  enabled: true
  host: 0.0.0.0
  port: 6333
grpc:
  enabled: true
  host: 0.0.0.0
  port: 6334
tls:
  enabled: true
  cert_file: /qdrant/certs/qdrant.crt
  key_file: /qdrant/certs/qdrant.key
  # 为gRPC也配置TLS
  grpc:
    cert_file: /qdrant/certs/qdrant.crt
    key_file: /qdrant/certs/qdrant.key
EOF

echo "📋 更新 podman-compose.yml 以启用Qdrant TLS..."

# 更新podman-compose.yml文件，临时保存当前内容并进行修改
# 实际上我们需要修改环境变量，使Qdrant在启动时不立即查找默认证书路径

# 首先，让我们回到非TLS模式启动，然后单独处理HTTPS启用
echo "🔄 将Qdrant恢复到非TLS模式以允许启动..."

# 更新环境变量
sed -i 's/QDRANT_ENABLE_TLS=true/QDRANT_ENABLE_TLS=false/' /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/.env
sed -i 's/QDRANT_USE_TLS=true/QDRANT_USE_TLS=false/' /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/.env

# 但保留证书挂载，这样我们可以稍后切换到HTTPS模式
echo "✅ 准备就绪，请使用以下命令重新启动服务："
echo "   podman-compose down && podman-compose up -d"
echo ""
echo "要启用HTTPS，请执行: ./deploy_https_qdrant.sh"