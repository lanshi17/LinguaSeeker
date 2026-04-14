# docs/ 目录导航

本目录是仓库级文档入口。根目录只保留 `README.md`、六个冻结规范文档，以及按用途划分的子目录；其余说明、计划、指南、历史输出和支持文件都应进入对应子目录。

## 根目录冻结规范

以下六个文档是仓库级权威入口，默认按此顺序阅读：

1. [PRD.md](./PRD.md)
2. [APP_FLOW.md](./APP_FLOW.md)
3. [TECH_STACK.md](./TECH_STACK.md)
4. [FRONTEND_GUIDELINES.md](./FRONTEND_GUIDELINES.md)
5. [BACKEND_STRUCTURE.md](./BACKEND_STRUCTURE.md)
6. [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)

## 目录结构

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
├── guides/
├── reference/
├── archive/
├── data/
└── templates/
```

## 子目录用途

### `plans/`

放仍在执行、待跟踪、待复盘或仍会直接引用的计划与设计文档。

- `docs/plans/README.md`：当前活跃计划索引
- `docs/plans/archive/`：已完成但仍需按计划语义归档保留的历史计划
- `docs/plans/frontend/`：前端相关计划与实施方案

### `guides/`

放面向开发/使用/排障的操作型文档。

- `docs/guides/frontend/`：前端 quickstart、troubleshooting、开发指南、WebSocket 指南等

### `reference/`

放长期参考资料、冻结规范补充、报告与稳定说明。

- `docs/reference/CHANGE_CONTROL.md`
- `docs/reference/CONSTANTS.md`
- `docs/reference/EVALUATION_FRAMEWORK.md`
- `docs/reference/PS3_BS3_VALIDATION_REPORT.md`
- `docs/reference/v1.0-release-report.md`
- `docs/reference/backend/README.md`
- `docs/reference/frontend/`：前端长期参考资料

### `archive/`

放历史性、阶段性、一次性输出，不作为当前默认实现依据。

- `docs/archive/backend/`：后端历史产物
- `docs/archive/frontend/`：前端总结、修复记录、阶段性报告

### `data/`

放清单、样例、结构化数据文件。

- `docs/data/v1.0-100-paper-manifest.json`

### `templates/`

放模板文件。

- `docs/templates/release_report.md.template`

## 使用约定

1. 新需求先对齐冻结规范，再编写或更新执行计划。
2. 涉及状态、错误码、重试、保留策略、验收口径变更时，必须同时更新冻结文档与相关参考文档。
3. `docs/archive/` 与 `docs/plans/archive/` 中的文档仅用于追溯，不直接驱动当前实现。
4. 不要再把新文档直接堆在 `docs/` 根目录；除六个冻结规范外，其余文档必须进入对应子目录。
5. 项目业务文档统一归根目录 `docs/` 管理，不再保留 `apps/*/docs/` 这类应用级文档目录。

## 快速查找

### 按角色

**工程实现**
- [BACKEND_STRUCTURE.md](./BACKEND_STRUCTURE.md)
- [FRONTEND_GUIDELINES.md](./FRONTEND_GUIDELINES.md)
- [TECH_STACK.md](./TECH_STACK.md)
- [plans/README.md](./plans/README.md)

**产品/流程**
- [PRD.md](./PRD.md)
- [APP_FLOW.md](./APP_FLOW.md)
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)

**参考与发布**
- [reference/CONSTANTS.md](./reference/CONSTANTS.md)
- [reference/CHANGE_CONTROL.md](./reference/CHANGE_CONTROL.md)
- [reference/v1.0-release-report.md](./reference/v1.0-release-report.md)

## 维护规则

- 计划完成后，优先移动到 `docs/plans/archive/`，而不是继续留在活跃索引中。
- 历史总结、修复记录、lesson 类文档优先进入 `docs/archive/`。
- Frontend/backend 专属导航文档应放在 `docs/reference/<domain>/`，不要重新在根目录复制入口。

---

**最后更新**: 2026-04-13
