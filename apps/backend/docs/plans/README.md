# docs/plans 未完成任务索引

本目录优先保留当前仍需执行的计划文档。少量已完成但仍被当前 rollout 基线直接引用的执行文档可以暂留在 `docs/plans/`，但必须明确标记为 `REFERENCE ONLY`，避免与 active 任务混淆。

## 优先级规则

1. 冻结规范（`docs/PRD.md`、`docs/BACKEND_STRUCTURE.md`、`docs/APP_FLOW.md`）优先于任意计划。
2. 先执行 `ACTIVE` 基线计划，再从该基线派生更小的执行批次。
3. 已归档计划默认视为完成，仅在需要复盘或回滚时重新打开。
4. 任意计划完成后，都必须同步 `progress.txt`；若过程中出现新的调试根因，再同步 `lesson.md`。

## 当前可执行计划

### `ACTIVE`

1. `2026-03-22-v1.0-multi-source-6node-rollout.md`
   当前唯一保留在本目录的基线计划。当前分支状态已收口到：
   - `M1/M2` 已完成
   - `M3` 的 service-boundary contract slice 已完成并归档
   - `M4` 的 `Task 4-6` 已并入当前分支
   - `Task 7` 与真实 100-paper acceptance 仍未完成
2. `2026-04-05-m3-m4-service-boundary-and-contract-verification-implementation.md`
   当前 active executable plan。已完成的 `Task 1-6` 已在合并后的当前分支落地，剩余执行面收口到 `Task 7`。

### `REFERENCE ONLY`

1. `2026-04-05-multi-source-6node-rollout-design.md`
   记录多源 + 6 节点 rollout recovery 的设计面，不再是当前 active executable plan。
2. `2026-04-05-multi-source-6node-rollout-implementation.md`
   记录已完成的 rollout recovery 实施批次，保留作追溯参考。

## 当前未完成任务

当前 `docs/plans/` 中真正仍需继续执行的工作已收口到：

1. `Task 7: Docs + focused regression`
   - 以合并后的当前分支为准，同步 rollout / progress / lesson 文档
   - 跑 focused M3/M4 regression suite
   - 明确记录 release-gate 工具已存在，但正式 acceptance 仍未执行
2. `100-paper acceptance run`
   - 使用固定 manifest 实际执行 acceptance
   - 生成并发布最终 release report
   - 保持 `FILE_DUPLICATE` 同时计入分子与分母
   - 校验单篇时长门槛 `<= 1800s`

## 建议任务顺序

建议按下面顺序继续执行剩余工作：

1. `Task 7`
   先对合并后的当前分支做文档收口和 focused regression 复核，确保 `task4-7-release-gate` 的增量没有被冲掉。
2. `100-paper acceptance run`
   在工具链和 contract 已稳定的前提下，再执行真实 acceptance 并产出最终 report。

## 已完成并归档的计划

已于 `2026-04-05` 归档到 `docs/archive/2026-04-05-completed-plans/`：

- `2026-03-21-acquisition-strategy-adapter-design.md`
- `2026-03-21-acquisition-strategy-adapter-implementation.md`
- `2026-03-21-database-unified-management.md`
- `2026-03-23-m2-task-creation-flow-design.md`
- `2026-03-23-m2-task-creation-flow-implementation.md`
- `2026-04-05-m3-service-boundary-hardening-batch-1.md`

另有较早的完成归档保留在 `docs/archive/2026-04-02-completed-plans/`：

- `2026-03-30-backend-6node-contract-cleanup-design.md`
- `2026-03-30-backend-6node-contract-cleanup.md`

## 历史归档目录

- `docs/archive/2026-03-22-legacy-plans/`
- `docs/archive/2026-04-02-completed-plans/`
- `docs/archive/2026-04-05-completed-plans/`

## 当前整理结论

1. 当前 active 工作只剩 `Task 7` 和真实 100-paper acceptance 执行。
2. release-gate calculation / reporting surface 已随 `task4-7-release-gate` 合并进入当前分支。
3. `docs/plans/2026-04-05-multi-source-6node-rollout-*.md` 现仅作 rollout recovery 参考，不再视为 active executable plan。
