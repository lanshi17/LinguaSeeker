# Document Acquisition 文档采集

> 统一文档采集门面，支持本地文件上传和在线文献搜索/下载两种来源。

## 概述

`document_acquisition` 模块提供文档获取的统一接口。通过 `DocumentAcquisitionService` 门面，调用方无需关心底层来源差异——本地上传走 `local_upload` 子模块（验证→哈希→存储），在线获取走 `online_acquisition` 子模块（多提供商搜索→下载→相关性过滤）。

## 结构

```
document_acquisition/
├── __init__.py          # 导出 Service、Request、Result、Source 枚举
├── contracts.py         # 统一数据类型定义
├── service.py           # DocumentAcquisitionService 门面
├── README.md
├── local_upload/        # 本地文件上传子模块
│   ├── contracts.py     # LocalUploadedFile、LocalStoredFile、LocalUploadResult
│   ├── service.py       # 验证与存储逻辑
│   └── workflow.py      # upload_document() 入口
└── online_acquisition/  # 在线文献获取子模块
    ├── contracts.py     # OnlineAcquisitionRequest/Response/Item 等
    ├── gateway.py       # 统一 HTTP 网关（调用 net_io）
    ├── workflow.py       # 三阶段在线获取流水线
    ├── search_service.py # 多语言搜索编排
    ├── normalizers.py    # 各提供商数据标准化器
    ├── pubmed_service.py # PubMed API 集成
    ├── query_translator.py # 查询多语言翻译
    ├── relevance_gate.py # LLM 相关性门控
    ├── literature_type_classifier.py # 文献类型分类
    ├── provider_health.py # 提供商健康追踪
    └── web_search/       # Web 搜索适配器（Firecrawl/Tavily/SerpApi）
```

## 核心组件

### contracts.py — 统一数据类型

- **`AcquisitionSource`**：枚举 `LOCAL` / `ONLINE`
- **`DocumentDownloadEntry`**：单个在线下载结果，含 `file_path`、`pdf_url`、`pre_parsed_markdown`（可跳过 MinerU 重解析）
- **`DocumentAcquisitionRequest`**：统一请求，覆盖本地上传（filename/content）和在线获取（query/identifiers/limit/proxy 等）全部参数
- **`DocumentAcquisitionResult`**：统一响应，含 `stored_file`（本地）或 `items`/`downloads`（在线）、`route` 路由信息、`cached` 标志

### service.py — 门面服务

- **`DocumentAcquisitionService`**：统一入口
  - `acquire(request)` → 根据 `source` 分发到 `_handle_upload()` 或 `_handle_literature()`
  - 本地上传：委托 `local_upload` 模块，支持去重（SHA-256）
  - 在线获取：委托 `online_acquisition.workflow.online_acquisition_workflow()`，返回文献列表和下载结果

## 数据流

```
DocumentAcquisitionRequest
        ↓
DocumentAcquisitionService.acquire()
        ├── LOCAL → local_upload.upload_document()
        │           → validate → SHA-256 → store → LocalStoredFile
        │
        └── ONLINE → online_acquisition_workflow()
                     → search → download → relevance_gate
                     → items[] + downloads[]
        ↓
DocumentAcquisitionResult
```

## 使用

```python
from src.core.ingest_and_digitize_data.document_acquisition import (
    DocumentAcquisitionService, DocumentAcquisitionRequest, AcquisitionSource
)

svc = DocumentAcquisitionService()

# 本地上传
result = await svc.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.LOCAL,
    filename="paper.pdf",
    content=paper_bytes,
))

# 在线搜索
result = await svc.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    query="BRCA1 variant classification",
    limit=20,
    language="auto",
))
```
