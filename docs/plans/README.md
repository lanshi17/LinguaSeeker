# docs/plans 未完成任务索引

本目录只保留当前仍需执行、仍需持续跟踪、或仍会被直接引用的计划文档。已完成且不再属于当前执行面的计划应移动到 `docs/plans/archive/`，避免活跃计划与历史切片混淆。

## 优先级规则

1. 冻结规范（`docs/PRD.md`、`docs/BACKEND_STRUCTURE.md`、`docs/APP_FLOW.md`）优先于任意计划。
2. 先执行 `ACTIVE` 基线计划，再从该基线派生更小的执行批次。
3. 已归档计划默认视为完成，仅在需要复盘或回滚时重新打开。
4. 任意计划完成后，都必须同步 `progress.txt`；若过程中出现新的调试根因，再同步 `lesson.md`。

## 当前可执行计划

### `ACTIVE`

当前顶层 `docs/plans/` 暂无 backend/root active baseline。若后续出现新的 release 风险、补充验证或复盘任务，请基于已归档的 `v1.0` rollout baseline 重新派生新计划；前端计划继续保留在 `docs/plans/frontend/`。

## 当前状态（已同步到真实执行结果）

结合当前分支最新执行结果：

1. release artifact consistency remediation 已完成，manifest / release report / backend tests 已重新对齐。
2. docs root reorganization 已完成，仓库级文档已统一到根 `docs/` 体系，并完成 backend/frontend 文档迁移。
3. repository baseline contract unification 与 m3/m4 service-boundary provenance 文档已完成，仅保留追溯价值。
4. 当前根 `docs/plans/` 已不再保留 rollout active baseline；后续如需继续 release 风险整改，应从归档基线重新派生增量计划。

## 建议后续顺序

1. 如需继续 release 风险整改或复盘，基于归档的 `v1.0` rollout baseline 派生新的执行批次，不再恢复该基线到 active 目录。
2. 新的 frontend 规划继续放在 `docs/plans/frontend/`，避免重新把一次性总结放回活跃目录。
3. 完成后的计划统一迁移到 `docs/plans/archive/<date>-completed-plans/`，并同步更新本索引。

## 已完成并归档的计划

已于 `2026-04-16` 归档到 `docs/plans/archive/2026-04-16-completed-plans/`：

- `2026-04-15-rollout-plan-archive-implementation.md`
- `2026-04-16-completed-plan-batch-archive-design.md`
- `2026-04-16-completed-plan-batch-archive-implementation.md`

已于 `2026-04-15` 归档到 `docs/plans/archive/2026-04-15-completed-plans/`：

- `2026-03-22-v1.0-multi-source-6node-rollout.md`

已于 `2026-04-05` 归档到 `docs/plans/archive/2026-04-05-completed-plans/`：

- `2026-03-21-acquisition-strategy-adapter-design.md`
- `2026-03-21-acquisition-strategy-adapter-implementation.md`
- `2026-03-21-database-unified-management.md`
- `2026-03-23-m2-task-creation-flow-design.md`
- `2026-03-23-m2-task-creation-flow-implementation.md`
- `2026-04-05-m3-service-boundary-hardening-batch-1.md`

已于 `2026-04-06` 归档到 `docs/plans/archive/2026-04-06-completed-plans/`：

- `2026-04-05-multi-source-6node-rollout-design.md`
- `2026-04-05-multi-source-6node-rollout-implementation.md`

已于 `2026-04-09` 归档到 `docs/plans/archive/2026-04-09-completed-plans/`：

- `2026-04-06-acceptance-closeout-design.md`
- `2026-04-06-acceptance-closeout-implementation.md`
- `2026-04-06-release-closure-program-design.md`
- `2026-04-06-release-closure-program-implementation.md`

已于 `2026-04-13` 归档到 `docs/plans/archive/2026-04-13-completed-plans/`：

- `2026-04-05-m3-m4-service-boundary-and-contract-verification-implementation.md`
- `2026-04-06-repository-baseline-contract-unification-design.md`
- `2026-04-06-repository-baseline-contract-unification-implementation.md`
- `2026-04-10-release-artifact-consistency-remediation.md`
- `2026-04-11-docs-root-reorganization-design.md`
- `2026-04-11-docs-root-reorganization-implementation.md`
- `2026-04-13-docs-subdirectory-centralization-design.md`
- `2026-04-13-docs-subdirectory-centralization-implementation.md`

另有较早的完成归档保留在 `docs/plans/archive/2026-04-02-completed-plans/`：

- `2026-03-30-backend-6node-contract-cleanup-design.md`
- `2026-03-30-backend-6node-contract-cleanup.md`

## 历史归档目录

- `docs/plans/archive/2026-03-22-legacy-plans/`
- `docs/plans/archive/2026-04-02-completed-plans/`
- `docs/plans/archive/2026-04-05-completed-plans/`
- `docs/plans/archive/2026-04-06-completed-plans/`
- `docs/plans/archive/2026-04-09-completed-plans/`
- `docs/plans/archive/2026-04-13-completed-plans/`
- `docs/plans/archive/2026-04-15-completed-plans/`
- `docs/plans/archive/2026-04-16-completed-plans/`

## 当前整理结论

1. 当前根 `docs/plans/` 已移除已完成的 rollout baseline active 入口，仅保留仍需继续推进的计划入口与前端计划目录。
2. `REFERENCE ONLY` 计划已迁入归档切片，不再占用活跃目录。
3. 刚完成的 docs root reorganization 与 release artifact consistency remediation 已归档保留追溯。
4. 后续主线如需恢复 release 风险整改，应从已归档的 `v1.0` 基线计划重新派生新的增量计划。
