# Document Acquisition 文档采集

> 统一文档采集门面，支持本地文件上传和在线文献搜索/下载两种来源。

## 概述

`document_acquisition` 模块提供文档获取的统一接口。通过 `DocumentAcquisitionService` 门面，调用方无需关心底层来源差异--本地上传走 `local_upload` 子模块（验证->哈希->存储），在线获取委托外部 **`lit-acquisition` SDK**（`multilingual_acquisition_workflow` / `online_acquisition_workflow`，多提供商搜索->下载->相关性过滤）。

## 结构

```
document_acquisition/
├── __init__.py          # 导出 Service、Request、Result、Source 枚举
├── contracts.py         # 统一数据类型定义（Item/RouteInfo 复用 lit_acquisition 模型）
├── service.py           # DocumentAcquisitionService 门面
├── README.md
└── local_upload/        # 本地文件上传子模块
    ├── contracts.py     # LocalUploadedFile、LocalStoredFile、LocalUploadResult
    ├── service.py       # 验证与存储逻辑
    └── workflow.py      # upload_document() 入口
```

在线文献获取（搜索、下载、多语言翻译、相关性门控、提供商健康追踪、Web 搜索适配器）由 **`lit-acquisition` SDK** 提供：本地路径依赖（`../../17_lit-acquisition`，editable，声明于 `backend/pyproject.toml` 的 `[tool.uv.sources]`）。SDK 自身的 LLM / Web 搜索 / 代理配置在应用启动时由 `src/api/wiring.py::_configure_lit_acquisition()` 从后端配置桥接注入；`UNPAYWALL_EMAIL` / `PUBMED_API_KEY` 等提供商密钥经后端 YAML 扁平化为环境变量后由 SDK 自动读取。

## 核心组件

### contracts.py — 统一数据类型

- **`AcquisitionSource`**：枚举 `LOCAL` / `ONLINE`
- **`DocumentDownloadEntry`**：单个在线下载结果，含 `file_path`、`pdf_url`、`pre_parsed_markdown`（可跳过 MinerU 重解析）
- **`DocumentAcquisitionRequest`**：统一请求，覆盖本地上传（filename/content）和在线获取（query/identifiers/limit/proxy 等）全部参数
- **`DocumentAcquisitionResult`**：统一响应，含 `stored_file`（本地）或 `items`/`downloads`（在线）、`route` 路由信息、`cached` 标志

### service.py — 门面服务

- **`DocumentAcquisitionService`**：统一入口
  - `acquire(request)` -> 根据 `source` 分发到 `_handle_upload()` 或 `_handle_literature()`
  - 本地上传：委托 `local_upload` 模块，支持去重（SHA-256）
  - 在线获取：委托 `lit_acquisition.multilingual_acquisition_workflow()`（自由文本 + `language="auto"` 时）或 `lit_acquisition.online_acquisition_workflow()`（单语言 / 标识符驱动），返回文献列表和下载结果

## 数据流

```
DocumentAcquisitionRequest
        ↓
DocumentAcquisitionService.acquire()
        ├── LOCAL → local_upload.upload_document()
        │           → validate → SHA-256 → store → LocalStoredFile
        │
        └── ONLINE -> lit_acquisition workflow（SDK）
                     -> search -> download -> relevance_gate
                     -> items[] + downloads[]
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
