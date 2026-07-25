# Format 文档格式化模块

> 源文档格式化、OCR 修复、Markdown 规范化和 token 预算分段

## 概述

`format` 模块负责将 MinerU 解析输出转换为标准化 Markdown 文本，同时进行 OCR 修复、缺失值标记和字符级位置追踪。输出的 `FormattedDocument` 供下游翻译管线使用。

## 结构

```
format/
├── __init__.py      # 空模块入口
├── base.py          # BaseFormatter 抽象接口
├── formatter.py     # MarkdownFormatter 具体实现
└── segmenter.py     # Token 预算文本分段器
```

## 核心组件

### BaseFormatter (`base.py`)

抽象基类，定义格式化接口：

```python
class BaseFormatter(ABC):
    @abstractmethod
    def format(self, pages, content_blocks=None) -> FormattedDocument: ...
```

可替换实现，便于测试或替代格式化策略。

### MarkdownFormatter (`formatter.py`)

核心格式化实现：

- **页面偏移映射** (`build_page_offset_map`) — 从页面数据构建字符偏移到页码的映射
- **句子提取** (`extract_sentences`) — 按中英文句号分割文本，追踪每个句子的起止偏移
- **Markdown 格式化** (`_format_markdown`) — 空白规范化、标题间距修复、`[REDACTED]` 标记注入
- **字符漂移计算** (`compute_format_drift`) — 比较原始文本与格式化文本中句子位置的漂移
- **HTML 检测** (`_is_html`) — 识别 HTML 文档并适配处理
- **内容块模式** — 当提供 `content_blocks` 时，从结构化 JSON 构建 `FormattedDocument`，包含 `PageSpan` 和 `ContentBlock`

### Token 分段器 (`segmenter.py`)

将文本分段以适应 LLM 上下文窗口：

- **`estimate_tokens(text)`** — 粗略 token 估算：ASCII 字符 / 4，CJK 字符各算 1
- **`segment_text(text, max_tokens, prompt_overhead_tokens)`** — 按段落边界分段，支持 CJK 混合内容的自适应字符/token 比率
- **`_split_paragraph`** — 在 token 预算内拆分单个段落，优先按句子边界切割

## 数据流

```
MinerU pages + content_list.json
    │
    ▼
MarkdownFormatter.format()
    │
    ├── 从 content_blocks 构建结构化文本 + PageSpan
    │   或从 pages 直接提取 markdown
    │
    ├── extract_sentences() → 句子级位置追踪
    ├── _normalize_whitespace() → 空白规范化
    ├── _fix_markdown_headings() → 标题修复
    ├── mark_redacted_values() → 缺失值标记
    │
    ▼
FormattedDocument
    ├── formatted_markdown: str       # 格式化后的 Markdown
    ├── original_text: str            # 原始文本
    ├── sentences: List[SentenceRegion]  # 句子位置
    ├── layout_report: OriginalLayoutReport  # 布局漂移报告
    ├── content_blocks: List[ContentBlock]   # 结构化内容块
    └── page_spans: List[PageSpan]           # 页面跨度
```

## 使用

```python
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import MarkdownFormatter
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.segmenter import segment_text

# 格式化文档
formatter = MarkdownFormatter()
formatted = formatter.format(pages, content_blocks=blocks)

# 分段用于 LLM 输入
chunks = segment_text(formatted.formatted_markdown, max_tokens=8192)
```
