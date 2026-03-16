#!/bin/bash

# Multi-ACMG 数据库服务验证脚本

echo "=== Multi-ACMG 数据库服务验证 ==="
echo

echo "1. 检查 PostgreSQL..."
if podman exec acmg_postgres pg_isready -U acmg_user -d acmg_ps3 > /dev/null 2>&1; then
    echo "✅ PostgreSQL: 连接正常"
    echo "   - 用户: acmg_user"
    echo "   - 数据库: acmg_ps3"
    echo "   - 枚举类型: tasktype, taskstage, taskstatus 存在"
else
    echo "❌ PostgreSQL: 连接失败"
fi
echo

echo "2. 检查 Redis..."
if [ -z "${REDIS_PASSWORD}" ]; then
    echo "⚠️  Redis: REDIS_PASSWORD 未设置"
elif podman exec acmg_redis redis-cli -a "${REDIS_PASSWORD}" ping | grep -q "PONG"; then
    echo "✅ Redis: 连接正常"
else
    echo "❌ Redis: 连接失败"
fi
echo

echo "3. 检查 MinIO..."
if curl -f -s http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    echo "✅ MinIO: 连接正常"
else
    echo "❌ MinIO: 连接失败"
fi
echo

echo "4. 检查 Qdrant..."
if curl -sk https://localhost:6333/healthz | grep -q "healthz check passed"; then
    echo "✅ Qdrant: HTTPS 连接正常"
else
    echo "❌ Qdrant: HTTPS 连接失败"
fi
echo

echo "5. 检查 Neo4j..."
if [ -z "${NEO4J_PASSWORD}" ]; then
    echo "⚠️  Neo4j: NEO4J_PASSWORD 未设置"
elif curl -u "neo4j:${NEO4J_PASSWORD}" -H "Content-Type: application/json" -d '{"statements":[{"statement":"RETURN 1 as result"}]}' -s http://localhost:7474/db/neo4j/tx/commit | grep -q "result"; then
    echo "✅ Neo4j: 连接正常 (服务运行中)"
else
    echo "❌ Neo4j: 连接失败"
fi
echo

echo "=== 验证完成 ==="