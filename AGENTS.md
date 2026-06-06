# AGENTS.md

项目规范文档 — 所有参与本项目的开发者与 AI Agent 必须遵守以下规则。

---

## 一、硬性规则

### 1. 依赖管理 — 仅限现代化工具

- 项目必须且只能使用现代化管理工具启动与管理依赖：
  - **Python**: `uv`（禁止使用系统 `pip`）
  - **Node.js**: `nvm` + `npm`（禁止使用系统全局 Node）
  - **Rust**: `cargo`
  - **C/C++**: `cmake`
- 禁止直接使用系统环境安装或管理任何项目依赖。
- 所有依赖版本必须在对应配置文件中明确声明（`pyproject.toml` / `package.json` / `Cargo.toml`）。

### 2. 业务代码目录

- 除主入口文件外，所有业务代码必须放入 **`src/`** 目录。
- Backend 入口：`backend/app/main.py`；业务逻辑放 `backend/src/` 及其子目录。
- Frontend 入口：Next.js App Router 页面放 `frontend/app/`；组件放 `frontend/components/`。

### 2.1 架构偏好 — 编排式垂直切片架构

- 设计新模块/组件时，优先采用 **编排式垂直切片架构（Orchestrated Vertical Slice Architecture）**。
- 编排层只负责流程拓扑、全局状态、路由决策与节点可观测性；不得包含具体业务规则。
- 垂直特性包负责完整业务闭环：对编排器暴露 `api.py`/Node 接口，内部使用 `core.py` 放纯业务逻辑，`providers.py` 封装 LLM/DB/Rust I/O/外部服务，`contracts.py` 或 `schema.py` 放强类型契约。
- 全局状态使用 Pydantic 模型作为单一真相源；节点之间通过类型化状态增量通信，禁止裸 `dict` 作为稳定跨模块契约。
- 本仓库 Backend 映射：`backend/src/agents/` 是 Orchestrator，`backend/src/core/<feature>/` 是 Features，`backend/src/utils/`、`backend/src/dao/`、Rust crates 是 Shared infrastructure，`backend/src/core/config.py` 是 Config。
- Frontend 映射：`frontend/app/**/page.tsx` 负责页面级编排，`frontend/components/<feature>/` 与 `frontend/lib/hooks/` 承载垂直 UI 特性，`frontend/components/ui/`、`frontend/lib/api/`、`frontend/lib/types/`、`frontend/stores/` 为共享基础设施。

### 3. 文档管理

- 所有文档统一放入 **`docs/`**。
- 完成或过时的文档归档到 **`docs/archive/`**。
- 每次任务完成后，必须将相关文档归档。

### 4. 测试文件目录

- 所有测试文件统一放入 **`tests/`**。
- Backend 测试：`backend/tests/`
- Frontend 测试：`frontend/tests/`
- Rust 测试：`backend/libs/rust-io/tests/`

### 5. 进度记录

- 每完成一个任务节点，必须在根目录 **`progress.txt`** 中记录项目进度。
- 格式：`[日期] [任务描述] [状态]`

### 6. 复盘记录

- 每次调试试错或迭代排查必须复盘，并记录到 **`lesson.md`**。
- 记录内容：问题描述、排查过程、根因分析、解决方案、预防措施。

### 7. 日志与测试框架

- **日志**：使用 `loguru` 进行日志记录。日志文件写入 **`logs/`**，按时间命名（如 `2026-05-04_143000.log`）。
- **测试**：Backend 使用 `pytest`；Frontend 使用对应测试框架。

### 8. 脚本目录

- 与初始化、启动相关的脚本统一放入 **`scripts/`**。

### 9. 数据库目录

- 数据库相关文件统一放入 **`database/`**。
- 包括：迁移脚本（`database/migrations/`）、种子数据（`database/seeds/`）。

### 10. 需求确认

- 任何不明确的需求必须先询问并确认，**禁止自行假设**。

### 11. 分支策略

