# Phase 2: 跨语言处理与证据提取

> 跨语言文档翻译、格式化和 ACMG/GDV 证据提取的全流程管线

## 概述

本模块是医学遗传学文献自动化管线的核心阶段，负责将多语言生物医学文献翻译为英文，并从中提取结构化的 ACMG/GDV 证据。管线基于 LangGraph 构建，分为两大子系统：

1. **跨语言处理 (`cross_lingual/`)** — 文档格式化、语言检测、多阶段 LLM 翻译、翻译质量验证
2. **证据提取 (`extract_evidence/`)** — 双轨证据提取（原文轨 + 译文轨）、交叉校验、源文本溯源

模块通过 `TranslationService` 和 `EvidenceExtractionService` 对外提供统一 API，支持单文档和双轨文档处理模式。

## 结构

```
cross_lingual_process_and_extract_evidence/
├── __init__.py              # 模块入口，导出核心类型
├── contracts.py             # 全局数据契约（PipelineState, TranslationResult 等）
├── config_context.py        # TranslationConfigContext — LLM 配置注入点
├── router.py                # LanguageRouter — 语言路由决策
├── workflow.py              # TranslationService — LangGraph 翻译编排
├── persistence.py           # DocumentPersistenceService — 本地文件持久化
├── cross_lingual/           # 跨语言处理子系统
│   ├── format/              # 文档格式化与规范化
│   └── translate/           # 多阶段 LLM 翻译引擎
└── extract_evidence/        # 证据提取子系统
    ├── stages/              # LangGraph 流水线阶段
    ├── reconcile/           # 双轨证据交叉校验
    └── verify/              # 证据验证
```

## 核心组件

### 数据契约 (`contracts.py`)

| 类型 | 说明 |
|------|------|
| `PipelineState` | LangGraph 管线状态（Pydantic Model），包含 pages、formatted、result 等字段 |
| `ContentBlock` | 结构化内容块，遵循 MinerU content_list.json 格式 |
| `FormattedDocument` | 格式化输出，含 markdown、句子区域、布局漂移报告 |
| `TranslationSegment` | 翻译段落，含 bbox 映射回原始文本 |
| `TranslationResult` | 翻译最终输出，含术语表、段落、翻译块、对齐信息 |
| `CrossLingualOutput` | 下游模块的类型化输出契约 |
| `SavedDocuments` | 文件持久化结果 |

### 翻译服务 (`workflow.py`)

`TranslationService` 是跨语言处理的公共 API：

- **LangGraph 节点**：`format` → `detect_language` → 条件路由 → `translate` / `skip_translate`
- **`run(pages, content_blocks)`** — 异步执行翻译管线
- **`run_sync(...)`** — 同步包装
- **`save(result, ...)`** — 持久化翻译结果并返回 `CrossLingualOutput`

### 语言路由 (`router.py`)

`LanguageRouter.route(state)` — 基于 CJK 比率和 lingua 语言检测决定是否跳过翻译。

### 配置上下文 (`config_context.py`)

`TranslationConfigContext` — 冻结数据类，封装 model、api_key、api_keys、base_url、temperature、max_tokens、timeout，从 `cfg.translation` 构建。

### 文件持久化 (`persistence.py`)

`DocumentPersistenceService` — 将 `TranslationResult` 持久化到本地文件系统，支持 rust_io 加速写入：
- 保存翻译文本、原文文本、翻译对齐 JSON、图像文件
- 构建确定性源文本-英文对齐（`_build_translation_alignment`）
- 输出 `SavedDocuments` 和 `CrossLingualOutput`

## 数据流

```
原始文档 pages + content_blocks
    │
    ▼
MarkdownFormatter.format()     ── 格式化、规范化、OCR修复
    │
    ▼
detect_language()              ── 语言检测
    │
    ├── 英文 → skip_translate  ── 直接输出
    │
    ▼
MultiStageTranslator           ── 3阶段翻译: 术语提取 → 翻译 → 验证
    │
    ▼
DocumentPersistenceService     ── 保存到本地文件系统
    │
    ▼
CrossLingualOutput             ── 传递给 extract_evidence 子系统
    │
    ▼
EvidenceExtractionService      ── 双轨证据提取 + 交叉校验
    │
    ▼
EvidenceExtractionResult       ── 结构化 ACMG/GDV 证据
```

## 使用

```python
from src.core.cross_lingual_process_and_extract_evidence import TranslationService

# 初始化
service = TranslationService(cfg)

# 执行翻译管线
result = await service.run(pages, content_blocks)

# 持久化结果
output = service.save(result, output_dir, document_id)
```

证据提取通过 `extract_evidence/api.py` 的 `EvidenceExtractionService` 访问，支持单轨和双轨模式。
