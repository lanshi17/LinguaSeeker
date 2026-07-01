# Parse Document 文档解析

> MinerU VLM 引擎驱动的 PDF 解析模块，支持远程云 API 和本地 FastAPI 双模式。

## 概述

`parse_document` 模块负责将 PDF 文档解析为结构化的 Markdown、表格和图片数据。采用策略模式，提供 `MinerURemoteParser`（云端 API）和 `MinerULocalParser`（本地 FastAPI 服务）两种解析器实现，由 `DocumentParseOrchestrator` 编排为远程优先、本地回退的容错策略。

## 结构

```
parse_document/
├── __init__.py          # 工厂函数 create_parse_service() + 全量导出
├── contracts.py         # 数据类型：ParseResult、PageContent、TableStructure 等
├── base.py              # 抽象基类 ParserStrategy
├── service.py           # 高级门面 ParseDocumentService
├── orchestrator.py      # 远程优先→本地回退编排器 DocumentParseOrchestrator
├── exceptions.py        # 自定义异常层级
├── common/              # 通用解析工具
│   ├── converters.py    # HTML→Markdown 转换、block→Markdown 转换
│   └── parsers.py       # HTML TableParser
├── local/               # 本地 MinerU 解析器
│   └── parser.py        # MinerULocalParser（调用本地 FastAPI /file_parse）
└── remote/              # 远程 MinerU 解析器
    └── parser.py        # MinerURemoteParser（调用 MinerU 云 API）
```

## 核心组件

### contracts.py — 数据类型

- **`DocumentMetadata`**：文档级元数据（title/authors/journal/abstract_text）
- **`PageContent`**：单页内容（page_number/markdown/figures/tables）
- **`FigurePosition`**：图片位置信息（page/caption/index/img_path）
- **`TableStructure`**：结构化表格（headers/rows）
- **`ParseResult`**：完整解析结果（metadata/pages/full_markdown/images/parser_name）
- **`SavedFiles`**：保存结果（output_dir/markdown_path/metadata_path/images_dir）
- **`DedupResult`**：去重检查结果（file_path/sha256/is_duplicate）
- **MinerU 批量类型**：`MinerULocalBatchOptions`、`MinerUBatchStatus`、`MinerULocalBatchParseResult` 等
- **`ParseAndSaveResult`**：`ParseResult` 扩展，含 `saved_files`

### base.py — 策略接口

- **`ParserStrategy`**（ABC）：
  - `name`：解析器标识符（property）
  - `parse(pdf_path)` → `ParseResult`：解析 PDF 文件

### orchestrator.py — 编排器

- **`DocumentParseOrchestrator`**（实现 `ParserStrategy`）：
  - 远程优先策略：先尝试 `MinerURemoteParser`，失败则回退 `MinerULocalParser`
  - URL 输入自动下载到临时文件供本地解析器使用
  - 两者均失败时抛出 `ParserExhaustedError`
  - `parse_local_files()`：批量本地文件解析（委托远程解析器）

### service.py — 高级门面

- **`ParseDocumentService`**：
  - `parse(pdf_path)` → `ParseResult`：单文件解析
  - `parse_local_files(file_paths)` → `MinerULocalBatchParseResult`：批量解析
  - `save(result, output_dir)` → `SavedFiles`：保存解析结果（Markdown + 元数据 JSON + 图片）
  - `dedup(file_paths)` → `List[DedupResult]`：SHA-256 去重检查
  - `parse_and_save(pdf_path, output_dir)` → `ParseAndSaveResult`：解析 + 保存一步到位

### exceptions.py — 异常层级

- **`ParseDocumentError`**：基类
- **`MinerUAPIError`**：MinerU API 错误（含 status_code）
- **`MinerUTimeoutError`**：MinerU 轮询超时（含 total_timeout）
- **`ParserExhaustedError`**：所有解析器均失败（含 errors 字典）

### 工厂函数

- **`create_parse_service(config)`**：从配置创建 `ParseDocumentService` 实例，自动组装远程/本地解析器和编排器

## 数据流

```
PDF 文件路径（本地路径或 URL）
        ↓
ParseDocumentService.parse()
        ↓
DocumentParseOrchestrator.parse()
        ├── MinerURemoteParser (远程优先)
        │   → MinerU 云 API → 轮询结果 → ParseResult
        │
        └── MinerULocalParser (本地回退)
            → POST /file_parse → 解析响应 → ParseResult
        ↓
ParseResult {
    metadata: { title, authors, journal, abstract },
    pages: [ { page_number, markdown, figures, tables } ],
    full_markdown: str,
    images: { name: bytes },
    parser_name: "mineru-remote" | "mineru-local"
}
```

## 使用

```python
from src.core.ingest_and_digitize_data.parse_document import create_parse_service

# 创建服务（从全局配置）
svc = create_parse_service()

# 解析 PDF
result = await svc.parse("/data/papers/example.pdf")
print(result.metadata.title)
for page in result.pages:
    print(f"Page {page.page_number}: {len(page.tables)} tables")

# 解析 + 保存
saved = await svc.parse_and_save("/data/papers/example.pdf", "/data/output/")
print(saved.saved_files.markdown_path)
```