- 主分支为 **`dev`**（或指定分支）。
- **`master`** 分支只能手动合并处理，禁止直接推送。

### 12. 代码规范

- 代码规范按照 **Google Style Guide** 严格执行。
- Backend（Python）：遵循 [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)，使用 Ruff 强制检查。
- Frontend（TypeScript）：遵循 [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html)，使用 ESLint 强制检查。

### 13. 工作树隔离

- 按任务量判断是否需要隔离工作区新建工作树：
  - **轻量任务**：在当前工作区直接实现。
  - **中大型任务**：新建 Git Worktree 隔离开发。
- 任务完成后自动合并到主分支并删除工作树分支。

### 14. 部署目录

- 部署项目的容器/编排文件统一放入 **`deploy/`**。

---

## 二、补充规则

### 15. 代码审查

- 所有代码变更在合并前必须经过 Code Review。
- AI Agent 完成的代码同样需要人工审查确认后方可合并。

### 16. 环境变量与密钥管理

- 所有敏感配置（数据库密码、API Key、Token 等）必须通过环境变量或 `backend/config/vault/<env>.yaml` 文件注入。
- **禁止**将任何密钥、凭证硬编码到源代码或提交到版本控制。
- `backend/config/vault/*.yaml` 文件已在 `.gitignore` 中排除。

### 17. 提交信息规范

- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：
  - `feat: 新功能`
  - `fix: 修复缺陷`
  - `docs: 文档变更`
  - `refactor: 重构`
  - `test: 测试相关`
  - `chore: 构建/工具变更`
- 提交信息使用英文，简洁描述变更内容。

### 18. API 版本控制

- 所有对外 API 必须带版本号前缀（如 `/api/v1/`）。
- API 变更必须保持向兼容性，破坏性变更需升级版本号。

### 19. 依赖锁定与审计

- 生产依赖必须锁定到具体版本（Python `uv.lock` / Node `package-lock.json` / Rust `Cargo.lock`）。
- 定期审计依赖安全性，发现漏洞及时升级。

---

### 20. 行为准则 — 减少常见 LLM 编码错误

权衡：以下准则偏向谨慎而非速度。对于简单任务，自行判断。

#### 20.1 先思考再编码

**不要假设。不要隐藏困惑。暴露权衡。**

实现前：
- 明确陈述假设。不确定时，先问。
- 存在多种理解时，全部呈现 — 不要默默选择其一。
- 存在更简单方案时，主动提出。必要时反驳。
- 某处不清楚时，停下来。说清楚哪里困惑，然后提问。

#### 20.2 简单优先

**最小代码解决问题。不做投机性设计。**

- 不添加超出需求的功能。
- 不为单次使用代码创建抽象。
- 不添加未要求的"灵活性"或"可配置性"。
- 不为不可能的场景添加错误处理。
- 若 200 行能缩减为 50 行，重写。

自问："资深工程师会觉得这过度复杂吗？" 若是，简化。

#### 20.3 精确改动

**只动必须动的。只清理自己造成的遗留。**

编辑现有代码时：
- 不要"顺手改进"相邻代码、注释或格式。
- 不要重构未损坏的部分。
- 匹配现有风格，即使你会用不同方式。
- 发现无关死代码时，提及它 — 不要删除。

当你的改动产生孤立代码时：
- 删除 **你的改动** 造成的未使用导入/变量/函数。
- 不要删除改动前已存在的死代码，除非被要求。

检验标准：每一行改动都应直接追溯到用户请求。

#### 20.4 目标驱动执行

**定义成功标准。循环直到验证通过。**

将任务转化为可验证目标：
- "添加验证" → "为无效输入编写测试，然后使其通过"
- "修复 bug" → "编写复现测试，然后使其通过"
- "重构 X" → "确保重构前后测试均通过"

多步任务需列出简要计划：
```
1. [步骤] → 验证: [检查项]
2. [步骤] → 验证: [检查项]
3. [步骤] → 验证: [检查项]
```

强成功标准让你能独立循环。弱标准（"让它跑起来"）需要反复确认。

