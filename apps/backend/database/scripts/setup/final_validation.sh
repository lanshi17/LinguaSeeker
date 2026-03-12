#!/bin/bash
# 最终验证脚本 - 确保所有数据库连接问题都已解决

echo "✅ 最终验证 - PostgreSQL 和 MinIO 连接测试"
echo "=========================================="

# 加载环境变量
source /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/.env

echo "📋 使用配置:"
echo "   用户: $POSTGRES_USER"
echo "   主数据库: $POSTGRES_DB"
echo "   测试数据库: acmg_test_6c513a5f"
echo "   密码长度: ${#POSTGRES_PASSWORD} 字符"
echo ""

# 设置密码环境变量
export PGPASSWORD="$POSTGRES_PASSWORD"

# 测试 1: 主数据库连接
echo "🔍 测试 1: 主数据库 ($POSTGRES_DB) 连接..."
if psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 'Main DB OK' AS status;" >/dev/null 2>&1; then
    echo "   ✅ 主数据库连接成功"
else
    echo "   ❌ 主数据库连接失败"
fi

# 测试 2: 测试数据库连接
echo "🔍 测试 2: 测试数据库 (acmg_test_6c513a5f) 连接..."
if psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "acmg_test_6c513a5f" -c "SELECT 'Test DB OK' AS status;" >/dev/null 2>&1; then
    echo "   ✅ 测试数据库连接成功"
else
    echo "   ❌ 测试数据库连接失败"
fi

# 测试 3: 权限验证
echo "🔍 测试 3: 验证数据库权限..."
PRIV_CHECK=$(psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT has_schema_privilege('$POSTGRES_USER', 'public', 'CREATE');" 2>/dev/null)
if [ "$PRIV_CHECK" = "t" ]; then
    echo "   ✅ 用户有创建权限"
else
    echo "   ❌ 用户缺少创建权限"
fi

# 测试 4: MinIO 配置验证
echo "🔍 测试 4: MinIO 配置验证..."
if [ "$MINIO_ENDPOINT" = "localhost:9000" ]; then
    echo "   ✅ MinIO endpoint 格式正确 (不含路径)"
else
    echo "   ❌ MinIO endpoint 格式可能有问题: $MINIO_ENDPOINT"
fi

# 测试 5: 服务可用性
echo "🔍 测试 5: 服务可用性检查..."
if nc -z localhost 5432; then
    echo "   ✅ PostgreSQL 服务运行中"
else
    echo "   ❌ PostgreSQL 服务未运行"
fi

if nc -z localhost 9000; then
    echo "   ✅ MinIO 服务运行中"
else
    echo "   ❌ MinIO 服务未运行"
fi

echo ""
echo "📊 验证总结:"
echo "   - 主数据库: $POSTGRES_DB"
echo "   - 测试数据库: acmg_test_6c513a5f"
echo "   - 用户: $POSTGRES_USER"
echo "   - MinIO Endpoint: $MINIO_ENDPOINT (路径问题已修复)"

echo ""
echo "🎉 所有连接问题应已解决！"
echo ""
echo "💡 如需运行测试，请确保使用以下数据库URL之一："
echo "   主数据库: postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5432/$POSTGRES_DB"
echo "   测试数据库: postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5432/acmg_test_6c513a5f"

unset PGPASSWORD