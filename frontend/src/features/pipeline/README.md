# Pipeline 流水线功能

> 三阶段文献处理流水线的启动、监控和历史管理

## 概述

Pipeline 模块管理 Lingua Seeker 的三阶段文献处理流水线：
1. **Phase 1 — 文献获取**（Acquisition）：解析 PDF/在线检索
2. **Phase 2 — 证据提取**（Extraction）：LLM 驱动的 ACMG 证据提取
3. **Phase 3 — 标准化**（Standardization）：证据标准化与入库

支持启动新运行、实时监控进度（2 秒轮询）、查看历史记录和阶段详情。

## 文件结构

```
pipeline/
├── index.ts                          # 模块导出
├── pipeline.css                      # 样式
├── components/
│   ├── PipelineStatusView.tsx        # 流水线状态主视图
│   ├── PhaseTimeline.tsx             # 阶段时间线
│   ├── PhaseDetailCard.tsx           # 阶段详情卡片
│   ├── RunHistory.tsx                # 运行历史列表
│   ├── RunListItem.tsx               # 运行列表项
│   ├── TaskQueuePanel.tsx            # 任务队列面板
│   └── TaskQueueRow.tsx              # 任务队列行
├── hooks/
│   ├── usePipelineRun.ts            # 启动运行 mutation hook
│   ├── usePipelineStatus.ts         # 运行状态轮询 hook（2s 间隔）
│   ├── usePipelineRuns.ts           # 运行列表查询 hook（5s 轮询）
│   └── usePhaseTimeline.ts          # 阶段时间线数据投影 hook
├── services/
│   └── pipeline.ts                  # API 服务层
├── types/
│   └── pipeline.ts                  # 流水线类型定义
└── README.md
```

## 关键组件

### `PipelineStatusView`

流水线运行状态主视图，展示当前运行的阶段进度、任务队列和指标。

### `PhaseTimeline`

阶段时间线组件，水平展示三个阶段的状态和耗时。

### `PhaseDetailCard`

单个阶段的详情卡片，展示子节点（文献提供者、LLM 步骤）的状态、耗时和指标。

### `RunHistory`

运行历史列表，支持分页、状态筛选和搜索。

### `TaskQueuePanel` / `TaskQueueRow`

任务队列面板，展示流水线中各任务的执行状态。

## Hooks

### `usePipelineRun()`

启动新流水线运行的 mutation hook。

- **返回**: `useMutation` 对象，调用 `startPipelineRun(body)`

### `usePipelineStatus(runId)`

运行状态轮询 hook。

- 运行中/排队中：每 2 秒轮询
- 终态（completed/failed/skipped）或超过 30 分钟：停止轮询
- **返回**: `{ data: PipelineStatusResponse, isLoading, error }`

### `usePipelineRuns(params?)`

运行列表查询 hook。

- 支持分页、状态筛选、搜索
- 每 5 秒轮询更新
- **返回**: `{ data: PipelineRunListResponse, isLoading }`

### `usePhaseTimeline(status, t)`

将 `PipelineStatusResponse` 投影为 `PhaseTimelineStep[]`，用于时间线组件渲染。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/pipeline/run` | 启动流水线运行 |
| GET | `/pipeline/runs/{id}/status` | 查询运行状态 |
| GET | `/pipeline/runs` | 列出运行历史 |

## 类型

- `PipelineRunRequest` — 启动请求（source_type、mode、content_base64、query 等）
- `PipelineStatusResponse` — 运行状态（pipeline_status、phases 字典）
- `PhaseStatus` — 阶段状态（status、duration_seconds、PhaseNode 子节点）
- `PipelineRunSummary` — 运行历史摘要
- `ProcessingStatus` — 状态枚举：`pending` / `running` / `completed` / `failed` / `skipped`
- `PhaseId` — 阶段标识：`phase_1` / `phase_2` / `phase_3`
