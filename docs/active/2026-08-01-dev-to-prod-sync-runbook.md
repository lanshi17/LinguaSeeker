# dev → prod 数据库同步 Runbook

> 首次走通: 2026-08-01(sync_bundle_batch_20260801_094627,~134k 行)

## 0. 概述

dev 数据库是数据写入的**唯一来源**,prod 是只读副本(供搜索/查询)。
本流程做**单向增量同步**:dev 写入 → 打包 bundle → 传输到 prod → upsert。
**prod 独立产生的数据绝不会被删除**(协议保证)。

## 1. 前置条件

| 项 | dev 端 | prod 端 |
|---|---|---|
| 工具 | `psql` + `bash` | 容器 `pgvector/pgvector:pg18`(自带 psql) |
| DB 凭证 | 从 `backend/config/vault/development.yaml` 读 | 容器内 `$POSTGRES_PASSWORD` env |
| 网络 | 本地 `127.0.0.1:5432` 直连 | 经 `docker exec` 进入容器内操作 |
| 用户/库 | `lingua_seeker` / `dev_lingua_seeker` | `lingua_seeker` / `lingua_seeker` |

**关键约定**:
- 业务表 schema 名固定 `lingua_seeker`(per CLAUDE.md §28.1)
- dev 库 + prod 库通过 `frontend_search_index` 行数比对大致估算增量规模
- 每次 export 在 `MANIFEST` 写入 `next_since`,作为下次 export 的 `--since`

## 2. 流程图

```
┌──────────────────┐                    ┌──────────────────┐
│   DEV (本地)     │                    │  PROD (服务器)   │
│  127.0.0.1:5432  │                    │ 容器: backend-   │
│  dev_lingua_seeker│                   │ host-postgres-1  │
└────────┬─────────┘                    └────────┬─────────┘
         │                                       │
   [1] export                                  │
   bash sync_dev_to_prod.sh                    │
   export --since <ts>                         │
   --out data/sync_bundle_X                    │
         │                                       │
   [2] tar.gz                                  │
         │                                       │
   [3] scp ./data/sync_bundle_X.tar.gz ────►  ssh + tar + docker cp
                                            [4] docker exec
                                                bash sync_dev_to_prod.sh
                                                import --in sync_bundle_X
                                                (PG* env from container)
                                                → COMMIT
                                            [5] 重建 read models
                                                (a) frontend_search_index
                                                    bash sync_dev_to_prod.sh
                                                    refresh-search-index
                                                (b) literature_profiles
                                                    uv run python
                                                    refresh_business_read_models.py
```

## 3. 完整步骤

### 3.1 dev 端:export 增量 bundle

```bash
cd /home/yangzs/Projects/01_ACMG_Lingua

PGPASSWORD="$(grep -A2 'postgres:' backend/config/vault/development.yaml \
    | grep password | head -1 | sed -E 's/.*password:\s*"?([^"]*)".*/\1/')" \
PGHOST=127.0.0.1 PGPORT=5432 \
PGUSER=lingua_seeker PGDATABASE=dev_lingua_seeker \
    bash scripts/sync_dev_to_prod.sh export \
        --since '<NEXT_SINCE>' \
        --out data/sync_bundle_<LABEL>
```

- `<NEXT_SINCE>` 第一次用 prod 端的 restore 时间(可以从 `pg_restore --list` 或 `pg_stat_activity` 推断),之后用上次 `MANIFEST` 里的 `next_since`
- `<LABEL>` 建议带日期,例 `incremental_20260801`

### 3.2 dev 端:打包 tarball(便于传输 + 含脚本)

```bash
BUNDLE="data/sync_bundle_<LABEL>"
TARBALL="${BUNDLE}.tar.gz"
tar -czf "$TARBALL" \
    -C "$(pwd)/data" "$(basename "$BUNDLE")" \
    -C "$(pwd)" "scripts/sync_dev_to_prod.sh"
```

