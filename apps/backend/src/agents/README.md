# src/agents 说明（代码对齐版）

本目录是工作流编排层，核心由 `supervisor.py` 负责构建 LangGraph 图，节点实现分布在各子目录。

## 目录结构

```text
agents/
├── supervisor.py
├── acquisition/
│   ├── node.py
│   ├── api_tool.py
│   └── crawl_tool.py
├── parsing/
│   ├── node.py
│   ├── mineru_tool.py
│   └── translation_tool.py
├── extraction/
│   ├── node.py
│   ├── extraction_tool.py
│   └── validator_tool.py
├── reasoning/node.py
├── arbitration/
│   ├── node.py
│   ├── ps3_bs3_evaluator.py
│   └── rule_checker.py
└── interaction/
    ├── node.py
    └── prompts.py
```

## 核心职责

- `supervisor.py`
  - 定义节点图与条件路由。
  - 暴露 `build_supervisor_graph()` / `compile_supervisor()`。
- `*/node.py`
  - 节点态输入输出转换。
  - 维护 `SupervisorState` 关键字段。
- `*_tool.py`
  - 多为对 `src/domain` 或 `src/services` 的导出封装（re-export / thin wrapper）。

## 当前流程节点顺序

`route_by_source -> interaction -> acquisition -> parsing -> translation -> extraction -> reasoning -> arbitration -> finalize/human_review/finalize_failed`

## 备注

- `acquisition` 节点在代码中支持 `upload/pubmed/web` 三类 source。
- `interaction` 节点通过 `domain.agent.interaction.InteractionAgent` 做最多两轮澄清式表单提取。
