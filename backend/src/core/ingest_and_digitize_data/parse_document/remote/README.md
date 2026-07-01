# Remote Parser 远程解析器

> 通过 MinerU 云端 API 解析 PDF，支持异步任务提交与轮询。

## 概述

`remote` 子模块实现 `ParserStrategy` 接口，调用 MinerU 云端 API 进行 PDF 解析。采用异步任务模式：提交解析任务 → 轮询状态 → 下载结果。支持单文件解析和批量本地文件上传解析，是 `DocumentParseOrchestrator` 的首选解析器。

## 结构

```
remote/
├── __init__.py    # 导出 MinerURemoteParser
├── parser.py      # MinerURemoteParser 实现（云 API + 批量上传）
└── README.md
```

## 核心组件

### parser.py — 远程 MinerU 解析器

- **`MinerURemoteParser`**（实现 `ParserStrategy`）：
  - `name` → `"mineru-remote"`
  - 构造参数：
    - `api_token`：MinerU 云 API Token
    - `poll_interval`：轮询间隔（秒）
    - `max_poll_attempts`：最大轮询次数
  - `parse(pdf_path)` → `ParseResult`：
    1. 支持本地路径和 URL 输入
    2. 提交解析任务到 MinerU 云 API
    3. 轮询任务状态直到完成或超时
    4. 下载并解析结果（Markdown + 图片 + 元数据）
  - `parse_local_files(file_paths, **kwargs)` → `MinerULocalBatchParseResult`：
    1. 上传本地文件到 MinerU 预签名 URL
    2. 提交批量解析任务
    3. 轮询批量状态直到所有文件完成
    4. 返回每个文件的解析结果

### 内部类型

- **`_MinerUPageData`**：单页原始数据（page_number/markdown/figures/tables）
- **`_MinerURawResult`**：完整原始结果（state/total_pages/title/authors/abstract/pages/full_markdown/images/raw_blocks）

### 关键特性

- 使用 `net_io`（Rust IO 层）进行 HTTP 请求
- 支持 `MinerUModelVersion`：`pipeline`、`vlm`、`MinerU-HTML`
- 支持 `MinerUExtraFormat`：`docx`、`html`、`latex`
- 结果解析使用 `common/converters.py` 的 `block_to_markdown()` 和 `html_table_to_structured()`
- 提取文档摘要使用 `markdown_helpers.extract_abstract_from_markdown()`
- 超时抛出 `MinerUTimeoutError`，API 错误抛出 `MinerUAPIError`

## 数据流

```
PDF 文件路径（本地或 URL）
        ↓
MinerURemoteParser.parse()
        ↓
提交解析任务 → MinerU 云 API
        ↓
轮询任务状态 (poll_interval × max_attempts)
  ├── running/converting → 继续等待
  ├── done → 下载结果
  └── failed → MinerUAPIError
        ↓
下载结果 JSON {
    state, total_pages, title, authors, abstract,
    pages: [ { page_number, markdown, figures, tables } ],
    full_markdown, images, raw_blocks
}
        ↓
解析结果
  ├── DocumentMetadata(title, authors, journal, abstract)
  ├── List[PageContent] (按 page 分组)
  ├── images: { name: bytes }
  └── block_to_markdown() 处理 raw_blocks
        ↓
ParseResult { metadata, pages, full_markdown, images, parser_name="mineru-remote" }
```

### 批量解析流程

```
List[file_paths]
        ↓
上传到 MinerU 预签名 URL (net_io.put)
        ↓
提交批量任务
        ↓
轮询批量状态 → MinerUBatchStatus
        ↓
MinerULocalBatchParseResult {
    batch_id, status: MinerUBatchStatus,
    results: { filename: ParseResult }
}
```

## 使用

```python
from src.core.ingest_and_digitize_data.parse_document.remote.parser import MinerURemoteParser

parser = MinerURemoteParser(
    api_token="your-mineru-token",
    poll_interval=2,
    max_poll_attempts=150,
)

# 单文件解析
result = await parser.parse("/data/papers/example.pdf")
# 或 URL
result = await parser.parse("https://example.com/paper.pdf")

# 批量解析
batch_result = await parser.parse_local_files([
    "/data/papers/paper1.pdf",
    "/data/papers/paper2.pdf",
])
```
