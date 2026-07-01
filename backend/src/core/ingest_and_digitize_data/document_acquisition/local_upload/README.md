# Local Upload 本地文件上传

> 本地文件上传子模块：验证、哈希并存储用户上传的文档。

## 概述

`local_upload` 处理从本地文件系统上传的文档。流程为：验证文件（扩展名、大小、PDF 魔数）→ 计算 SHA-256 → 存储到指定目录。支持 `.pdf`、`.doc`、`.docx` 格式，最大 50MB。

## 结构

```
local_upload/
├── __init__.py       # 导出 upload_document、validate/store 函数和数据类型
├── contracts.py      # 数据类型：LocalUploadedFile、LocalStoredFile、LocalUploadResult
├── service.py        # 验证逻辑 validate_local_upload() 和存储逻辑 store_local_file()
├── workflow.py       # 公开入口 upload_document()
└── README.md
```

## 核心组件

### contracts.py — 数据类型

- **`ALLOWED_EXTENSIONS`**：`frozenset({".pdf", ".doc", ".docx"})`
- **`MAX_FILE_SIZE_BYTES`**：50MB (50 × 1024 × 1024)
- **`LocalUploadedFile`**（frozen dataclass）：`filename`、`content`、`content_type`、`size`（自动计算）
- **`LocalStoredFile`**（frozen dataclass）：`file_path`、`sha256`、`original_filename`、`size`、`content_type`
- **`LocalUploadResult`**：`success`、`stored_file`、`warnings`、`error`

### service.py — 验证与存储

- **`validate_local_upload(file)`**：验证扩展名、大小、PDF 魔数（`%PDF`），返回错误列表
- **`store_local_file(file, upload_dir, deduplicate)`**：调用 `files_io`（Rust IO）计算 SHA-256 并写入磁盘，支持去重

### workflow.py — 公开入口

- **`upload_document(filename, content, content_type, upload_dir)`**：组合验证和存储，返回 `LocalUploadResult`

## 数据流

```
filename + bytes
      ↓
upload_document()
      ↓
LocalUploadedFile (自动计算 size)
      ↓
validate_local_upload() → [错误列表] → 失败则返回 LocalUploadResult(success=False)
      ↓ 通过
store_local_file() → files_io.sha256() + files_io.write()
      ↓
LocalStoredFile { file_path, sha256, size }
      ↓
LocalUploadResult(success=True, stored_file=...)
```

## 使用

```python
from src.core.ingest_and_digitize_data.document_acquisition.local_upload import upload_document

result = upload_document(
    filename="paper.pdf",
    content=pdf_bytes,
    content_type="application/pdf",
    upload_dir="/data/uploads",
)
if result.success:
    print(result.stored_file.file_path, result.stored_file.sha256)
```