### 3.3 传输到 prod 服务器

```bash
scp "$TARBALL" <USER>@<SERVER>:/tmp/
```

### 3.4 prod 端:进入容器 + import bundle

```bash
# 1) 拷进容器
docker cp /tmp/$TARBALL backend-host-postgres-1:/tmp/

# 2) 容器内解压
docker exec -it backend-host-postgres-1 bash -c '
    cd /tmp
    tar -xzf '"$TARBALL"'
'

# 3) import(容器内 PG* env 自动可用)
docker exec -it backend-host-postgres-1 bash -c '
    cd /tmp
    PGPASSWORD="$POSTGRES_PASSWORD" \
    PGUSER=lingua_seeker PGDATABASE=lingua_seeker \
    PGHOST=127.0.0.1 PGPORT=5432 \
        bash sync_dev_to_prod.sh import --in '"$BUNDLE_DIR"'
'
```

**预期输出**(成功):
```
Import complete.
NOTE: session_replication_role=replica also skipped user triggers.
      After import, rebuild read models:
        1. frontend_search_index (pure SQL, no Python needed)
        2. literature_profiles (per-document Python refresh)
```

### 3.5 prod 端:重建 read models(必须)

> import 用了 `session_replication_role=replica` 跳过 FK/trigger,read model 没自动更新。

#### 3.5.1 `frontend_search_index`(纯 SQL,无 Python 依赖)

```bash
bash scripts/sync_dev_to_prod.sh refresh-search-index \
    | docker exec -i backend-host-postgres-1 \
        env PGPASSWORD="$POSTGRES_PASSWORD" \
        psql -U lingua_seeker -d lingua_seeker
```

> 也可以直接在服务器上 `bash scripts/sync_dev_to_prod.sh refresh-search-index` 看 SQL,再手动管道到 psql。

#### 3.5.2 `literature_profiles`(需 Python,可选)

无 Python 环境时的方案:用 SSH 隧道从本地 dev 机器跑。

```bash
# 本地(django/dev)开 SSH 隧道
ssh -L 55432:127.0.0.1:5432 <USER>@<SERVER>

# 另开一个本地 shell
cd /home/yangzs/Projects/01_ACMG_Lingua
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=55432
export POSTGRES_DB=lingua_seeker
export POSTGRES_USER=lingua_seeker
export POSTGRES_PASSWORD='<prod-vault-password>'
export POSTGRES_SCHEMA=lingua_seeker

cd backend && uv run python ../scripts/refresh_business_read_models.py
```

**预期输出**:
```
Refreshing literature_profiles ...
  Found N source documents
  Refreshed N/N literature profiles
Refreshing frontend_search_index ...
  frontend_search_index: N rows
  ...
  literature_profiles: N
  frontend_search_index: N
  source_documents: N
  canonical_evidence_items: N
  run_evidence_items: N
  processing_runs: N
Done.
```

### 3.6 清理

```bash
# 容器内
docker exec backend-host-postgres-1 \
    rm -rf /tmp/sync_bundle_<LABEL> \
           /tmp/sync_dev_to_prod.sh \
           /tmp/$TARBALL

# 服务器 /tmp
rm -f /tmp/$TARBALL
```

## 4. 关键设计要点

### 4.1 为什么用 CSV bundle 而不是 `pg_dump`?

| 维度 | CSV bundle(本流程) | pg_dump |
|---|---|---|
| 语义 | 增量 upsert(无破坏) | 全量覆盖(`--clean` 会 DROP) |
| 适合 | dev → prod 周期同步 | 首次 bootstrap / 灾难恢复 |
| 协议保障 | prod 独立数据保留 | prod 数据全删 |

### 4.2 `normalized_entities` 为何需要两阶段合并?

prod 上有 **partial unique index**:
```sql
CREATE UNIQUE INDEX uq_normalized_entities_standardized_external_id
  ON normalized_entities (entity_type, external_id)
  WHERE external_id IS NOT NULL AND standardization_status = 'standardized';
```

