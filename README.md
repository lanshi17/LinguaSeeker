# LinguaSeeker

> 医学遗传学文献自动化和结构化证据提取的多智能体基础设施平台。提供四阶段证据管线：文献获取与数字化、跨语言双轨证据提取与融合、实体标准化与知识对齐、双语可视化与专家反馈。

## 发布状态

**当前版本：** `v1.0.0`

首个稳定版本冻结当前 FastAPI 后端、Vite + React 前端、Rust 原生 I/O 扩展、数据库 schema 契约和部署配置。生产部署应将后端和前端镜像固定到相同的不可变标签。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vite、React 18、TypeScript（strict）、Ant Design、Zustand、React Query、Axios、React Router |
| 后端 | Python 3.12、FastAPI、SQLAlchemy 2.0（async）、Alembic、LangGraph |
| 原生 I/O | Rust（PyO3/maturin 扩展：rust-io、files-io、net-io） |
| 推理 | 外部 Docker 容器：Embedding(:8002)、Rerank(:8003)、Doc-Parse(:44321) |
| 数据库 | PostgreSQL 16（pgvector）、Redis 8.0 |
| 基础设施 | Docker Compose、Ansible |

## 项目结构

```
.
├── backend/                        # FastAPI 应用
│   ├── app/                        # 入口点（main.py）
│   ├── src/                        # 业务逻辑（编排垂直切片架构）
│   │   ├── agents/                 # 管线编排器（LangGraph）
│   │   ├── api/                    # FastAPI 路由（v1/）
│   │   ├── core/                   # 功能切片（Phase 1-4）
│   │   │   ├── config.py                       # 配置
│   │   │   ├── ingest_and_digitize_data/       # Phase 1
│   │   │   ├── cross_lingual_process_and_extract_evidence/  # Phase 2
│   │   │   ├── standardize_entities_and_align_knowledge/    # Phase 3
│   │   │   └── visualize_evidence_with_expert_in_loop/      # Phase 4
│   │   ├── dao/                    # 数据访问（PostgreSQL、Redis）
│   │   └── utils/                  # 共享工具
│   ├── libs/                       # Rust 原生扩展
│   ├── config/                     # 分层 YAML 配置
│   ├── tests/                      # 后端测试
│   └── pyproject.toml              # Python 项目（uv 管理）
├── frontend/                       # Vite + React 应用
│   ├── src/                        # 应用源码
│   │   ├── pages/                  # 路由级页面组件
│   │   ├── components/             # 可复用 UI 组件（antd）
│   │   ├── api/                    # API 客户端
│   │   ├── hooks/                  # 自定义 React Hooks
│   │   ├── stores/                 # Zustand 状态存储
│   │   ├── types/                  # TypeScript 类型定义
│   │   └── utils/                  # 工具函数
│   ├── tests/                      # 前端测试
│   └── package.json                # Node 项目（bun 管理）
├── database/                       # Alembic 迁移 + 术语数据
│   ├── migrations/                 # SQL 迁移脚本（23 个版本）
│   ├── terminology_database/       # 参考数据（ClinVar、ClinGen、HPO、OMIM 等）
│   └── config/                     # 数据库配置
├── deploy/                         # 部署配置
│   ├── compose/                    # Docker Compose 部署
│   │   ├── single-server/          # 一体化部署
│   │   ├── backend-host/           # 后端 + Postgres + Redis
│   │   ├── frontend-host/          # Nginx + 预构建 SPA
│   │   └── staging/                # 预发布环境
│   └── ansible/                    # Ansible 部署自动化
│       ├── roles/                  # backend、frontend、postgres、redis、nginx
│       ├── playbooks/              # site.yml、healthcheck.yml
│       └── inventories/            # production/
├── docs/                           # 文档（active、planned、archive）
├── benchmark/                      # 管线基准测试 + 评估
├── scripts/                        # 项目级运维脚本
├── knowledges/                     # 知识库文档（ACMG 指南等）
├── data/                           # 测试 PDF + 管线运行产物
├── libs/                           # 共享 Python 库（config-loader）
├── artifacts/                      # 数据库导出和术语导出
├── AGENTS.md                       # 项目规则和约定
├── copier.yaml                     # Copier 模板配置
└── README.md
```

## 快速开始

### 前置条件

- Docker & Docker Compose
- [bun](https://bun.sh/)（前端包管理器和运行时）
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）
- Rust 工具链（用于原生 I/O 库）

### Docker 本地开发

```bash
docker compose up
```

- 前端：http://localhost:3000
- 后端 API：http://localhost:8000
- PostgreSQL：`localhost:5432`
- Redis：`localhost:6379`

### 本地开发

**后端：**
```bash
cd backend
uv pip install -e ".[dev]"
uv run uvicorn app.main:app --reload
```

**前端：**
```bash
cd frontend
bun install
bun run dev
```

**推理服务（外部）：**

模型推理（Embedding、Rerank、Doc-Parse）由外部 Docker 容器提供，在 `backend/config/` 中配置服务 URL。

## 开发命令

| 命令 | 描述 |
|------|------|
| `cd backend && uv run ruff check` | 后端代码检查 |
| `cd backend && uv run pytest` | 运行所有后端测试 |
| `cd frontend && bun run lint` | 前端代码检查 |
| `cd frontend && bun run type-check` | TypeScript 类型检查 |
| `cd frontend && bun run build` | 生产构建 |
| `cd frontend && bun run test` | 前端测试 |
| `cd backend/libs/rust-io && cargo test` | Rust 测试 |

## 部署

### 数据库环境

| 环境 | 数据库 | Schema | 用户 |
|------|--------|--------|------|
| Development | `dev_lingua_seeker` | `lingua_seeker` | `lingua_seeker` |
| Staging | `staging_lingua_seeker` | `lingua_seeker` | `lingua_seeker` |
| Production | `lingua_seeker` | `lingua_seeker` | `lingua_seeker` |

### 单机部署

```bash
cd /opt/lingua-seeker
cp deploy/compose/single-server/.env.example .env
docker-compose --env-file .env up -d
docker exec lingua-backend uv run alembic upgrade head
```

详见 [deploy/compose/single-server/](deploy/compose/single-server/)。

### 分离前后端

前端（nginx + SPA）和后端（FastAPI + Postgres + Redis）部署在独立主机。详见 [deploy/compose/README.md](deploy/compose/README.md)。

### Ansible

裸机 / systemd 部署。详见 [deploy/ansible/](deploy/ansible/)。

## 分支策略

- **`dev`** — 主开发分支
- **`master`** — 仅手动合并，禁止直接推送

## 约定

详见 [AGENTS.md](./AGENTS.md)。关键要点：

- 包管理器：`uv`（Python）、`bun`（Node.js）、`cargo`（Rust）
- 日志：`loguru`，输出到 `logs/`
- 测试：`pytest`（后端）、`vitest`（前端）、`cargo test`（Rust）
- 代码风格：Google Style Guide，Ruff（Python）和 ESLint（TypeScript）
- 提交信息：Conventional Commits（`feat:`、`fix:`、`docs:` 等）
- API 版本：`/api/v1/` 前缀
