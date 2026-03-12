#!/bin/bash
# 使用OpenSSL生成自签名证书以便Qdrant使用TLS

set -e  # 任何命令失败时退出

echo "🔐 使用OpenSSL生成自签名证书..."

# 检查OpenSSL是否可用
if ! command -v openssl &> /dev/null; then
    echo "❌ OpenSSL 未安装"
    exit 1
fi

# 创建证书目录
CERTS_DIR="./qdrant/certs"
mkdir -p "$CERTS_DIR"

# 生成私钥
echo "🔑 生成私钥..."
openssl genrsa -out "$CERTS_DIR/qdrant.key" 2048

# 生成证书
echo "📜 生成自签名证书..."
openssl req -new -x509 -key "$CERTS_DIR/qdrant.key" -out "$CERTS_DIR/qdrant.crt" -days 365 -subj "/C=CN/ST=State/L=City/O=Organization/CN=localhost" -addext "subjectAltName=DNS:localhost,DNS:qdrant,DNS:acmg_qdrant,IP:127.0.0.1"

echo "✅ 证书已生成!"
echo ""
echo "📁 证书位置:"
echo "   证书文件: $CERTS_DIR/qdrant.crt"
echo "   私钥文件: $CERTS_DIR/qdrant.key"
echo ""
echo "📝 证书信息:"
openssl x509 -in "$CERTS_DIR/qdrant.crt" -text -noout | head -20

echo ""
echo "🎉 证书生成完成！现在可以启用Qdrant的TLS功能。"