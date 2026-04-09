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
   顶层 `v1.0` 基线计划。当前用于约束 release 后续整改与复盘执行面。
2. `2026-04-06-release-closure-program-design.md`
   release closure program 的设计基线（已执行完成，保留为 closeout 事实来源与后续整改参考）。
3. `2026-04-06-release-closure-program-implementation.md`
   release closure program 执行计划（`Task 14/15` 已完成，保留为执行 provenance）。

### `REFERENCE ONLY`

1. `2026-04-05-m3-m4-service-boundary-and-contract-verification-implementation.md`
   `Task 1-6` 已落地后的历史 provenance 文档。
2. `2026-04-06-repository-baseline-contract-unification-design.md`
   仓库口径统一设计文档，已完成，保留追溯。
3. `2026-04-06-repository-baseline-contract-unification-implementation.md`
   上述设计的执行计划，已完成，保留追溯。

## 当前状态（已同步到真实执行结果）

结合 2026-04-09 实际执行结果：

1. `Task 14` 已完成：100 篇 acceptance 已全部进入终态并同步回 manifest。
2. `Task 15` 已完成：最终 backend/frontend/static 验证切片已执行完成。
3. `docs/release/v1.0-release-report.md` 已发布，当前 gate 结果为 `FAILED`，阻塞原因是 `DURATION_SLA_BREACHED`（非 run incomplete）。

当前分支不再存在“Task 14/15 未执行”的阻塞；后续工作应转入 release gate 失败项整改与复盘。

## 建议后续顺序

1. 基于 `v1.0-release-report.md` 分析 `DURATION_SLA_BREACHED` 的主要来源（按论文/节点拆解）。
2. 制定并执行时延整改批次（优先 acquisition/translation/extraction 热点）。
3. 重新运行 acceptance 验证并更新 release report。
4. 在 `progress.txt` / `lesson.md` 记录整改闭环。

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

已于 `2026-04-09` 归档到 `docs/archive/2026-04-09-completed-plans/`：

- `2026-04-06-acceptance-closeout-design.md`
- `2026-04-06-acceptance-closeout-implementation.md`
- `2026-04-06-repository-baseline-contract-unification-design.md`
- `2026-04-06-repository-baseline-contract-unification-implementation.md`

另有较早的完成归档保留在 `docs/archive/2026-04-02-completed-plans/`：

- `2026-03-30-backend-6node-contract-cleanup-design.md`
- `2026-03-30-backend-6node-contract-cleanup.md`

## 历史归档目录

- `docs/archive/2026-03-22-legacy-plans/`
- `docs/archive/2026-04-02-completed-plans/`
- `docs/archive/2026-04-05-completed-plans/`
- `docs/archive/2026-04-06-completed-plans/`
- `docs/archive/2026-04-09-completed-plans/`

## 当前整理结论

1. `Task 14/15` 已执行完成，相关结果已反映在 manifest/report 与 progress 记录中。
2. `2026-04-06` 的 acceptance closeout 与 repository baseline unification 派生计划已转入归档。
3. 当前 `docs/plans/` 仅保留 active baseline 与已执行 closeout program 的事实来源文档。
4. 后续主线是 release gate 失败项（`DURATION_SLA_BREACHED`）整改，不是 acceptance 执行补齐。