---

这些准则有效的标志：diff 中不必要的变更更少、因过度复杂导致的重写更少、澄清问题出现在实现之前而非犯错之后。

### 21. 自动化 Skill 触发

- **文档整理**：每当计划文档完成或 `docs/` 目录发生变更（新建、修改、归档），必须自动使用 `skill:doc-organize` 整理文档结构。
- **模块指南**：每当一个模块被实现（功能代码完成且测试通过），必须自动使用 `skill:module-guide` 生成开发者指南文档。

### 22. 后端 Python 类型安全 — 禁止裸 dict 返回值

- **禁止**使用 `-> dict`、`-> Dict[str, Any]` 等裸字典类型作为函数返回类型标注。
- 必须使用具名类型体代替，按场景选择：

| 场景 | 使用类型 | 示例 |
|---|---|---|
| **API 请求/响应** | `pydantic.BaseModel` | `class LiteratureResponse(BaseModel): ...` |
| **内部数据契约**（模块间传递、不可变数据） | `dataclasses.dataclass` | `@dataclass class GatewayResult: ...` |
| **轻量键值映射**（仅限配置、元数据等简单键值） | `TypedDict` | `class ProviderPlanItem(TypedDict): ...` |

- 所有 API 路由函数的返回值必须声明 `response_model`，使用 `BaseModel` 子类。
- 类型定义统一放在模块的 `contracts.py` 或 `schemas.py` 中，遵循现有命名约定：
  - `*Request` / `*Response` — Pydantic BaseModel（API 边界）
  - `*Result` / `*Entry` — dataclass（内部契约）
  - `*Item` / `*Params` — TypedDict（轻量映射）
- **例外**：解析外部第三方 API 的原始 JSON、配置文件字典等确实无固定结构的数据，可使用 `dict`，但必须添加 `# noqa: dict-return` 注释并说明理由。

### 23. LLM 模型使用约定

项目中按场景使用不同的 LLM 模型，通过配置文件中的环境变量注入：

| 场景 | 配置变量 | 说明 |
|---|---|---|
| **默认通用任务** | `LLM_MODEL` | 通用文本生成、摘要、分析、翻译等 |
| **审查/验证/推理** | `REASONING_LLM_MODEL` | 证据审查、结果验证、多源推理/仲裁等需要高精度的场景 |
| **多模态任务** | `MULTIMODAL_LLM_MODEL` | 图片识别、图表提取、PDF 视觉信息解析等需要多模态能力的场景 |

- 代码中必须根据实际场景选择对应的模型配置变量，**禁止混用**。
- 各模型的具体型号和参数在 `backend/config/` 中配置，通过 `src/core/config.py` 统一加载。

### 24. 文件删除操作

- 删除文件或目录时，**只允许使用 `rm` 命令**。
- **禁止**使用 `shred`、`unlink`、`find -delete`、`find -exec rm`、`perl -e unlink` 等替代方式删除文件。
- 使用 `rm` 删除目录时必须显式确认路径，禁止对项目根目录或关键配置目录执行 `rm -rf`。

### 25. 配置管理 — 采用 Ansible 架构配置文件

- 部署、运维、环境初始化、服务编排相关配置必须优先采用 **Ansible 架构配置文件** 组织。
- Ansible 相关文件统一放入 **`deploy/ansible/`**，按 `inventories/`、`group_vars/`、`host_vars/`、`playbooks/`、`roles/` 等标准结构拆分。
- 禁止将环境初始化、主机配置、服务编排配置散落在业务代码目录或临时脚本中；确需脚本辅助时，脚本放入 `scripts/`，并由 Ansible playbook 调用或记录调用关系。

---

## 三、违反处理

- 违反以上规则的代码不得合并到主分支。
- AI Agent 违反规则时，必须在 `lesson.md` 中记录并修正。

---

## 附录：Claude Code 项目上下文

> 以下内容供 Claude Code 在本仓库工作时参考。

### Project Overview

