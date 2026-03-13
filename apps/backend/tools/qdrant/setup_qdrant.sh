#!/bin/bash
# 解决Qdrant端口占用问题的脚本

echo "🔍 检查端口6333占用情况..."
lsof -i :6333 2>/dev/null || echo "端口6333未被占用或无法查询"

echo ""
echo "🔧 检查Docker服务状态..."
if systemctl is-active --quiet docker; then
    echo "✅ Docker服务正在运行"
else
    echo "⚠️ Docker服务未运行，尝试启动..."
    sudo systemctl start docker 2>/dev/null || echo "💡 请手动启动Docker服务: sudo systemctl start docker"
fi

echo ""
echo "🐳 检查是否已有Qdrant容器运行..."
if docker ps | grep -q qdrant; then
    echo "⚠️ 发现正在运行的Qdrant容器，先停止它..."
    docker stop qdrant 2>/dev/null || echo "💡 可能需要手动停止容器"
fi

echo ""
echo "🧹 停止可能冲突的Docker容器..."
docker stop qdrant-vector-db 2>/dev/null || echo "💡 qdrant-vector-db容器不存在或已停止"

echo ""
echo "🚀 启动新的Qdrant容器..."
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -e QDRANT_API_KEY="EDhs@gJcftnT3sBU" \
  qdrant/qdrant:latest

if [ $? -eq 0 ]; then
    echo "✅ Qdrant容器已启动"
    echo "⏳ 等待Qdrant服务就绪..."
    sleep 10
    
    echo ""
    echo "🔍 验证Qdrant服务状态..."
    if curl --noproxy localhost -sf http://localhost:6333/healthz > /dev/null 2>&1; then
        echo "✅ Qdrant服务运行正常"
        echo "📊 服务信息:"
        curl --noproxy localhost -s http://localhost:6333/healthz
        echo ""
    else
        echo "⚠️ Qdrant服务可能还未完全就绪，等待额外时间..."
        sleep 15
        if curl --noproxy localhost -sf http://localhost:6333/healthz > /dev/null 2>&1; then
            echo "✅ Qdrant服务现在运行正常"
        else
            echo "❌ Qdrant服务启动失败，请检查Docker日志"
            docker logs qdrant
        fi
    fi
else
    echo "❌ 无法启动Qdrant容器，请检查Docker配置"
fi

echo ""
echo "📋 当前端口6333状态:"
lsof -i :6333 2>/dev/null || echo "端口6333未被占用或无法查询"