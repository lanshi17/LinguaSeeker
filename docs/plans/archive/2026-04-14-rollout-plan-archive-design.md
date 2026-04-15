# Rollout Plan Archive Design

> **Status:** `APPROVED FOR EXECUTION`
> **Target Plan:** `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md`
> **Validated Against Current Branch:** `yangzs-agents` on `2026-04-14`

## Context
当前 `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md` 仍标记为 active baseline，但在当前分支复核后，计划正文所描述的 rollout 主体工作已经完成。backend/frontend 相关实现与 focused verification 也已在当前分支再次核实通过。

现存问题不是实现未完成，而是文档状态与引用已经滞后于仓库结构调整：
1. 多个归档引用仍指向旧的 `docs/archive/...` 路径，实际应位于 `docs/plans/archive/...`
2. backend/frontend 代码与测试路径仍使用旧布局，实际已迁移到 `apps/backend/...` 与 `apps/frontend/...`
3. `progress.txt` 的引用仍假设仓库根目录存在该文件，实际位置为 `apps/backend/progress.txt`

## Goal
将该 rollout baseline 从 active plan 收口为准确、可追溯的历史归档文档，而不改动其已完成的技术结论。

## Chosen Approach
采用“归档前纠偏 + 正式归档”的最小改动策略：
1. 先修正文档中的失效引用与路径，使其反映当前仓库真实结构
2. 将头部状态与剩余工作描述改为 completed/archived 语义，明确该计划不再作为执行中的 active plan
3. 再将文档移入 `docs/plans/archive/` 体系中的归档位置，保留其作为 v1.0 rollout baseline 的历史作用

## Scope
### In scope
1. 修正 `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md` 中的过期路径与引用
2. 将文档状态改为 archived/completed，并补充基于当前分支复核后的归档说明
3. 将该文档移动到符合现有约定的 `docs/plans/archive/` 目录
4. 复核归档后文档的路径正确性与状态一致性

### Out of scope
1. backend/frontend 代码改动
2. 新增 release remediation 执行计划
3. 重写 rollout 里程碑结论
4. 重新定义已完成的验收结果

## Design Details
### 1. Reference normalization before archival
在归档前统一修正文档内的关键路径：
1. `docs/archive/...` → `docs/plans/archive/...`
2. `progress.txt` → `apps/backend/progress.txt`
3. `src/...` / `tests/...` → `apps/backend/src/...` / `apps/backend/tests/...`
4. `../frontend/...` → `apps/frontend/...`

### 2. Status transition
文档头部状态从 active 改为 completed/archived，并明确说明：
1. 当前分支复核表明 rollout 主体实现已完成
2. 文档保留为历史基线，不再作为持续执行的主计划
3. 如后续出现新的 release 风险，必须新开增量计划，而不是继续在本计划中追加执行项

### 3. Archive placement
归档位置应延续当前 `docs/plans/archive/` 的完成态目录约定，保证历史检索时可与其他 completed plans 一致浏览。

## Validation Plan
归档完成后执行以下检查：
1. 文档已不再位于 active `docs/plans/` 顶层
2. 归档后文件中的关键引用均指向当前仓库真实位置
3. 头部状态、正文剩余工作、归档定位三者表述一致
4. 文档仍可作为 v1.0 rollout 的历史基线和追溯入口

## Acceptance Criteria
满足以下条件即可视为本次归档完成：
1. `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md` 已从 active plans 移出
2. 归档后的文档不再包含已知失效路径
3. 文档明确标识为已完成且已归档的历史基线
4. 不新增未完成实施计划，因为当前复核未发现 rollout 实现缺口
