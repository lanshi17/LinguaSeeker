# src/infrastructure 说明（代码对齐版）

本目录实现数据库与外部系统客户端、ORM 模型、以及部分适配器。

## 目录结构

```text
infrastructure/
├── models.py
├── enum.py
├── dtos.py
├── postgres.py
├── neo4j.py
├── qdrant.py
├── redis.py
├── minio.py
├── adapters/mineru/
└── store/
```

## 关键模块

- `models.py`
  - SQLAlchemy 模型：`Document`, `Task`, `TaskRequest`, `PaperTask`, `EvidenceRecord` 等
- `postgres.py`
  - 连接构建、schema 初始化、`PostgresClient` CRUD 与 request/paper task 更新
- `neo4j.py`
  - 图模型 upsert/link、检索与 schema 初始化
- `qdrant.py`
  - `QdrantManager`（建库、写入、检索、健康检查）
- `redis.py`
  - 哈希缓存与 Celery 元信息辅助
- `minio.py`
  - MinIO 高层异步包装（桶管理、上传下载、签名链接）

## 适配器与存储

- `adapters/mineru/`：MinerU 接口与实现
- `store/base_store.py` + `store/minio_store.py`：旧式存储抽象与 MinIO 实现（仍有路径引用）

## 说明

`src/infrastructure` 里同时存在新接口（如 `minio.py`）与历史实现（如 `store/minio_store.py`），请按调用方选择。