ACMG Lingua is a Multi-Agent infrastructure platform for medical genetics literature automation and structured evidence extraction. It provides a four-phase evidence pipeline: literature acquisition and digitization, cross-lingual dual evidence extraction and fusion, entity standardization and knowledge alignment, and bilingual visualization with expert-in-the-loop feedback. Monorepo with a Next.js frontend, FastAPI backend, and three Rust native extensions via PyO3.

### Architecture

#### Backend (`backend/`)

FastAPI async application. Business logic lives in `backend/src/` (not `app/`) and should prefer **Orchestrated Vertical Slice Architecture** for new modules: `src/agents/` owns workflow topology, global Pydantic state, routing decisions, and node telemetry; `src/core/<feature>/` owns vertical feature slices; `src/dao/`, `src/utils/`, Rust crates, and shared clients provide infrastructure.

```
src/
├── agents/        # Orchestrator: LangGraph topology, GraphState, router decisions
├── core/
│   ├── config.py                          # pydantic-settings singleton, all env vars
│   ├── ingest_and_digitize_data/          # Phase 1 feature slices: acquisition + upload + parsing
│   │   ├── literature_acquisition/        #   gateway, providers, PubMed, web scrapers
│   │   └── user_upload/                   #   PDF/DOCX upload handling
│   ├── cross_lingual_process_and_extract_evidence/  # Phase 2 features: extraction, translation, fusion
│   ├── standardize_entities_and_align_knowledge/    # Phase 3 features: standardization, alignment
│   └── visualize_evidence_with_expert_in_loop/      # Phase 4 features: review, feedback, export
├── api/           # FastAPI routes
├── dao/           # Shared persistence boundary
└── utils/         # Shared telemetry/logging/hash utilities
```

Feature slices should expose orchestrator-facing node adapters (`api.py` when useful), keep pure business behavior in `core.py`, wrap LLM/DB/Rust/external-service calls in `providers.py`, and define typed contracts in `contracts.py` or `schema.py`. Workflow code wires nodes and edges only; it must not embed extraction, translation, standardization, feedback, or report-generation business rules.

Configuration: `src/core/config.py` loads layered YAML from `backend/config/defaults`, `backend/config/environments`, and `backend/config/vault`, then lets environment variables override those values. Nested domain models (`cfg.llm`, `cfg.postgresql`, etc.) are built from flat fields by a `model_validator`. Access via `from src.core.config import get_config`.

#### Rust Native Extensions (`backend/libs/`)

Three PyO3 crates, all using `cdylib` + `rlib` crate types, async via `pyo3-async-runtimes` + tokio:

| Crate | Python module | Purpose |
|-------|--------------|---------|
| `rust-io` | `rust_io` | Literature search/download via providers (Crossref, OpenAlex, EuropePMC, PMC, DOAJ, JStage, Unpaywall). Also has `files` submodule for SHA256, file write, PDF validation. |
| `files-io` | `files_io` | Unified local + S3 file I/O. Dedup, parallel ops, archive (zip/tar/gzip). |
| `net-io` | `rust_io.net` | Literature search/download via providers + MinerU document parsing API. Same provider set as rust-io, newer architecture. |

All three expose async Python functions via `pyo3_async_runtimes::tokio::future_into_py`. The Python gateway (`src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/gateway.py`) calls `net_io.fetch_one()` for HTTP I/O and handles PDF downloads in Python.

#### Model Server (`backend/services/model-server/`)

Standalone FastAPI microservice (port 8001) for local model inference: Embedding, Rerank, LLM chat. OpenAI-compatible API. Models lazy-loaded on first request. Shares the `backend/config/` layered configuration source with the backend.

#### Frontend (`frontend/`)

Next.js 15 App Router, React 18, TypeScript, Tailwind CSS. State: Zustand. Data fetching: React Query + Axios. API proxy: `next.config.ts` rewrites `/api/v1/*` to `localhost:8000`.

