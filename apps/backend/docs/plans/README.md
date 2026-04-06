# docs/plans 未完成任务索引

本目录只保留当前仍需执行或仍需直接引用的计划文档。已完成且不再属于当前执行面的计划应移动到 `docs/archive/`，避免活跃计划与历史切片混淆。

## 优先级规则

1. 冻结规范（`docs/PRD.md`、`docs/BACKEND_STRUCTURE.md`、`docs/APP_FLOW.md`）优先于任意计划。
2. 先执行 `ACTIVE` 基线计划，再从该基线派生更小的执行批次。
3. 已归档计划默认视为完成，仅在需要复盘或回滚时重新打开。
4. 任意计划完成后，都必须同步 `progress.txt`；若过程中出现新的调试根因，再同步 `lesson.md`。

## 当前可执行计划

### `ACTIVE`

1. `2026-03-22-v1.0-multi-source-6node-rollout.md`
   顶层 `v1.0` 基线计划。当前用于约束未完成的 release 收口工作。
2. `2026-04-06-release-closure-program-design.md`
   当前 release closure program 的设计基线。
3. `2026-04-06-release-closure-program-implementation.md`
   当前 release closure program 的执行计划；实际剩余阻塞以该文件为准。

### `REFERENCE ONLY`

1. `2026-04-05-m3-m4-service-boundary-and-contract-verification-implementation.md`
   `Task 1-6` 已落地后的历史 provenance 文档，保留追溯上下文，但不再代表当前 active backlog。

## 当前未完成任务

当前 active backlog 已基本收口到 release final closeout：

1. `Task 14: 100-paper acceptance run`
   - 锁定固定 100 篇 manifest
   - 执行 acceptance set
   - 回写 manifest 实际结果
   - 生成最终 release report
2. `Task 15: final verification sweep`
   - 在真实 acceptance 完成后运行最终后端 release 验证切片
   - 以最终结果更新 `progress.txt` / `lesson.md`

当前已知阻塞：
1. `docs/acceptance/v1.0-100-paper-manifest.json` 仍是 scaffold
2. 仓库内尚无固定 100 篇来源清单，因此 acceptance 无法诚实执行

## 建议任务顺序

建议按下面顺序继续执行剩余工作：

1. 固定并锁定真实 100 篇 manifest
2. 运行 acceptance set 并同步实际结果
3. 生成最终 release report
4. 执行 Task 15 最终验证并记录 closeout

## 已完成并归档的计划

已于 `2026-04-05` 归档到 `docs/archive/2026-04-05-completed-plans/`：

- `2026-03-21-acquisition-strategy-adapter-design.md`
- `2026-03-21-acquisition-strategy-adapter-implementation.md`
- `2026-03-21-database-unified-management.md`
- `2026-03-23-m2-task-creation-flow-design.md`
- `2026-03-23-m2-task-creation-flow-implementation.md`
- `2026-04-05-m3-service-boundary-hardening-batch-1.md`

已于 `2026-04-06` 归档到 `docs/archive/2026-04-06-completed-plans/`：

- `2026-04-05-multi-source-6node-rollout-design.md`
- `2026-04-05-multi-source-6node-rollout-implementation.md`

另有较早的完成归档保留在 `docs/archive/2026-04-02-completed-plans/`：

- `2026-03-30-backend-6node-contract-cleanup-design.md`
- `2026-03-30-backend-6node-contract-cleanup.md`

## 历史归档目录

- `docs/archive/2026-03-22-legacy-plans/`
- `docs/archive/2026-04-02-completed-plans/`
- `docs/archive/2026-04-05-completed-plans/`
- `docs/archive/2026-04-06-completed-plans/`

## 当前整理结论

1. `master` 的 plans 归档整理已合并到当前 `yangzs-agents` 分支。
2. `2026-04-05` rollout 设计/实现文档已移出 active plans surface，转入 `docs/archive/2026-04-06-completed-plans/`。
3. 当前 `docs/plans/` 保留的是顶层基线、当前 release closure program，以及一个 provenance-only 历史实现文档。
4. 当前分支仍不能视为 release-complete；真实 100-paper acceptance 尚未执行。
