# src/knowledge 说明（代码对齐版）

本目录维护 Prompt 与规则模板，供交互、提取、仲裁环节调用。

## 目录结构

```text
knowledge/
├── ontologies/
└── prompts/
    ├── loader.py
    ├── system.yaml
    ├── extraction.yaml
    ├── arbitration.yaml
    └── acmg_rules.yaml
```

## 当前加载接口

`prompts/loader.py` 暴露：

- `load_prompt_bundle(name)`
- `get_prompt_value(bundle, key)`
- `render_prompt_template(bundle, key, **kwargs)`

内部带 `_PROMPT_CACHE` 做 bundle 级缓存。

## 模板内容来源

- `system.yaml`：交互澄清系统提示词
- `extraction.yaml`：翻译/融合/PS3 提取提示词
- `arbitration.yaml`：仲裁与反馈修订提示词
- `acmg_rules.yaml`：OddsPath 阈值、字段提取规则
