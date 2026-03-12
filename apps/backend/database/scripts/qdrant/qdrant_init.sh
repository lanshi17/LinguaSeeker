#!/bin/bash
# 初始化Qdrant TLS证书链接

# 创建TLS目录（如果不存在）
mkdir -p /qdrant/tls

# 创建证书符号链接以匹配Qdrant默认期望的路径
ln -sf /qdrant/certs/qdrant.crt /qdrant/tls/cert.pem
ln -sf /qdrant/certs/qdrant.key /qdrant/tls/key.pem

echo "✅ TLS证书链接已创建"

# 启动Qdrant（使用原始入口点）
exec /qdrant/entrypoint.sh