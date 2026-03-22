# Docs 导航与持久化规范

## 1. 冻结规范（发布契约）
以下文档是 MVP 的长期有效规范，修改需要同步发布说明与影响评估：
1. `PRD.md`
2. `BACKEND_STRUCTURE.md`
3. `APP_FLOW.md`
4. `TECH_STACK.md`
5. `FRONTEND_GUIDELINES.md`
6. `IMPLEMENTATION_PLAN.md`
7. `CONSTANTS.md`（错误码/状态机/重试参数单一来源）

## 2. 支撑规范（长期保留）
1. `EVALUATION_FRAMEWORK.md`
2. `PS3_BS3_VALIDATION_REPORT.md`
3. `CHANGE_CONTROL.md`

## 3. 工作文档（可迭代）
1. `plans/`：设计与实施计划，允许随阶段更新（执行前先读 `plans/README.md` 状态索引）。
2. `archive/`：仅保留必要历史记录，不再作为当前实现依据。

## 4. 清理规则
1. 与冻结规范冲突且无迁移价值的文档应删除。
2. 历史测试产物优先外部制品库保存，不在 `docs/` 长期堆积。
3. 任何状态、错误码、重试、保留策略变更，必须先更新冻结规范文档。

## 5. 本次整理（2026-03-22）
1. 已完成 `v1.0` 基线切换：多源获取 + 6 节点流程 + 三个独立微服务。
2. 变更控制文档已合并为单一入口：`CHANGE_CONTROL.md`。
3. 旧计划文档与过时图已归档到 `archive/`，`plans/` 仅保留活动计划。
4. `PS3_BS3_QUICK_REFERENCE.txt` 已合并进 `EVALUATION_FRAMEWORK.md` 附录并删除。
