#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# 服务器端一键导入术语库（Docker PostgreSQL 容器）
#
# 前置条件：
#   1. 已上传 4 个 .csv.gz 文件到 /tmp/terminology_export/
#   2. PostgreSQL 容器正在运行
#   3. 术语表已通过 alembic migrate 创建（空表）
#
# 用法：
#   chmod +x import_terminology_docker.sh
#   ./import_terminology_docker.sh [PGPASSWORD]
#
#   或直接设环境变量：
#   PGPASSWORD="your_pass" ./import_terminology_docker.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── 配置（按实际情况修改）──────────────────────────────────────────────────
CONTAINER="${PG_CONTAINER:-lingua-postgres}"   # docker ps | grep postgres
DB_USER="${PGUSER:-lingua_seeker}"
DB_NAME="${PGDATABASE:-lingua_seeker}"
PGPASSWORD="${1:-${PGPASSWORD:-}}"

HOST_DIR="/tmp/terminology_export"             # 宿主机 gz 文件目录
CONTAINER_DIR="/tmp/terminology"               # 容器内临时目录

GZ_FILES=(
  terminology_entries.csv.gz
  terminology_aliases.csv.gz
  terminology_relationships.csv.gz
  terminology_embeddings.csv.gz
)
# 导入顺序：先主表再子表（FK 依赖）
IMPORT_ORDER=(
  terminology_entries
  terminology_aliases
  terminology_relationships
  terminology_embeddings
)

# ── 前置检查 ────────────────────────────────────────────────────────────────
echo "════════════════════════════════════════════════════════════"
echo "  术语库导入 → Docker PostgreSQL"
echo "════════════════════════════════════════════════════════════"
echo ""

# 检查密码
if [[ -z "$PGPASSWORD" ]]; then
  echo "❌ 请提供数据库密码："
  echo "   ./import_terminology_docker.sh 'your_password'"
  echo "   或 PGPASSWORD=xxx ./import_terminology_docker.sh"
  exit 1
fi

# 检查容器运行状态
if ! docker inspect "$CONTAINER" &>/dev/null; then
  echo "❌ 容器 $CONTAINER 不存在。请检查："
  echo "   docker ps | grep postgres"
  echo "   然后设置: PG_CONTAINER=实际容器名"
  exit 1
fi
echo "✓ 容器 $CONTAINER 存在"

# 检查宿主机文件
for f in "${GZ_FILES[@]}"; do
  if [[ ! -f "$HOST_DIR/$f" ]]; then
    echo "❌ 缺少文件: $HOST_DIR/$f"
    echo "   请先上传: scp *.csv.gz server:$HOST_DIR/"
    exit 1
  fi
done
echo "✓ 4 个 gz 文件就绪"

# 测试数据库连接
if ! docker exec -e PGPASSWORD="$PGPASSWORD" "$CONTAINER" \
  psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" &>/dev/null; then
  echo "❌ 无法连接数据库 $DB_USER@$DB_NAME"
  echo "   请检查密码和容器状态"
  exit 1
fi
echo "✓ 数据库连接正常"

# 检查表是否存在
TABLE_COUNT=$(docker exec -e PGPASSWORD="$PGPASSWORD" "$CONTAINER" \
  psql -U "$DB_USER" -d "$DB_NAME" -tAc "
  SELECT count(*) FROM information_schema.tables
  WHERE table_schema='lingua_seeker'
    AND table_name IN ('terminology_entries','terminology_aliases',
                       'terminology_relationships','terminology_embeddings')
")
if [[ "$TABLE_COUNT" -ne 4 ]]; then
  echo "❌ 术语表不完整（找到 $TABLE_COUNT/4 张）"
  echo "   请先运行迁移: alembic -c database/alembic.ini upgrade head"
  exit 1
fi
echo "✓ 4 张术语表就绪"

# ── 步骤 1：复制文件进容器 ──────────────────────────────────────────────────
echo ""
echo "── Step 1/4: 复制文件进容器 ──────────────────────────────"
docker exec "$CONTAINER" mkdir -p "$CONTAINER_DIR"

for f in "${GZ_FILES[@]}"; do
  echo "  cp $f → $CONTAINER:$CONTAINER_DIR/"
  docker cp "$HOST_DIR/$f" "$CONTAINER:$CONTAINER_DIR/$f"
done
echo "✓ 文件复制完成"

# ── 步骤 2：导入数据 ────────────────────────────────────────────────────────
echo ""
echo "── Step 2/4: 导入数据 ────────────────────────────────────"

for tbl in "${IMPORT_ORDER[@]}"; do
  gz="$CONTAINER_DIR/${tbl}.csv.gz"
  echo ""
  echo "  ── $tbl"

  # 用 docker exec 管道导入
  start=$SECONDS
  docker exec -e PGPASSWORD="$PGPASSWORD" "$CONTAINER" bash -c \
    "zcat '$gz' | psql -U $DB_USER -d $DB_NAME -c \"\\copy lingua_seeker.$tbl FROM STDIN WITH CSV HEADER\""

  elapsed=$(( SECONDS - start ))
  cnt=$(docker exec -e PGPASSWORD="$PGPASSWORD" "$CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT count(*) FROM lingua_seeker.$tbl")
  echo "  ✓ 导入 $cnt 行，耗时 ${elapsed}s"
done

# ── 步骤 3：更新统计信息 ────────────────────────────────────────────────────
echo ""
echo "── Step 3/4: 更新统计信息 ────────────────────────────────"
docker exec -e PGPASSWORD="$PGPASSWORD" "$CONTAINER" \
  psql -U "$DB_USER" -d "$DB_NAME" -c "
    ANALYZE lingua_seeker.terminology_entries;
    ANALYZE lingua_seeker.terminology_aliases;
    ANALYZE lingua_seeker.terminology_relationships;
    ANALYZE lingua_seeker.terminology_embeddings;
"
echo "✓ ANALYZE 完成"

# ── 步骤 4：验证 & 清理 ────────────────────────────────────────────────────
echo ""
echo "── Step 4/4: 验证 ───────────────────────────────────────"
docker exec -e PGPASSWORD="$PGPASSWORD" "$CONTAINER" \
  psql -U "$DB_USER" -d "$DB_NAME" -c "
    SELECT 'terminology_entries' as table_name, count(*) as rows
      FROM lingua_seeker.terminology_entries
    UNION ALL
    SELECT 'terminology_aliases', count(*) FROM lingua_seeker.terminology_aliases
    UNION ALL
    SELECT 'terminology_relationships', count(*) FROM lingua_seeker.terminology_relationships
    UNION ALL
    SELECT 'terminology_embeddings', count(*) FROM lingua_seeker.terminology_embeddings
    ORDER BY rows DESC;
"

# 清理容器内临时文件
docker exec "$CONTAINER" rm -rf "$CONTAINER_DIR"
echo ""
echo "✓ 容器内临时文件已清理"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ 导入完成"
echo ""
echo "  ⚠ embeddings 仅含元数据，向量列为空。"
echo "  如需生成向量嵌入，在 backend 容器中执行："
echo "    docker exec lingua-backend python -m scripts.data.import.import_terminology \\"
echo "      --terminology-root /app/data/terminology_database \\"
echo "      --version 2026.05 --generate-embeddings"
echo "════════════════════════════════════════════════════════════"
