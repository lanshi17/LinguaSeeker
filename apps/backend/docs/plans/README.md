# docs/plans 计划索引

本目录只保留当前仍需执行的计划文档。已完成或仅供历史参考的计划应移入 `docs/archive/`。

## 优先级规则

1. 冻结规范（`docs/PRD.md`、`docs/BACKEND_STRUCTURE.md`、`docs/APP_FLOW.md`）优先于任意计划。
2. 先执行 `ACTIVE` 基线计划，再从该基线派生更小的执行批次。
3. 已归档计划默认视为完成，仅在需要复盘或回滚时重新打开。
4. 任意计划完成后，都必须同步 `progress.txt`；若过程中出现新的调试根因，再同步 `lesson.md`。

## 当前可执行计划

### `ACTIVE`

1. `2026-03-22-v1.0-multi-source-6node-rollout.md`
   当前唯一保留在本目录的基线计划。后续工作应围绕这份计划推进。

## 建议任务顺序

建议按下面顺序继续执行 `2026-03-22-v1.0-multi-source-6node-rollout.md`：

1. `M1: Acquisition & Orchestration`
   先补齐多源调度、来源追踪、获取层收口，确保入口契约稳定。
2. `M2: 6-Node Execution`
   在获取层稳定后，再推进 6 节点完整执行、状态回传和分类/裁决拆分。
3. `M3: Service Boundary Hardening`
   收紧解析、翻译、提取三类独立服务的边界与产物契约。
4. `M4: Contract & Verification`
   最后做 100 文献验收、成功率/时长校验，以及 release note / backward impact 收口。

## 已完成并归档的计划

已于 `2026-04-05` 归档到 `docs/archive/2026-04-05-completed-plans/`：

- `2026-03-21-acquisition-strategy-adapter-design.md`
- `2026-03-21-acquisition-strategy-adapter-implementation.md`
- `2026-03-21-database-unified-management.md`
- `2026-03-23-m2-task-creation-flow-design.md`
- `2026-03-23-m2-task-creation-flow-implementation.md`

## 历史归档目录

- `docs/archive/2026-03-22-legacy-plans/`
- `docs/archive/2026-04-05-completed-plans/`
