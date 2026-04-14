# Docs Subdirectory Centralization Design

> **归档说明（2026-04-14）**：后续在隔离 worktree 中复核时确认，本设计假设的残留状态已经被更早的文档集中化提交消化：`apps/backend/docs/` 已不存在，仓库内也没有剩余项目自有子目录级 `docs/`。因此本设计文档只保留追溯价值，对应收尾动作仅剩 `docs/README.md` 规则补充，而不是继续执行目录迁移。

## Context

当前仓库已经把项目级业务文档统一收敛到根 `docs/` 体系，并在 `docs/README.md` 中定义了根目录冻结规范、用途型子目录和维护规则。

但仓库内仍残留个别子目录级 `docs/`，与“所有文档集中到根 `docs/`”这一仓库约束不完全一致。当前确认到的项目自有残留项是：

- `apps/backend/docs/archive/2026-03-22-outdated-diagrams/pdf_cd.puml`
- `apps/backend/docs/archive/2026-03-22-outdated-diagrams/pdf_sd.puml`

用户希望继续完成统一：将其余子目录中的显式 `docs/` 目录内容全部收口到项目根目录 `docs/`，并采用完全迁移方式，不保留原目录壳。

## Goals

- 让项目自有业务文档只保留一个根入口：`/docs`
- 消除仓库内残留的应用级 `docs/` 目录
- 让文档存放规则与实际目录结构完全一致
- 以最小改动完成本轮统一，不扩大到未确认范围

## Non-Goals

- 不处理 `apps/frontend/api_docs/` 这类非 `docs/` 命名目录
- 不迁移源码旁模块级 `README.md`
- 不重写文档正文或做大规模内容去重
- 不处理第三方依赖中的 `node_modules/**/docs`

## Recommended Approach

### 1. Scope boundary

本次仅处理仓库内**显式命名为 `docs/` 的项目自有目录**。

因此：

- **纳入范围**：`apps/backend/docs/`
- **排除范围**：`apps/frontend/api_docs/`、源码旁 `README.md`、`node_modules/**/docs`

这样可以严格匹配用户确认的边界：只统一各子目录中的 `docs/`，不顺手扩大为全面文档重构。

### 2. File migration

将 `apps/backend/docs/archive/2026-03-22-outdated-diagrams/` 下的历史图文件迁移到根文档归档体系：

- `apps/backend/docs/archive/2026-03-22-outdated-diagrams/pdf_cd.puml`
  → `docs/archive/backend/2026-03-22-outdated-diagrams/pdf_cd.puml`
- `apps/backend/docs/archive/2026-03-22-outdated-diagrams/pdf_sd.puml`
  → `docs/archive/backend/2026-03-22-outdated-diagrams/pdf_sd.puml`

目标语义保持不变：这些文件仍属于后端历史归档，不进入根 `docs/` 的权威规范入口。

### 3. Rule update

同步更新 `docs/README.md`，明确两层规则：

1. 项目业务文档统一归根 `docs/` 管理
2. `apps/*/docs/` 这类应用级文档目录不再保留

这样后续新增文档时，有明确的落点规则，而不是只依赖一次性迁移结果。

### 4. Cleanup policy

在确认迁移完成后，删除空的 `apps/backend/docs/` 目录。

本次采用完全迁移，不保留壳目录、占位 README 或兼容跳转说明，避免双入口继续存在。

## Target Structure

```text
docs/
├── README.md
├── PRD.md
├── APP_FLOW.md
├── TECH_STACK.md
├── FRONTEND_GUIDELINES.md
├── BACKEND_STRUCTURE.md
├── IMPLEMENTATION_PLAN.md
├── archive/
│   ├── backend/
│   │   └── 2026-03-22-outdated-diagrams/
│   │       ├── pdf_cd.puml
│   │       └── pdf_sd.puml
│   └── frontend/
├── guides/
├── plans/
├── reference/
├── data/
└── templates/
```

迁移完成后，项目自有应用级 `docs/` 目录应清零。

## Risks and Controls

- **风险：误把第三方依赖中的 `docs` 当成治理对象**  
  - 控制：校验时只检查项目自有路径，显式排除 `node_modules/**/docs`

- **风险：根索引规则与实际结构不同步**  
  - 控制：迁移文件后立即更新 `docs/README.md`，让规则和现状保持一致

- **风险：历史文件分类位置不清楚**  
  - 控制：统一放入 `docs/archive/backend/...`，保持“历史后端归档”语义，不混入规范入口

## Verification

完成后需要满足：

1. `apps/backend/docs/` 不再存在
2. 两个 `.puml` 文件已经迁入 `docs/archive/backend/2026-03-22-outdated-diagrams/`
3. `docs/README.md` 明确规定项目业务文档统一归根 `docs/` 管理，且不再保留 `apps/*/docs/`
4. 仓库内项目自有的显式子目录 `docs/` 已全部收口到根 `docs/`
5. 第三方依赖目录未被纳入迁移或清理操作
