# docs/plans 未完成任务索引

本目录只保留当前仍需执行的计划文档。已完成或仅供历史参考的计划应移入 `docs/archive/`，不再保留在 `docs/plans/`。

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
   - `M4` 仍未完成
2. `2026-04-05-m3-m4-service-boundary-and-contract-verification-implementation.md`
   当前 active executable plan。已完成的 `Task 1-3` 已归档，后续只继续执行 `Task 4-7`。

## 当前未完成任务

当前 `docs/plans/` 中真正仍需继续执行的只剩 `M4: Contract & Verification`：

1. `Task 4: Trace-chain contract`
   - 稳定 `PipelineResult.trace_chain`
   - 稳定 `TaskStatusResponse.warning_codes`
   - 稳定 `TaskStatusResponse.trace_chain`
2. `Task 5: Release-gate calculation`
   - 固定 100 文献口径的成功率计算
   - `FILE_DUPLICATE` 同时计入分子与分母
   - 单篇时长门槛 `<= 1800s`
3. `Task 6: Reporting surface`
   - release report 渲染
   - CLI 包装脚本
   - acceptance manifest / report 模板
4. `Task 7: Docs + focused regression`
   - 稳定 JSON 溯源链字段契约
   - 同步 rollout / progress / lesson 文档
   - 跑 focused M3/M4 regression suite
   - 保持 100-paper acceptance work 显式未完成

## 建议任务顺序

建议按下面顺序继续执行剩余工作：

1. `Task 4`
   先补齐 trace-chain 与 task-status contract，否则 release gate 和 reporting 都缺少稳定输入。
2. `Task 5`
   在输出 contract 稳定后，再固化 acceptance 口径与 release gate 计算。
3. `Task 6`
   在 gate 计算稳定后，补 CLI/reporting surface。
4. `Task 7`
   最后做文档收口和 focused regression；100-paper acceptance 保持单独显式追踪。

## 已完成并归档的计划

已于 `2026-04-05` 归档到 `docs/archive/2026-04-05-completed-plans/`：

- `2026-03-21-acquisition-strategy-adapter-design.md`
- `2026-03-21-acquisition-strategy-adapter-implementation.md`
- `2026-03-21-database-unified-management.md`
- `2026-03-23-m2-task-creation-flow-design.md`
- `2026-03-23-m2-task-creation-flow-implementation.md`
- `2026-04-05-m3-service-boundary-hardening-batch-1.md`

## 历史归档目录

- `docs/archive/2026-03-22-legacy-plans/`
- `docs/archive/2026-04-05-completed-plans/`

## 当前整理结论

1. `docs/plans/` 目前只保留 active baseline 和 active executable plan 两份未完成文档。
2. 已完成的 M3 contract slice 已从活动执行视图中归档出去。
3. 当前剩余工作已收口到 `Task 4-7`，本质上都属于 `M4`。
