# docs/plans 计划索引

本目录仅保留当前仍需继续执行的计划文档。已完成计划应移动到 `docs/archive/`，避免当前目录与实际执行状态脱节。

## 优先级规则

1. 冻结规范（`docs/PRD.md` 等）优先于任意计划。
2. `ACTIVE` 计划可直接执行。
3. 草案/扩展计划执行前应先做契约一致性复核。
4. `docs/archive/` 仅历史参考。

## 当前活动计划

- `2026-03-22-v1.0-multi-source-6node-rollout.md`

说明：
- 该文件是当前保留的总控基线计划。
- 其 M1/M2 已完成切片的执行文档已转入归档目录保存。

## 2026-04-06 已完成并归档

- `docs/archive/2026-04-06-completed-plans/2026-03-21-database-unified-management.md`
- `docs/archive/2026-04-06-completed-plans/2026-03-23-m2-task-creation-flow-design.md`
- `docs/archive/2026-04-06-completed-plans/2026-03-23-m2-task-creation-flow-implementation.md`
- `docs/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-design.md`
- `docs/archive/2026-04-06-completed-plans/2026-04-05-multi-source-6node-rollout-implementation.md`

## 归档目录

- `docs/archive/2026-03-22-legacy-plans/`
- `docs/archive/2026-04-02-completed-plans/`
- `docs/archive/2026-04-06-completed-plans/`

## 建议流程

1. 从当前活动基线计划派生子任务。
2. 已完成切片从 `docs/plans/` 移出，转入 `docs/archive/`。
3. 记录变更原因、影响范围、回滚方案。
4. 完成后同步 `progress.txt`。
