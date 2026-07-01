# Documentation Index

> 项目文档，按生命周期状态组织。

## 概述

本目录是 Lingua Seeker 所有项目文档的索引和组织中心。文档按生命周期分类：活跃（active/）、计划中（planned/）、归档（archive/），以及模板和图表。

## 目录结构

```text
docs/
├── active/           # 进行中的计划和活跃参考文档
├── planned/          # 尚未开始的计划工作
├── codereview/       # 活跃代码审查（.gitkeep）
├── diagrams/         # Mermaid 流程图（phase1-phase4）
├── archive/
│   ├── plans/        # 已完成或被取代的计划
│   ├── codereview/   # 已完成的代码审查
│   └── deprecated-modules/  # 已移除模块的 README
└── templates/        # plan.md、codereview.md 模板
```

## 分类规则

- `active/` — 进行中的实施计划和活跃参考文档
- `planned/` — 尚未开始的计划工作（`YYYY-MM-DD-<topic>.md`）
- `codereview/` — 活跃代码审查报告
- `diagrams/` — 四个管线阶段的 Mermaid 流程图（`.mmd`）
- `archive/plans/` — 已完成或被取代的计划
- `archive/codereview/` — 已完成的代码审查
- `archive/deprecated-modules/` — 已移除模块保留的 README
- `templates/` — 可复用文档模板

### 文档迁移时机

| 触发条件 | 从 | 到 |
|---------|-----|-----|
| 开始实施计划 | `planned/` | `active/` |
| 计划完成/合并/被取代 | `active/`（或 `planned/`） | `archive/plans/` |
| 代码审查解决 | `codereview/` | `archive/codereview/` |

## 命名规范

新文档使用 `YYYY-MM-DD-<kebab-case-description>.md` 格式。

## 活跃计划和参考

| 日期 | 标题 | 状态 |
|------|------|------|
| 2026-06-29 | Evidence DB Field Model Implementation Plan | in-progress |
| 2026-06-27 | Backend Host Deployment Guide | reference |
| 2026-06-25 | Lingua Seeker v1.0.0 Release Checklist | in-progress |
| 2026-06-23 | Environment Consistency Standard | reference |
| 2026-06-21 | BIBM Main Paper TeX | in-progress |
| 2026-06-21 | BIBM Main Paper Manuscript Draft | in-progress |
| 2026-06-15 | ClinGen + ClinVar Fused Benchmark Dataset Plan | in-progress |
| 2026-05-13 | Phase Workflow Overview | reference |
| 2026-05-09 | PRD / APP_FLOW / TECH_STACK / BACKEND_STRUCTURE | reference |

完整列表见本目录源文件。

## 计划中工作

| 日期 | 标题 | 状态 |
|------|------|------|
| 2026-07-01 | [Semantic Word Alignment Design](planned/2026-07-01-semantic-word-alignment-design.md) | planned |
| 2026-07-01 | [Semantic Word Alignment Implementation Plan](planned/2026-07-01-semantic-word-alignment-plan.md) | planned |
| 2026-06-29 | BIBM N=50 Comparison and Ablation Experiment Design | planned |
| 2026-06-24 | BIBM Dataset D Pipeline Optimization Design | proposed |
| 2026-06-20 | Variant ID Guarantee Plan | planned |

## 图表

| 文件 | 内容 |
|------|------|
| [phase1.mmd](diagrams/phase1.mmd) | Phase 1：文献获取、解析 |
| [phase2.mmd](diagrams/phase2.mmd) | Phase 2：翻译、双轨证据提取 |
| [phase3.mmd](diagrams/phase3.mmd) | Phase 3：实体标准化、知识对齐 |
| [phase4.mmd](diagrams/phase4.mmd) | Phase 4：证据可视化、专家反馈 |

## 模块 README 索引

每个 `backend/` 模块都有自己的 `README.md` 开发者指南。关键模块：

- **[backend/app/](../backend/app/README.md)** — FastAPI 应用入口
- **[backend/src/agents/](../backend/src/agents/README.md)** — 管线编排器（LangGraph）
- **[backend/src/api/](../backend/src/api/README.md)** — HTTP 边界、依赖注入
- **[backend/src/core/](../backend/src/core/README.md)** — 垂直功能切片
- **[backend/src/dao/](../backend/src/dao/README.md)** — 持久化层
- **[backend/libs/](../backend/libs/README.md)** — Rust 原生扩展
