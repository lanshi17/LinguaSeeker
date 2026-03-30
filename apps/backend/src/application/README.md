# src/application 说明（代码对齐版）

该目录提供应用层 DTO、服务与异步处理器。当前代码同时存在新旧实现并存情况。

## 目录结构

```text
application/
├── dtos/document_dto.py
├── enums/task_status.py
├── processors/async_document_processor.py
└── services/
    ├── base_service.py
    ├── document_service.py
    ├── embedding_service.py
    ├── llm_service.py
    └── rerank_service.py
```

## 主要模块

- `dtos/document_dto.py`
  - `DocumentUploadDTO`
  - `DocumentProcessResultDTO`
- `enums/task_status.py`
  - 应用层任务状态枚举（`pending/processing/completed/failed/cancelled`）
- `processors/async_document_processor.py`
  - Celery 任务提交、查询、取消封装
- `services/document_service.py`
  - 文档解析与 MinIO 存储编排（调用 `domain.impl`）
- `services/base_service.py`
  - 服务基类抽象

## 现状说明

- `embedding_service.py` 与 `rerank_service.py` 当前都定义了 `EmbeddingService`（遗留命名）。
- `llm_service.py` 依赖旧路径 `infrastructure.adapters.llm.llm_client`，属于历史兼容代码区。
