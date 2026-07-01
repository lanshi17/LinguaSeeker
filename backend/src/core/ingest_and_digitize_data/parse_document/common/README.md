# Common 通用解析工具

> 文档解析的通用工具集：HTML 表格解析和内容块 Markdown 转换。

## 概述

`common` 子包提供文档解析过程中共享的工具函数和解析器。核心功能包括 HTML 表格到 Markdown/结构化数据的转换，以及 MinerU content_list 块到 Markdown 的转换。被 `local/parser.py` 和 `remote/parser.py` 共同使用。

## 结构

```
common/
├── __init__.py       # 导出 TableParser、转换函数
├── converters.py     # 内容转换：HTML 表格→Markdown、block→Markdown
├── parsers.py        # HTML 解析器：TableParser
└── README.md
```

## 核心组件

### parsers.py — HTML 解析器

- **`TableParser`**（继承 `HTMLParser`）：解析 HTML `<table>` 元素
  - `rows: list[list[str]]`：提取的行数据
  - `has_th: bool`：是否包含 `<th>` 表头行
  - 逐行解析 `<tr>` → `<td>`/`<th>` 单元格

### converters.py — 内容转换

- **`html_table_to_markdown(html)`**：HTML `<table>` → Markdown 表格字符串
  - 使用 `TableParser` 提取行列，自动生成表头分隔符

- **`html_table_to_structured(html)`**：HTML `<table>` → `(headers, rows)` 结构化数据
  - 返回 `(list[str], list[list[str]])` 元组

- **`block_to_markdown(block)`**：MinerU content_list 单个块 → Markdown
  - 支持类型：`text`、`image`（含 caption）、`table`（HTML 或结构化）、`list`、`equation`、`code`、`chart`、`header`/`footer` 等
  - 图片渲染为 `![caption](img_path)` 格式
  - 表格自动调用 `html_table_to_markdown()` 转换

## 数据流

```
MinerU content_list blocks
        ↓
block_to_markdown(block)
  ├── text     → 直接输出
  ├── image    → ![caption](path)
  ├── table    → html_table_to_markdown() → Markdown 表格
  ├── list     → - item1\n- item2
  ├── equation → text
  ├── code     → ```lang\ncode\n```
  └── chart    → chart caption
        ↓
Markdown 字符串
```

## 使用

```python
from src.core.ingest_and_digitize_data.parse_document.common import (
    html_table_to_markdown, html_table_to_structured, block_to_markdown, TableParser
)

# HTML 表格 → Markdown
md = html_table_to_markdown("<table><tr><td>A</td><td>B</td></tr></table>")

# HTML 表格 → 结构化数据
headers, rows = html_table_to_structured(html_content)

# MinerU block → Markdown
markdown = block_to_markdown({"type": "text", "text": "Hello world"})
```
