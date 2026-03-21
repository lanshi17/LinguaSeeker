# 启动维护复盘笔记

## 背景与目标
- 目标：恢复后端服务与本地数据库栈（Postgres/Redis/Neo4j/MinIO/Qdrant）正常启动与健康检查通过。
- 触发：`uv run uvicorn main:app` 失败，依赖缺失、配置冲突与存储认证问题叠加。

## 主要问题与根因
- `pyproject.toml` 重复段落导致解析失败。
- 运行时依赖缺失（`uvicorn`、`pydantic-settings`、`psycopg2`、`sqlalchemy`、`qdrant-client`、`langchain-*`、`langgraph`、`neo4j`）。
- 包/模块命名冲突：`src/config` 目录与 `src/config.py` 文件冲突、`src/domain/models` 目录与 `src/domain/models.py` 文件冲突。
- MinIO 访问密钥不匹配，导致桶检查失败。
- Redis 密码未生效（compose 变量在宿主提前展开），应用侧一直用带密码连接。
- Postgres 角色 `acmg_user` 缺失，导致认证失败。
- Neo4j 使用 `NEO4J_PASSWORD` 导致配置解析失败。
- Qdrant 客户端版本检测无法获取服务版本产生告警。

## 关键修复
- 修复 `pyproject.toml` 重复 `[tool.pytest.ini_options]`。
- 补齐核心依赖并将 `uvicorn` 固化为项目依赖。
- 处理命名冲突：
  - `src/config` -> `src/configs` 并更新引用。
  - `src/domain/models` -> `src/domain/task_models` 并更新引用。
- 补齐缺失工具函数与枚举（`get_all_files_in_directory`、`TaskStatus`）。
- MinIO：使用 `.env.local` 中的访问密钥创建同名用户并授予 `readwrite` 权限。
- Postgres：创建 `acmg_user` 并设置 `acmg_ps3` 数据库归属。
- Redis：修复 compose 中密码变量注入方式为 `$$REDIS_PASSWORD` 并重建容器。
- Neo4j：`.env.neo4j` 仅保留 `NEO4J_AUTH`，移除 `NEO4J_USER/NEO4J_PASSWORD`。
- Qdrant：在客户端创建中设置 `check_compatibility=False` 去除兼容性告警。

## 维护过程摘要（按时间线）
- 处理 `pyproject.toml` 解析错误并补齐依赖。
- 修复命名冲突与导入错误，确保模块加载成功。
- 对齐 MinIO 访问密钥，解决桶初始化失败。
- 使用 `podman-compose down/up` 重建容器，确保新配置生效。
- 修复 Redis 密码注入问题并重建 Redis 容器。
- 修复 Postgres 角色缺失，重新授权数据库。
- 修复 Neo4j 启动失败的配置项问题。
- 清理 Qdrant 兼容性警告。

## 关键命令（示例）
- 容器重建：`podman-compose -f database/podman-compose.yml down && podman-compose -f database/podman-compose.yml up -d`
- 单服务重建：`podman-compose -f database/podman-compose.yml up -d neo4j`、`podman-compose -f database/podman-compose.yml up -d redis`
- Postgres 角色与权限：
  - `CREATE ROLE acmg_user WITH LOGIN PASSWORD '***';`
  - `ALTER DATABASE acmg_ps3 OWNER TO acmg_user;`
- MinIO 用户授权：`mc admin user add` + `mc admin policy attach readwrite`

## 验证结果
- 应用健康接口 `/api/v1/health` 返回 `status=ok`，`redis/postgres/minio/qdrant` 均为 `true`。
- MinIO、Qdrant、Neo4j HTTP/Bolt 接口可访问。
- 容器状态大多为 `healthy`，Neo4j 在修复配置后进入正常启动状态。

## 后续建议
- 保持 `.env.local` 与 `database/config/.env` 关键参数一致，避免服务与应用侧配置漂移。
- 对 `podman-compose.yml` 中涉及密钥的变量使用 `$$VAR`，防止宿主提前展开。
- 将必需依赖固定到 `pyproject.toml`，避免运行时缺包。
- 对关键服务启动加入更明确的启动检测与错误提示。
