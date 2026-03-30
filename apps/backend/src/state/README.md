# src/state 说明（代码对齐版）

本目录定义 supervisor 工作流的状态契约。

## 目录结构

```text
state/
├── global_state.py
└── schemas.py
```

## 模块说明

- `global_state.py`
  - 定义 `SupervisorState`（`TypedDict`）
  - 覆盖请求级、论文级、节点跟踪、解析/提取/仲裁结果、交互字段等状态键
- `schemas.py`
  - 主要作为 re-export 层，导出 `src.domain.models` 与 `src.domain.enums` 中的状态相关模型

## 关键点

- 工作流节点之间通过 `SupervisorState` 传递字段。
- API/任务层与节点层共享该状态契约，修改字段前需同步上下游。
