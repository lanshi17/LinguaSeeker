#!/bin/bash
# 创建和配置 PostgreSQL 测试数据库

echo "🔧 创建 PostgreSQL 测试数据库"
echo ""

# 从环境文件加载配置
source /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/.env

echo "📋 当前配置:"
echo "POSTGRES_USER: $POSTGRES_USER"
echo "POSTGRES_DB: $POSTGRES_DB"
echo "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD/#????????????/****}"

# 设置密码环境变量
export PGPASSWORD="$POSTGRES_PASSWORD"

TEST_DB_NAME="acmg_test_6c513a5f"

echo ""
echo "🔍 检查测试数据库 $TEST_DB_NAME 是否存在..."

# 检查测试数据库是否存在
TEST_DB_EXISTS=$(psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_database WHERE datname = '$TEST_DB_NAME';" 2>/dev/null)

if [ "$TEST_DB_EXISTS" = "1" ]; then
    echo "✅ 测试数据库 $TEST_DB_NAME 已存在"
else
    echo "❌ 测试数据库 $TEST_DB_NAME 不存在，正在创建..."
    
    # 尝试创建测试数据库
    RESULT=$(createdb -h localhost -p 5432 -U "$POSTGRES_USER" -O "$POSTGRES_USER" "$TEST_DB_NAME" 2>&1)
    if [ $? -eq 0 ]; then
        echo "✅ 测试数据库 $TEST_DB_NAME 创建成功"
    else
        echo "❌ 测试数据库创建失败: $RESULT"
        echo "💡 尝试使用容器内部创建..."
        
        # 尝试通过容器内部创建数据库
        CONTAINER_RESULT=$(podman exec acmg_postgres createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" "$TEST_DB_NAME" 2>&1)
        if [ $? -eq 0 ]; then
            echo "✅ 通过容器内部成功创建测试数据库 $TEST_DB_NAME"
        else
            echo "❌ 通过容器内部创建测试数据库也失败: $CONTAINER_RESULT"
            echo "💡 可能需要检查用户权限或容器连接"
        fi
    fi
fi

# 检查并设置权限
echo ""
echo "🔧 设置测试数据库权限..."

# 确保 acmg_user 对测试数据库有连接权限
GRANT_RESULT=$(psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "GRANT ALL PRIVILEGES ON DATABASE $TEST_DB_NAME TO $POSTGRES_USER;" 2>&1)
if [ $? -eq 0 ]; then
    echo "✅ 权限设置成功"
else
    echo "⚠️ 权限设置可能失败: $GRANT_RESULT"
    echo "💡 这可能不影响连接，因为用户是数据库所有者"
fi

# 验证连接
echo ""
echo "🔍 验证到测试数据库的连接..."

if PGPASSWORD="$POSTGRES_PASSWORD" psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$TEST_DB_NAME" -c "SELECT current_user, current_database();" >/dev/null 2>&1; then
    echo "✅ 可以成功连接到测试数据库 $TEST_DB_NAME"
else
    echo "❌ 无法连接到测试数据库 $TEST_DB_NAME"
    echo "💡 这可能是由于权限或认证问题"
fi

# 检查测试数据库中是否需要创建模式或枚举
echo ""
echo "🔧 在测试数据库中设置基本结构..."

# 连接到测试数据库并检查是否需要创建枚举类型
SETUP_RESULT=$(psql -h localhost -p 5432 -U "$POSTGRES_USER" -d "$TEST_DB_NAME" -c "
-- 创建测试数据库需要的枚举类型（如果不存在）
DO \$\$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tasktype') THEN
        CREATE TYPE tasktype AS ENUM ('PDF_PARSE', 'IDENTIFIER_RESOLVE', 'DATA_EXTRACTION');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taskstage') THEN
        CREATE TYPE taskstage AS ENUM ('INGESTION', 'PROCESSING', 'COMPLETED', 'FAILED');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taskstatus') THEN
        CREATE TYPE taskstatus AS ENUM ('PENDING', 'RUNNING', 'SUCCESS', 'ERROR');
    END IF;
EXCEPTION
    WHEN duplicate_object THEN
        RAISE NOTICE 'Type already exists, continuing...';
END\$\$;

-- 为当前用户授予 schema 权限
GRANT ALL ON SCHEMA public TO $POSTGRES_USER;
" 2>&1)

if [ $? -eq 0 ]; then
    echo "✅ 测试数据库基本结构设置成功"
else
    echo "⚠️ 结构设置可能有警告: $SETUP_RESULT"
fi

echo ""
echo "✅ 测试数据库 $TEST_DB_NAME 准备就绪！"

echo ""
echo "💡 对于 SQLAlchemy 测试配置，您可以使用:"
echo "   DATABASE_URL = \"postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5432/$TEST_DB_NAME\""

echo ""
echo "📋 额外提示:"
echo "   - 如果测试框架自动创建和删除测试数据库，确保用户有足够权限"
echo "   - 某些测试框架可能需要特定的数据库后缀（如 _test）"
echo "   - 检查应用程序的测试配置文件以确保使用正确的数据库名称"

unset PGPASSWORD