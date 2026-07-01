# Online Acquisition 在线文献获取

> 三阶段在线文献获取流水线：链接发现 → PDF 下载 → LLM 相关性过滤。

## 概述

`online_acquisition` 模块实现从多个学术数据库和搜索引擎在线获取文献的完整流程。支持 15+ 个提供商（CrossRef、PubMed/PMC、Unpaywall、OpenAlex、J-STAGE、DOAJ、SciELO、EuropePMC 等），提供多语言搜索（英/中/日/德/法/俄）、智能路由、提供商健康追踪和 LLM 相关性门控。

## 结构

```
online_acquisition/
├── __init__.py                      # 导出核心 API
├── contracts.py                     # 数据类型：Request/Response/Item/Gateway 等
├── workflow.py                      # 三阶段流水线 + 多语言采集工作流
├── gateway.py                       # 统一 HTTP 网关（委托 net_io）
├── search_service.py                # 多语言提供商规划与搜索编排
├── normalizers.py                   # 各提供商数据标准化器（15+ 提供商）
├── pubmed_service.py                # PubMed esearch/esummary/efetch 集成
├── query_translator.py              # LLM 查询多语言翻译（6 语言）
├── relevance_gate.py                # LLM 相关性门控（PDF 前 N 页分析）
├── literature_type_classifier.py    # 关键词文献类型分类器
├── provider_health.py               # 滑动窗口提供商健康追踪
└── web_search/                      # Web 搜索适配器子包
    ├── adapter.py                   # 抽象基类 WebSearchAdapter
    ├── firecrawl_adapter.py         # Firecrawl 搜索 + JSON 模式抓取
    ├── tavily_adapter.py            # Tavily 搜索 API
    └── serpapi_adapter.py           # SerpApi（Google/Google Scholar）
```

## 核心组件

### contracts.py — 数据类型

- **`OnlineAcquisitionRequest`**：统一请求（query/identifiers/limit/prefer/api_provider/relevance_gate/literature_types 等）
- **`OnlineAcquisitionItem`**：标准化文献元数据（title/doi/authors/journal/year/links/literature_type）
- **`OnlineAcquisitionResponse`**：统一响应（items/downloads/route/cached/warnings）
- **`OnlineAcquisitionGatewayRequest/Result`**：内部网关请求/结果（含 source_trace 调试链）
- **`DownloadResult`**：单文件下载结果（file_path/pdf_url/warnings）
- **`ApiProvider`**：支持的 API 提供商字面量类型

### workflow.py — 三阶段流水线

- **`online_acquisition_workflow(payload)`**：
  1. **Phase 1 — 链接发现**：API 搜索（并行多提供商）+ Web 搜索 → 合并去重
  2. **Phase 2 — PDF 下载**：候选链接 → 逐个下载 → 类型过滤
  3. **Phase 3 — 相关性门控**：LLM 分析 PDF 前 N 页 → 过滤不相关文献
- **`multilingual_acquisition_workflow(payload)`**：多语言版本，先翻译查询再搜索

### gateway.py — HTTP 网关

- **`call_provider(request)`**：调用单个提供商（委托 `net_io.fetch_one`）
- **`call_provider_with_retry(request, max_retries)`**：带重试的提供商调用
- **`search_provider(...)`** / **`download_file_from_url(...)`**：高层便捷函数
- **`resolve_oa_url(result)`**：从网关结果提取 OA 下载 URL

### search_service.py — 搜索编排

- **`build_provider_plan(language, hints)`**：基于语言的提供商执行计划
- **`search_multilingual(...)`**：多语言搜索，按语言路由到对应提供商
- **`search_parallel(...)`**：并行多提供商搜索 + 去重 + 排名
- **`dedupe_candidates()`**：按 DOI/URL/标题去重
- **`rank_candidates()`**：按标题匹配度、DOI 存在性排序

### normalizers.py — 数据标准化

- **`normalize_items(provider, items)`**：统一入口，根据提供商名分发到对应标准化器
- 支持 15+ 提供商：CrossRef、Unpaywall、PMC、J-STAGE、DOAJ、OpenAlex、SciELO、BASE、CORE、OpenAIRE、CiNii、EuropePMC、Firecrawl、preprint 等

### 其他关键组件

- **`OnlineAcquisitionPubMedService`**：PubMed API 集成（esearch → esummary → efetch）
- **`translate_query()`**：LLM 将查询翻译为 6 种语言（en/zh/ja/de/fr/ru）
- **`run_relevance_gate()`**：LLM 并发检查 PDF 相关性（支持文档类型分类）
- **`LiteratureTypeClassifier`**：基于关键词的文献类型分类（case_report/sequencing/functional）
- **`ProviderHealthTracker`**：线程安全滑动窗口健康追踪，自动降级不健康提供商

## 数据流

```
query / identifiers
        ↓
online_acquisition_workflow()
        ↓
Phase 1: 链接发现
  ├── API 搜索（CrossRef/PMC/Unpaywall 等并行）
  └── Web 搜索（Tavily/Firecrawl/SerpApi）
        ↓ 合并去重
Phase 2: PDF 下载
  ├── 候选链接 → download_file_from_url()
  └── 文献类型过滤（可选）
        ↓
Phase 3: LLM 相关性门控
  ├── PDF 前 N 页提取文本
  └── LLM 判断相关性 + 文档类型
        ↓
OnlineAcquisitionResponse { items[], downloads[], route }
```

## 使用

```python
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition import (
    online_acquisition_workflow, multilingual_acquisition_workflow
)

# 单语言搜索
result = await online_acquisition_workflow({
    "query": "ACMG variant classification guidelines",
    "limit": 20,
    "language": "en",
    "relevance_gate": True,
})

# 多语言搜索
result = await multilingual_acquisition_workflow({
    "query": "BRCA1 基因变异分类",
    "limit": 50,
    "languages": ["en", "zh", "ja"],
})
```