```
app/
├── api/              # Next.js API routes (auth, proxy)
├── (dashboard)/      # Dashboard layout group
│   ├── analysis/     # Variant analysis page
│   ├── results/      # Results review page
│   └── settings/     # User settings
components/
├── ui/               # Base UI components
├── charts/           # Data visualizations
├── forms/            # Input forms
└── layout/           # Page layouts
lib/
├── api/              # API client functions
├── hooks/            # React hooks
├── types/            # TypeScript types
└── utils/            # Utility functions
```

#### Infrastructure

Docker Compose: frontend (`:3000`), backend (`:8000`), PostgreSQL 16 (`:5432`), Redis 8.0 (`:6379`).

### Development Commands

#### Backend (Python)

All Python operations must go through `uv`. Never use system `pip`.

```bash
cd backend

# Install dependencies
uv pip install -e ".[dev]"

# Add dependencies
uv add <package>              # production
uv add --dev <package>        # dev

# Run dev server
uv run uvicorn app.main:app --reload

# Lint (Google Python Style, line-length 120)
uv run ruff check

# Run all tests
uv run pytest

# Run a single test
uv run pytest tests/path/to/test_file.py::test_function_name

# Update lock file
uv lock
```

#### Frontend (Node.js)

Use `nvm` to select Node 18+. Never use system global Node.

```bash
cd frontend
nvm use
npm install
npm run dev          # Dev server
npm run lint         # ESLint
npm run type-check   # TypeScript check
npm run build        # Production build
```

#### Rust Libraries

```bash
cd backend/libs/rust-io     # or files-io, net-io
cargo test
cargo bench                 # rust-io only
```

To rebuild the PyO3 extension after Rust changes: `maturin develop --release` (from the crate directory).

#### Model Server

```bash
cd backend/services/model-server
uv run python main.py       # Starts on :8001
uv run python main.py --port 8002
```

#### Full Stack

```bash
docker compose up
```

### Key Patterns

#### Old Version Code Reuse

The previous codebase is preserved in `backend/.old_version/`. **Always check it before writing new code.** Search first, reuse preferentially, adapt to new architecture.

```bash
grep -r "keyword" backend/.old_version/src/
find backend/.old_version/ -name "*.py" | xargs grep "ClassNameOrFunction"
tree backend/.old_version/src/ -L 2
```

| Directory | Contents |
|---|---|
| `.old_version/src/` | Core business logic (agents, api, domain, infrastructure, services, tools, utils) |
| `.old_version/utils/` | Shared utility modules |
| `.old_version/configs/` | App and database configuration |
| `.old_version/scripts/` | Ops scripts (log cleanup, cache purge, data sync, etc.) |
| `.old_version/database/` | Alembic migrations, Neo4j, Qdrant, MinIO configs |
| `.old_version/tests/` | Existing test cases |
| `.old_version/knowledge_docs/` | Knowledge base documents |
| `.old_version/lesson.md` | Past retrospective notes |
| `.old_version/prd.json` | Product requirements |

**Workflow**: Search first → reuse preferentially → adapt to new architecture → annotate source for complex migrations.

**Prohibited**: Writing new features without checking `.old_version/`, copying without adaptation, deleting `.old_version/`.

#### Literature Provider System

The literature acquisition gateway supports multiple providers (Crossref, OpenAlex, EuropePMC, PMC, DOAJ, JStage, Unpaywall, plus web scrapers for CyberLeninka, Hans Publishers, PubScholar). Rust handles HTTP I/O; Python handles business logic, retry, and PDF download orchestration.

#### Configuration

All config data lives in `backend/config/` or explicit environment variables. Key config domains: `FAST_LLM_*`, `REASONING_LLM_*`, `EMBEDDING_*`, `RERANK_*`, `MINERU_*`, `POSTGRES_*`, `REDIS_*`, `WEB_SEARCH_*`, `NETWORK_*`.

#### Testing

- Backend: `pytest` with `pytest-asyncio` for async tests. Tests mirror source structure under `backend/tests/`.
- Frontend: tests under `frontend/tests/`.
- Rust: `cargo test` per crate.
