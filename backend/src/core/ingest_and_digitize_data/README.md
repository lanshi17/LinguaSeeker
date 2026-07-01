# Ingest and Digitize Data 文献采集与数字化

> 阶段 1 流水线：从多种来源采集文献 PDF 并解析为结构化 Markdown。

## 概述

本模块是 ACMG Lingua 阶段 1 的顶层入口，协调两个子流程：**文档采集**（document_acquisition）和**文档解析**（parse_document）。采集环节支持本地文件上传和在线文献搜索/下载；解析环节使用 MinerU 引擎将 PDF 转换为结构化的 Markdown、表格和图片数据。

## 结构

```
ingest_and_digitize_data/
├── README.md
├── document_acquisition/     # 文档采集子模块
│   ├── contracts.py          # 统一数据类型（AcquisitionSource、Request/Result）
│   ├── service.py            # 统一门面服务 DocumentAcquisitionService
│   ├── local_upload/         # 本地文件上传
│   └── online_acquisition/   # 在线文献搜索与下载
└── parse_document/           # 文档解析子模块
    ├── contracts.py          # 解析结果数据类型（ParseResult、PageContent 等）
    ├── base.py               # 解析器抽象基类 ParserStrategy
    ├── service.py            # 解析服务 ParseDocumentService
    ├── orchestrator.py       # 解析编排器（远程优先→本地回退）
    ├── exceptions.py         # 自定义异常
    ├── common/               # 通用解析工具
    ├── local/                # 本地 MinerU 解析器
    └── remote/               # 远程 MinerU 云 API 解析器
```

## 核心组件

### 文档采集（document_acquisition）

- **`DocumentAcquisitionService`**：统一门面，根据 `AcquisitionSource`（LOCAL/ONLINE）分发到对应处理器
- **`DocumentAcquisitionRequest`**：统一请求，包含本地上传参数（filename/content）和在线获取参数（query/identifiers/limit）
- **`DocumentAcquisitionResult`**：统一响应，包含存储文件信息或在线获取的文献列表/下载结果

### 文档解析（parse_document）

- **`ParseDocumentService`**：高级门面，提供 `parse()`、`parse_and_save()`、`dedup()` 等接口
- **`DocumentParseOrchestrator`**：远程优先、本地回退的解析编排策略
- **`ParserStrategy`**：解析器抽象基类，`MinerURemoteParser` 和 `MinerULocalParser` 为具体实现
- **`create_parse_service()`**：工厂函数，从配置创建完整的解析服务实例

## 数据流

```
用户文件 / 在线搜索
        ↓
DocumentAcquisitionService.acquire()
        ↓
本地上传 → validate → hash → store
在线获取 → search → download → relevance_gate
        ↓
    PDF 文件路径
        ↓
ParseDocumentService.parse()
        ↓
DocumentParseOrchestrator (remote → local fallback)
        ↓
ParseResult { metadata, pages[], full_markdown }
```

## 使用

```python
from src.core.ingest_and_digitize_data.document_acquisition import (
    DocumentAcquisitionService, DocumentAcquisitionRequest, AcquisitionSource
)
from src.core.ingest_and_digitize_data.parse_document import create_parse_service

# 采集文献
svc = DocumentAcquisitionService()
result = await svc.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    query="ACMG variant classification",
    limit=10,
))

# 解析 PDF
parse_svc = create_parse_service()
parsed = await parse_svc.parse(result.downloads[0].file_path)
```
