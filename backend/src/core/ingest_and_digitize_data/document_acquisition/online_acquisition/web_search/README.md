# Web Search 搜索适配器

> 基于适配器模式的可插拔 Web 搜索后端，支持 Firecrawl、Tavily、SerpApi。

## 概述

`web_search` 子包使用适配器模式封装多种 Web 搜索服务。每个适配器实现统一的 `WebSearchAdapter` 接口（`search` + `scrape_links`），上游 `workflow.py` 和 `search_service.py` 无需感知底层搜索引擎差异。主要用于在线获取阶段的 Phase 1 链接发现。

## 结构

```
web_search/
├── __init__.py                # 导出 SearchLink、WebSearchAdapter、三个适配器
├── adapter.py                 # 抽象基类 WebSearchAdapter + 数据类型
├── firecrawl_adapter.py       # Firecrawl 适配器（搜索 + JSON 模式抓取）
├── tavily_adapter.py          # Tavily 适配器（搜索 + 内容提取）
├── serpapi_adapter.py         # SerpApi 适配器（Google/Google Scholar）
└── README.md
```

## 核心组件

### adapter.py — 抽象基类

- **`SearchLink`**（frozen dataclass）：候选下载链接（url/source/title/doi）
- **`WebSearchResult`**：搜索结果容器（links/query/provider/warnings）
- **`WebSearchAdapter`**（ABC）：
  - `search(query, language)` → `WebSearchResult`：搜索候选链接
  - `scrape_links(url)` → `List[SearchLink]`：从页面提取 PDF/下载链接
  - 构造参数：`api_key`、`base_url`、`timeout`、`max_results`

### firecrawl_adapter.py — Firecrawl 适配器

- **`FirecrawlAdapter`**：使用 Firecrawl 搜索 API 发现链接 + JSON 模式抓取结构化元数据
  - `search()`：调用 Firecrawl search API，返回候选链接
  - `scrape_links()`：对目标页面执行 JSON 模式抓取，提取 DOI 和 PDF URL
  - 内置 PDF URL 正则提取（markdown/HTML 回退）
  - 支持 DOI → URL 转换

### tavily_adapter.py — Tavily 适配器

- **`TavilyAdapter`**：使用 Tavily 搜索 API，内置内容提取
  - `search()`：调用 Tavily search API，从返回的内容片段中提取 PDF 链接
  - `scrape_links()`：使用 Tavily extract API 从页面提取 PDF 链接
  - 环境变量：`TAVILY_API_KEY`
  - 配置：`search_depth`（basic/advanced）

### serpapi_adapter.py — SerpApi 适配器

- **`SerpApiAdapter`**：使用 SerpApi 搜索引擎结果（Google/Google Scholar/Bing 等）
  - `search()`：调用 SerpApi，解析 organic_results 提取链接
  - `scrape_links()`：SerpApi 不支持页面抓取，返回空列表
  - 配置：`engine`（google/google_scholar/bing 等）

## 数据流

```
搜索查询
    ↓
WebSearchAdapter.search(query)
    ├── FirecrawlAdapter → Firecrawl Search API → 结构化结果
    ├── TavilyAdapter    → Tavily Search API → 内容片段 + URL
    └── SerpApiAdapter   → SerpApi → organic_results
    ↓
WebSearchResult { links: List[SearchLink] }
    ↓
WebSearchAdapter.scrape_links(url)  # 可选：深入页面提取 PDF 链接
    ↓
List[SearchLink] → 合并到在线获取流水线
```

## 使用

```python
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search import (
    TavilyAdapter, SerpApiAdapter, FirecrawlAdapter
)

# Tavily 搜索
adapter = TavilyAdapter(api_key="tvly-...", max_results=10)
result = await adapter.search("ACMG variant classification", language="en")
for link in result.links:
    print(link.url, link.doi)

# SerpApi Google Scholar 搜索
adapter = SerpApiAdapter(api_key="...", engine="google_scholar")
result = await adapter.search("BRCA1 pathogenic variant")
```
