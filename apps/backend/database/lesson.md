# 容器启动故障排除记录

## 问题描述

执行 `podman-compose up -d` 启动容器时，部分容器启动失败。

## 错误原因

### 1. 容器名称冲突

**错误信息：**
```
Error: creating container storage: the container name "acmg_xxx" is already in use by <container_id>.
You have to remove that container to be able to reuse that name.
```

**原因：** 之前运行的容器实例未被完全清理，容器名称仍被占用。

### 2. 挂载目录不存在

**错误信息：**
```
failed to fulfil mount request: open /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/init-scripts: no such file or directory
failed to fulfil mount request: open /mnt/data/Documents/Graduate/02_Research/07_Multi-ACMG-database/minio/data: no such file or directory
```

**原因：** `podman-compose.yml` 中定义的卷挂载目录在宿主机上不存在：
- `./init-scripts` - PostgreSQL 初始化脚本目录
- `./minio/data` - MinIO 数据存储目录

## 解决过程

### 步骤 1：停止并移除现有容器

```bash
podman-compose down
```

输出显示成功停止并移除所有 5 个容器：
- acmg_postgres
- acmg_redis
- acmg_neo4j
- acmg_qdrant
- acmg_minio

### 步骤 2：创建缺失的目录

```bash
mkdir -p ./init-scripts ./minio/data
```

创建以下目录：
- `init-scripts/` - 用于挂载 PostgreSQL 初始化脚本（`/docker-entrypoint-initdb.d`）
- `minio/data/` - 用于 MinIO 数据持久化存储

### 步骤 3：重新启动容器

```bash
podman-compose up -d
```

所有 5 个容器成功创建并启动。

## 最终解决方案

### 完整命令序列

```bash
# 1. 进入项目目录
cd /mnt/data/Documents/Graduate/02_Research/05_Multi-ACMG-dev-yangzs/apps/backend/database

# 2. 停止并移除现有容器
podman-compose down

# 3. 创建缺失的挂载目录
mkdir -p init-scripts minio/data

# 4. 重新启动所有服务
podman-compose up -d

# 5. 验证容器状态
podman-compose ps
```

### 容器状态

| 容器名 | 镜像 | 端口 | 状态 |
|--------|------|------|------|
| acmg_postgres | postgres:18 | 5432 | starting → healthy |
| acmg_redis | redis:8 | 6379 | healthy |
| acmg_neo4j | neo4j:community | 7474, 7687 | starting → healthy |
| acmg_qdrant | qdrant:gpu-nvidia-latest | 6333, 6334 | healthy |
| acmg_minio | minio:latest | 9000, 9001 | starting → healthy |

## 经验教训

### 1. 容器管理最佳实践

- 启动新容器前，先检查是否有同名容器存在：`podman ps -a`
- 使用 `podman-compose down` 清理旧容器，而不是直接 `up -d`
- 定期清理未使用的容器：`podman container prune`

### 2. 卷挂载注意事项

- 确保 `podman-compose.yml` 中定义的所有宿主机目录都已创建
- 对于需要持久化的数据目录，提前创建并设置正确的权限
- 使用 `mkdir -p` 确保目录存在，避免手动挂载错误

### 3. 健康检查

- 部分服务（如 Neo4j、PostgreSQL）启动较慢，健康检查需要时间
- 使用 `podman-compose ps` 查看健康状态，等待所有服务变为 `healthy`
- PostgreSQL 健康检查命令：`pg_isready -U acmg_user -d acmg_ps3`

## 后续操作

### 初始化数据库

```bash
./scripts/init_db.sh
```

### 查看服务日志

```bash
# 查看所有服务日志
podman-compose logs

# 查看特定服务日志
podman-compose logs postgresql
podman-compose logs neo4j
```

### 停止服务

```bash
podman-compose down
```

### 完全清理（包括数据卷）

```bash
# 警告：这将删除所有数据卷！
podman-compose down -v
```
