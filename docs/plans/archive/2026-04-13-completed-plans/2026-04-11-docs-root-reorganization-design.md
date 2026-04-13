# Docs Root Reorganization Design

## Context

当前仓库的文档分散在 `docs/`、`apps/backend/docs/`、`apps/frontend/docs/` 三处。用户希望把仓库根 `docs/` 变成统一入口，并将根目录收敛到少量核心文档：保留 `README.md`，以及 `PRD.md`、`APP_FLOW.md`、`TECH_STACK.md`、`FRONTEND_GUIDELINES.md`、`BACKEND_STRUCTURE.md`、`IMPLEMENTATION_PLAN.md` 六个核心文件；其余文档全部进入子目录整理。

本次整理采用 `apps/backend/docs/` 中的六个同名文档作为根目录核心文档来源。为控制改动范围，`apps/frontend/docs/` 中的内容不做一次性全面归一化，而是先按用途收纳到根 `docs/` 的子目录体系中，后续再逐步细分与去重。

## Goals

- 让根 `docs/` 成为仓库级文档入口。
- 让 `docs/` 根目录只保留 `README.md` 和六个核心文档。
- 把其余文档按用途归类到子目录，减少根目录噪音。
- 用最小风险完成一次结构统一，避免一次性大规模重写内容。

## Non-Goals

- 不在本次整理中重写文档正文内容。
- 不在本次整理中完成 backend/frontend 文档完全去重。
- 不强行把所有历史文档细分到完美分类，只先达到“根目录清爽 + 子目录清晰”。

## Recommended approach

### 1. Root canonical set

根 `docs/` 保留以下文件：

- `README.md`
- `PRD.md`
- `APP_FLOW.md`
- `TECH_STACK.md`
- `FRONTEND_GUIDELINES.md`
- `BACKEND_STRUCTURE.md`
- `IMPLEMENTATION_PLAN.md`

其中六个核心文件从 `apps/backend/docs/` 提升到根 `docs/`，作为仓库级规范入口。

### 2. Purpose-based subdirectories

根 `docs/` 下建立并使用以下用途型目录：

- `docs/plans/`：计划、设计、实施跟踪
- `docs/guides/`：开发指南、快速开始、排障、操作说明
- `docs/reference/`：长期参考资料、规范、报告、说明
- `docs/archive/`：历史文档、阶段性输出、一次性总结
- `docs/data/`：JSON 清单、样例、数据说明
- `docs/templates/`：模板文件

### 3. Migration rules

#### Backend docs

- 六个核心文档提升到根 `docs/`
- 其余 backend 文档按用途迁入：
  - `CHANGE_CONTROL.md`、`CONSTANTS.md`、`PS3_BS3_VALIDATION_REPORT.md` → `docs/reference/`
  - `release/v1.0-release-report.md` → `docs/reference/` 或 `docs/archive/`（按发布状态决定，默认归 `reference/`）
  - `acceptance/v1.0-100-paper-manifest.json` → `docs/data/`
  - `templates/*.template` → `docs/templates/`
  - `plans/` 与 `archive/` 保留并整合进根 `docs/` 体系

#### Frontend docs

- 不把 frontend 同名核心文档放到根目录
- frontend 的计划文档优先进入 `docs/plans/frontend/`
- frontend 的指南类文档进入 `docs/guides/frontend/`
- frontend 的修复总结、阶段性报告、一次性说明优先进入 `docs/archive/frontend/` 或 `docs/reference/frontend/`
- 第一轮整理以“整体收纳进用途型子目录”为目标，不要求一次性做到完全去重

### 4. README responsibilities

`docs/README.md` 继续保留为总索引页，但需要改写成新的根目录结构说明：

- 明确根目录只保留的核心文档
- 给出各子目录的用途定义
- 更新所有示例路径，避免继续引用旧的扁平结构

## Target structure

```text
docs/
├── README.md
├── PRD.md
├── APP_FLOW.md
├── TECH_STACK.md
├── FRONTEND_GUIDELINES.md
├── BACKEND_STRUCTURE.md
├── IMPLEMENTATION_PLAN.md
├── plans/
│   ├── frontend/
│   └── archive/
├── guides/
│   └── frontend/
├── reference/
│   └── frontend/
├── archive/
│   └── frontend/
├── data/
└── templates/
```

## Risks and controls

- **风险：链接失效**
  - 通过统一更新 `docs/README.md` 和必要的相对路径引用来控制。
- **风险：frontend 文档第一轮分类不够细**
  - 本次接受“先收纳、后细分”的策略，优先完成根目录规范化。
- **风险：重复文档暂时并存**
  - 本次只确定根目录权威入口，不要求一次性清除所有重复语义。

## Verification

- `docs/` 根目录只剩 `README.md` + 六个核心文档 + 子目录
- 六个核心文档来自 `apps/backend/docs/`
- 非核心文档不再直接堆在 `docs/` 根目录
- `docs/README.md` 目录树与实际文件布局一致
- `git diff --name-status` 能清楚显示迁移后的新结构
