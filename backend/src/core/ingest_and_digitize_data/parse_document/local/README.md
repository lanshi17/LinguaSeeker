# Local Parser 本地解析器

> 通过本地 MinerU FastAPI 服务 `/file_parse` 端点解析 PDF。

## 概述

`local` 子模块实现 `ParserStrategy` 接口，通过 HTTP 调用本地部署的 MinerU FastAPI 服务的 `/file_parse` 端点来解析 PDF。适合内网部署或本地 GPU 加速场景，作为远程云 API 解析器的回退方案。

## 结构

```
local/
├── __init__.py    # 空模块标识
├── parser.py      # MinerULocalParser 实现
└── README.md
```

## 核心组件

### parser.py — 本地 MinerU 解析器

- **`MinerULocalParser`**（实现 `ParserStrategy`）：
  - `name` → `"mineru-local"`
  - 构造参数：
    - `parse_url`：MinerU FastAPI 服务地址
    - `model_id`：模型标识
    - `timeout`：请求超时（秒）
    - `dpi`：PDF 渲染 DPI
    - `api_key`：可选 Bearer Token 认证
  - `parse(pdf_path)` → `ParseResult`：
    1. 读取 PDF 文件为 bytes
    2. 以 multipart/form-data POST 到 `/file_parse`
    3. 解析 JSON 响应，提取 metadata、content_list、images
  - 内部方法：
    - `_call_file_parse(pdf_bytes, filename)`：HTTP POST 调用
    - `_parse_file_parse_response(data)`：将响应转为 `ParseResult`
    - `_build_pages(content_list, md_content)`：按 `page_idx` 分组为 `PageContent`
    - `_decode_images(images)`：解码 base64 data-URI 图片

## 数据流

```
PDF 文件路径
    ↓
MinerULocalParser.parse()
    ↓
读取 PDF bytes
    ↓
POST /file_parse (multipart/form-data)
    ├── file: PDF bytes
    ├── model_id, dpi
    └── Authorization: Bearer token
    ↓
JSON 响应 {
    metadata: { title, authors, journal, abstract },
    content_list: [ { type, text, page_idx, ... } ],
    images: { name: base64_data_uri },
    raw_markdown: str
}
    ↓
_parse_file_parse_response()
    ├── 提取 DocumentMetadata
    ├── _build_pages() → 按 page_idx 分组 → List[PageContent]
    └── _decode_images() → { name: bytes }
    ↓
ParseResult { metadata, pages, full_markdown, images, parser_name="mineru-local" }
```

## 使用

```python
from src.core.ingest_and_digitize_data.parse_document.local.parser import MinerULocalParser

parser = MinerULocalParser(
    parse_url="http://localhost:8888",
    model_id="pipeline",
    timeout=120,
    dpi=200,
    api_key="your-api-key",
)
result = await parser.parse("/data/papers/example.pdf")
```
