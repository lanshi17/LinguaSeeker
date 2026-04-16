# ACMG-Lingua Backend

本仓库是 ACMG-Lingua 的后端服务代码库，当前实现以 `FastAPI + Celery + LangGraph + PostgreSQL/Neo4j/Qdrant/MinIO/Redis` 为主。

## 当前入口与运行方式

- 主入口：`main.py`
- 兼容入口：`app.py`、`src/main.py`（都只做 `from main import app`）
- 依赖管理：`uv`

```bash
cp .env.example .env.local
uv sync
uv run python main.py
```

默认 API 前缀由 `src/config.py` 配置（当前默认 `/api/v1`）。

## 当前主流程（代码）

`src/agents/supervisor.py` 中的 LangGraph 编排：

1. `route_by_source`
2. `interaction`
3. `acquisition`
4. `parsing`
5. `translation`
6. `extraction`
7. `reasoning`
8. `arbitration`
9. `finalize` / `human_review` / `finalize_failed`

## 目录总览（按当前代码）

- `src/`：业务实现
  - `api/`：HTTP / WebSocket 路由
  - `agents/`：多节点编排与节点实现
  - `domain/`：领域模型、证据/图谱/文献/变异逻辑
  - `infrastructure/`：数据库与外部系统客户端
  - `services/`：任务编排与 DTO
  - `state/`：Supervisor 状态契约
  - `tools/`：对外工具导出层（大多为 re-export）
  - `utils/`：通用工具（日志、异常、文件、计时等）
- `database/`：数据库与中间件容器编排、迁移、SQL 脚本
- `docs/`：规范、计划、归档
- `scripts/`：运维与清理脚本
- `tests/`：测试

## 常用命令

```bash
# 启动数据库栈
./database/scripts/dbctl.sh up

# 初始化 schema + seed
./database/scripts/dbctl.sh init

# 健康检查
./database/scripts/dbctl.sh check

# 运行测试
uv run pytest
```

## 文档索引

- 总文档导航：`docs/README.md`
- 计划索引：`docs/plans/README.md`
- 数据库管理：`database/README.md`
- 各源码目录说明：`src/*/README.md`
