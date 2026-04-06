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
   当前唯一保留在本目录的 tracked 基线计划。当前分支状态已收口到：
   - `M1/M2` 已完成
   - `M3` 的 service-boundary + traceability / release-gate slice 已完成并归档
   - 当前 release-critical backlog 剩余：
     - KG independent service
     - multi-variant graph fan-out
     - remaining frontend result / export surfaces
     - repo-wide quality cleanup
     - real 100-paper acceptance run
   - 真实 acceptance 仍明确未执行

### `REFERENCE ONLY`

1. `2026-04-05-multi-source-6node-rollout-design.md`
   记录多源 + 6 节点 rollout recovery 的设计面，不再是当前 active executable plan。
2. `2026-04-05-multi-source-6node-rollout-implementation.md`
   记录已完成的 rollout recovery 实施批次，保留作追溯参考。
3. `2026-04-05-m3-m4-service-boundary-and-contract-verification-implementation.md`
   记录 `Task 1-6` 已落地的 service-boundary / traceability / release-gate slice，并保留 `Task 7` 历史 closeout 上下文；不再代表当前 release backlog 的完整执行面。

## 当前未完成任务

当前 `docs/plans/` 中真正仍需继续执行的 release backlog 已收口到：

1. `KG independent service`
   - 以 PostgreSQL 为 source of truth 写入 KG outbox / event row
   - 使用独立 KG consumer / queue / backfill 恢复 Neo4j 同步
2. `multi-variant graph fan-out`
   - 在 PostgreSQL 层先完成 variant fan-out
   - 保证 KG 只消费已规范化的 PG rows
3. `remaining frontend result / export surfaces`
   - 补齐 request monitor / document / export 的剩余用户面
   - 保持 `warning_codes` / `trace_chain` / `source_trace` 可见
4. `repo-wide quality cleanup`
   - 先清 touched scope 的 `basedpyright` / `ruff`
   - 再扩展到 hotspot 与 full-repo cleanup
5. `100-paper acceptance run`
   - 使用固定 manifest 实际执行 acceptance
   - 生成并发布最终 release report
   - 保持 `FILE_DUPLICATE` 同时计入分子与分母
   - 校验单篇时长门槛 `<= 1800s`

## 建议任务顺序

建议按下面顺序继续执行剩余工作：

1. `KG independent service`
   先补齐冻结 KG contract，避免后续 graph / frontend work 建立在不完整的 sync boundary 上。
2. `multi-variant graph fan-out`
   在 KG contract 落稳之后，再修复 PG / Neo4j 的 variant granularity。
3. `remaining frontend result / export surfaces`
   等后端读模型与 graph contract 稳定后再补 UI，避免返工。
4. `repo-wide quality cleanup`
   先清 release-critical / hotspot，再收 full-repo debt。
5. `100-paper acceptance run`
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

1. `Task 4-6` 的 traceability / release-gate slice 已随 `task4-7-release-gate` 合并进入当前分支。
2. 当前 active backlog 已不再收口为单一 `Task 7`，而是 release closure program 的五个剩余执行面。
3. 真实 100-paper acceptance 仍明确未执行，不能将当前分支视为 release-complete。