即"同一 (entity_type, external_id) 在标准化状态下只能有 1 个 entity_id"。
通用 upsert(`ON CONFLICT (entity_id)`)只处理主键冲突,处理不了这个 unique index。
所以分两步:
1. **Phase 1**: `UPDATE ... WHERE t.entity_id = s.entity_id` — dev 端 entity_id 已存在于 prod,直接更新 prod 数据
2. **Phase 2a**: `INSERT ... WHERE NOT EXISTS (... entity_id)` — 新行
3. **Phase 2b**: `INSERT ... ON CONFLICT (entity_type, external_id) WHERE ...` —
   - dev 行 (entity_type, external_id) 与 prod 撞(但 entity_id 不同)
   - 用 dev 数据更新 prod 行
   - **不覆盖 prod 的 entity_id**(否则 `entity_merge_events` / `evidence_entity_bindings` 等 FK 断裂)

### 4.3 容器内 `psql` 的连接陷阱

容器里 `psql` 默认:
- 用户 = 当前 unix user(`root` —— 容器内没 `lingua_seeker` 角色)
- 库 = 用户同名(没有 `root` 库)
- 主机 = `/var/run/postgresql/.s.PGSQL.5432` unix socket(可能没权限)

**必须显式**:
```bash
PGHOST=127.0.0.1 PGPORT=5432 \
PGUSER=lingua_seeker PGDATABASE=lingua_seeker \
PGPASSWORD=$POSTGRES_PASSWORD
```

### 4.4 `session_replication_role=replica` 的副作用

import 期间为了批量插入绕过 FK 检查,设了这个 role。它的副作用:
- **跳过 user triggers** —— `frontend_search_index` 之类的 trigger-maintained 表可能不会自动更新
- **不影响数据** —— 只是衍生表没同步,主表数据完整

→ 必须在 import 后手动重建 read models。

## 5. 故障排查

| 症状 | 原因 | 修复 |
|---|---|---|
| `function _sync_upsert(regclass, regclass) does not exist` | search_path 不含 pg_temp | `PGOPTIONS="-c search_path=public,pg_temp"` 或在脚本里把 `SELECT _sync_upsert(...)` 改成 `SELECT pg_temp._sync_upsert(...)`(已修) |
| `duplicate key value violates unique constraint "uq_..."` | 通用 upsert 撞 prod 二级唯一约束 | 见 §4.2 两阶段合并(已针对 normalized_entities 处理) |
| `database "dev_lingua_seeker" does not exist` | 在 prod 上用了 dev 配置 | `ENVIRONMENT=production` 或显式 `POSTGRES_DB=lingua_seeker` |
| `FATAL: role "root" does not exist` | 容器内未设 `PGUSER` | 设 `PGUSER=lingua_seeker` |
| import 完成后搜索无新文档 | `frontend_search_index` stale | 跑 §3.5.1 |
| import 完成后详情页统计数字错 | `literature_profiles` stale | 跑 §3.5.2 |

## 6. 周期与监控

- **频率**: 取决于 dev 端数据写入速度。本次 4 天(~150k 行)
- **监控点**:
  - dev 端 `next_since` 间隔
  - import 输出的 `rows_written` 与 dev export 的 `COPY N` 差异
  - prod 端 `source_documents.updated_at` 最近值
- **不变量检查**(每次 import 后):
  - `prod.source_documents.count` ≥ 上次值
  - `prod.frontend_search_index.count` ≈ `prod.canonical_evidence_items.count`
  - `prod.literature_profiles.count` ≈ `prod.source_documents.count`

## 7. 变更历史

| 日期 | 变更 | 作者 |
|---|---|---|
| 2026-08-01 | 首次走通;`sync_dev_to_prod.sh` 加 `normalized_entities` 两阶段合并 + `refresh-search-index` 子命令;写本 runbook | AI + maintainer |
