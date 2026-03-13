# Database 目录

本目录包含 Multi-ACMG 项目后端的所有数据库相关配置、脚本和初始化文件。

## 目录结构

```
database/
├── alembic/                 # Alembic 数据库迁移工具配置
│   ├── env.py              # Alembic 运行环境配置
│   ├── script.py.mako      # 迁移脚本模板
│   └── versions/           # 数据库版本迁移脚本
│       ├── 20260226_01_fix_evidence_records.py
│       ├── 20260227_01_structural_variant_workflow.py
│       ├── 20260303_01_m0_request_paper_tables.py
│       └── 20260306_01_task_status_workflow_fields.py
├── config/                  # 配置文件目录
│   ├── .env                # 环境变量配置（数据库密码等敏感信息）
│   ├── .env.corrected      # 修正后的环境变量配置
│   ├── .env.example        # 环境变量配置示例
│   ├── .env.neo4j          # Neo4j 专用配置
│   ├── containers.conf     # 容器配置文件
│   └── qdrant_config.json  # Qdrant 向量数据库配置
├── init-scripts/            # 容器初始化脚本目录（挂载到 PostgreSQL）
├── minio/                   # MinIO 对象存储配置
│   ├── certs/              # MinIO TLS 证书
│   ├── minio.license       # MinIO 许可证
│   └── data/               # MinIO 数据目录
├── qdrant/                  # Qdrant 向量数据库配置
│   └── certs/              # Qdrant TLS 证书
├── scripts/                 # 辅助脚本
│   ├── qdrant/             # Qdrant 相关脚本
│   ├── setup/              # 初始化设置脚本
│   ├── backup_db.sh        # 数据库备份脚本
│   ├── init_db.sh          # 数据库初始化脚本
│   └── run_cleanup_sql.sh  # 执行清理 SQL 脚本
├── sql/                     # SQL 脚本文件
│   ├── init_database_schema.sql    # 数据库模式初始化
│   ├── seed_data.sql               # 种子数据
│   ├── cleanup_orphan_records.sql  # 清理孤立记录
│   └── README.md                   # SQL 脚本说明
├── alembic.ini            # Alembic 主配置文件
└── podman-compose.yml     # Podman Compose 服务编排配置
```

## 文件说明

### 核心配置文件

| 文件 | 描述 |
|------|------|
| `podman-compose.yml` | 使用 Podman 编排的多服务配置文件，定义 PostgreSQL、Redis、Neo4j、Qdrant、MinIO 五个服务 |
| `alembic.ini` | Alembic 数据库迁移工具的主配置文件 |

### 配置文件 (config/)

| 文件 | 描述 |
|------|------|
| `.env` | 主环境变量文件，包含 PostgreSQL、Redis、Qdrant、MinIO 的连接信息和凭证 |
| `.env.example` | 环境变量配置示例模板（不含真实凭证） |
| `.env.neo4j` | Neo4j 图数据库的专用环境变量 |
| `containers.conf` | 容器运行时配置 |
| `qdrant_config.json` | Qdrant 向量数据库的 JSON 配置 |

### 数据库迁移 (alembic/)

使用 Alembic 进行 PostgreSQL 数据库的版本控制和模式迁移：

- **versions/** - 存放历史迁移脚本，按日期和序号命名
  - `20260226_01_fix_evidence_records.py` - 修复证据记录表
  - `20260227_01_structural_variant_workflow.py` - 结构变异工作流表
  - `20260303_01_m0_request_paper_tables.py` - M0 请求论文相关表
  - `20260306_01_task_status_workflow_fields.py` - 任务状态和工作流字段

### SQL 脚本 (sql/)

| 脚本 | 描述 |
|------|------|
| `init_database_schema.sql` | PostgreSQL 数据库模式初始化（表结构、索引、约束、触发器） |
| `seed_data.sql` | 初始化种子数据（系统用户等） |
| `cleanup_orphan_records.sql` | 清理孤立/冗余记录 |
| `README.md` | SQL 脚本详细说明 |

### 脚本工具 (scripts/)

| 脚本 | 描述 |
|------|------|
| `init_db.sh` | 初始化 PostgreSQL 数据库（执行 schema 和 seed 脚本） |
| `backup_db.sh` | 数据库备份脚本 |
| `run_cleanup_sql.sh` | 执行清理 SQL 脚本 |

### 服务数据目录

| 目录 | 服务 | 描述 |
|------|------|------|
| `minio/` | MinIO | 对象存储，包含证书、许可证和数据目录 |
| `qdrant/` | Qdrant | 向量数据库，包含 TLS 证书 |

## 服务端口

| 服务 | 容器名 | 端口 | 描述 |
|------|--------|------|------|
| PostgreSQL | acmg_postgres | 5432 | 主关系数据库 |
| Redis | acmg_redis | 6379 | 缓存和消息队列 |
| Neo4j | acmg_neo4j | 7474(HTTP), 7687(Bolt) | 图数据库 |
| Qdrant | acmg_qdrant | 6333(HTTP), 6334(gRPC) | 向量数据库 |
| MinIO | acmg_minio | 9000(API), 9001(Console) | 对象存储 |

## 快速开始

### 1. 配置环境变量

```bash
# 复制示例配置并修改
cp config/.env.example config/.env
# 编辑 config/.env，设置强密码和正确的配置
```

### 2. 启动所有服务

```bash
podman-compose up -d
```

### 3. 初始化数据库

```bash
./scripts/init_db.sh
```

### 4. 查看服务状态

```bash
podman-compose ps
```

### 5. 停止服务

```bash
podman-compose down
```

## 常用命令

### Alembic 迁移命令

```bash
# 创建新的迁移
alembic revision -m "description"

# 应用所有迁移
alembic upgrade head

# 回滚一个版本
alembic downgrade -1

# 查看当前版本
alembic current
```

### 数据库操作

```bash
# 连接 PostgreSQL
psql -h localhost -p 5432 -U yangzs -d acmg_ps3

# 备份数据库
./scripts/backup_db.sh

# 清理孤立记录
./scripts/run_cleanup_sql.sh
```

## 注意事项

1. **安全**：`config/.env` 包含敏感凭证，请勿提交到版本控制系统
2. **备份**：定期使用 `backup_db.sh` 备份 PostgreSQL 数据
3. **网络**：所有服务运行在 `acmg-network` 桥接网络中
4. **健康检查**：每个服务都配置了健康检查，可通过 `podman-compose ps` 查看状态
