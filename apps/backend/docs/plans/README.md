# Plans Index

本目录用于存放实现计划，不同计划可以共存，但执行前必须先看状态标签。

## 1. 优先级与冲突规则
1. 冻结规范文档（`docs/PRD.md`, `docs/BACKEND_STRUCTURE.md`, `docs/APP_FLOW.md`, `docs/TECH_STACK.md`）高于所有计划文档。
2. `ACTIVE` 计划可直接执行。
3. `P1_EXT_DRAFT` 计划执行前必须先做兼容性复核并更新文档。
4. `LEGACY/HISTORICAL` 计划仅供历史参考，不作为当前执行依据。

## 2. 当前计划状态
- `ACTIVE`
1. `2026-03-22-v1.0-multi-source-6node-rollout.md`
2. `2026-03-21-acquisition-strategy-adapter-design.md`
3. `2026-03-21-acquisition-strategy-adapter-implementation.md`
4. `2026-03-21-database-unified-management.md`

## 2.1 已归档计划（不在本目录执行）
归档路径：`docs/archive/2026-03-22-legacy-plans/`
1. `2026-03-06-phase-3-document-parsing.md`
2. `2026-03-12-cleanup-old-architecture.md`
3. `2026-03-12-multimodal-and-reasoning.md`
4. `langgraph-refactor-plan.md`
5. `streaming-output-plan.md`

## 3. 执行建议
1. 新任务默认从 `2026-03-22-v1.0-multi-source-6node-rollout.md` 派生子计划。
2. 若需复用 legacy 内容，必须先在计划顶部写明“已完成 v1.0 对齐”。
