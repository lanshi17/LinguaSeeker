#!/bin/bash
# PostgreSQL 测试数据库权限修复脚本

echo "🔧 修复 PostgreSQL 测试数据库权限问题"
echo ""

# 从环境文件加载配置
source /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/.env

echo "📋 当前配置:"
echo "POSTGRES_USER: $POSTGRES_USER"
echo "POSTGRES_DB: $POSTGRES_DB"
echo "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD/#????????????/****}"

# 设置密码环境变量
export PGPASSWORD="$POSTGRES_PASSWORD"

echo ""
echo "🔍 检查所有数据库..."

# 列出所有数据库
ALL_DATABASES=$(psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT datname FROM pg_database WHERE NOT datistemplate;" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "✅ 可用数据库:"
    echo "$ALL_DATABASES" | while read db; do
        if [ -n "$db" ]; then
            echo "  - $db"
        fi
    done
else
    echo "❌ 无法获取数据库列表"
fi

# 检查特定的测试数据库是否存在
TEST_DB_NAME="acmg_test_6c513a5f"
echo ""
echo "🔍 检查测试数据库 $TEST_DB_NAME 是否存在..."

TEST_DB_EXISTS=$(psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_database WHERE datname = '$TEST_DB_NAME';" 2>/dev/null)
if [ "$TEST_DB_EXISTS" = "1" ]; then
    echo "✅ 测试数据库 $TEST_DB_NAME 存在"
    
    # 检查 acmg_user 对测试数据库的权限
    HAS_CONNECT_PRIV=$(psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT has_database_privilege('$POSTGRES_USER', '$TEST_DB_NAME', 'CONNECT');" 2>/dev/null)
    if [ "$HAS_CONNECT_PRIV" = "t" ]; then
        echo "✅ $POSTGRES_USER 对 $TEST_DB_NAME 有连接权限"
    else
        echo "❌ $POSTGRES_USER 对 $TEST_DB_NAME 没有连接权限"
        echo "💡 尝试授予连接权限..."
        
        # 尝试授予连接权限
        RESULT=$(psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "GRANT CONNECT ON DATABASE $TEST_DB_NAME TO $POSTGRES_USER;" 2>&1)
        if [ $? -eq 0 ]; then
            echo "✅ 连接权限已授予"
        else
            echo "❌ 授予权限失败: $RESULT"
            echo "💡 这可能是因为当前用户没有足够的权限来授予其他数据库的权限"
        fi
    fi
else
    echo "❌ 测试数据库 $TEST_DB_NAME 不存在"
    echo "💡 测试框架可能在运行时动态创建此数据库"
fi

echo ""
echo "🔧 建议的解决方案:"

echo "1. 如果是测试数据库权限问题:"
echo "   - 确保测试配置使用正确的主数据库 ($POSTGRES_DB)"
echo "   - 检查测试框架配置，可能需要调整测试数据库创建逻辑"

echo ""
echo "2. 如果测试框架自动创建数据库，确保:"
echo "   - 主数据库用户 ($POSTGRES_USER) 有创建数据库的权限"
echo "   - 在连接到主数据库后，再创建临时测试数据库"

echo ""
echo "3. SQLAlchemy 测试配置建议:"
echo "   # 在 SQLAlchemy 测试配置中使用模板数据库"
echo "   TEST_DATABASE_URL = f\"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:5432/{POSTGRES_DB}_test\""
echo "   # 或者使用内存数据库（如果适用）"

echo ""
echo "4. 验证当前用户权限:"
CAN_CREATE_DB=$(psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT rolsuper OR rolcreatedb FROM pg_roles WHERE rolname = current_user;" 2>/dev/null)
if [ "$CAN_CREATE_DB" = "t" ]; then
    echo "✅ 当前用户 $POSTGRES_USER 有创建数据库的权限"
else
    echo "❌ 当前用户 $POSTGRES_USER 没有创建数据库的权限"
    echo "💡 可能需要使用超级用户权限创建测试数据库"
fi

echo ""
echo "📋 如果测试继续失败，请检查应用程序的数据库配置文件，确保:"
echo "   - 数据库 URL 格式正确"
echo "   - 密码中的特殊字符被正确处理"
echo "   - 测试数据库创建逻辑正确"

unset PGPASSWORD