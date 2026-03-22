# src/domain 说明（代码对齐版）

`src/domain` 承载核心业务对象与领域服务，当前包含证据、图谱、文献获取、变异注释、Agent 工作流等子域。

## 目录结构（顶层）

```text
domain/
├── models.py
├── enums.py
├── abc/
├── agent/
├── evidence/
├── graph/
├── literature/
├── mineru/
├── variant/
├── task_models/
└── impl/
```

## 子域概览

- `agent/`
  - `workflow.py`：`EvidenceAgent`
  - `interaction.py`：任务表单澄清会话
  - `document_parsing.py`：解析代理与产物收集
  - `prompts.py`：Prompt 组装
- `evidence/`
  - 证据聚合、分类、评估框架与工具注册
- `graph/`
  - 图检索、实体关联分析、Postgres->Neo4j 同步逻辑
- `literature/`
  - PubMed、Firecrawl、Unified workflow
  - API 提供方实现：`api/crossref|doaj|jstage|pmc|unpaywall`
  - 自动化网页流程：`automated_web/*`
- `variant/`
  - ClinVar / ClinGen 客户端及聚合服务
- `mineru/`
  - MinerU 解析组件与常量
- `impl/`
  - 具体实现类（如 `pdf_parser.py`, `document_storage.py`），被历史路径依赖

## 备注

- `domain/__init__.py` 采用惰性 try-import 兼容策略，避免启动时强耦合。
- 代码中同时存在“当前主流程实现”和“历史兼容模块”。README 仅按文件现状描述。
