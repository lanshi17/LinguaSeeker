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
- Backend 入口：`backend/app/main.py`；业务逻辑放 `backend/app/` 及其子目录。
- Frontend 入口：Next.js App Router 页面放 `frontend/app/`；组件放 `frontend/components/`。

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

- 所有敏感配置（数据库密码、API Key、Token 等）必须通过环境变量或 `.env` 文件注入。
- **禁止**将任何密钥、凭证硬编码到源代码或提交到版本控制。
- `.env` 文件必须在 `.gitignore` 中排除。

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

## 三、违反处理

- 违反以上规则的代码不得合并到主分支。
- AI Agent 违反规则时，必须在 `lesson.md` 中记录并修正。
