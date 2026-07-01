# Cross-Lingual 跨语言处理子系统

> 文档格式化、语言检测和多阶段 LLM 翻译的完整管线

## 概述

`cross_lingual` 子系统负责将多语言生物医学文档转换为标准化英文文本。包含两个核心子模块：

- **`format/`** — 源文档格式化、OCR 修复、Markdown 规范化、缺失值标记
- **`translate/`** — 语言检测、多阶段 LLM 翻译、翻译质量验证、后处理

## 结构

```
cross_lingual/
├── __init__.py          # 空模块入口
├── format/              # 文档格式化子模块
│   ├── base.py          # BaseFormatter 抽象接口
│   ├── formatter.py     # MarkdownFormatter 实现
│   └── segmenter.py     # Token 预算文本分段
└── translate/           # 翻译子模块
    ├── __init__.py      # 导出核心翻译类型
    ├── base.py          # BaseTranslator 抽象接口
    ├── translator.py    # MultiStageTranslator 实现
    ├── postprocess.py   # 翻译后处理
    ├── blocks.py        # 块级标记/合并/拆分操作
    ├── language_detector.py  # 语言检测与跳过逻辑
    ├── providers.py     # LLM 客户端工厂与重试
    ├── exceptions.py    # TranslationError 异常
    ├── prompts/         # LLM 提示模板
    └── validator/       # 翻译质量验证
```

## 核心组件

### 格式化管线 (`format/`)

`MarkdownFormatter` 实现 `BaseFormatter` 接口：
- 从 MinerU `content_list.json` 构建结构化 `FormattedDocument`
- OCR 文本修复、whitespace 规范化、Markdown 标题修正
- 句子级位置追踪（`SentenceRegion`）和字符漂移计算（`SentenceDrift`）
- HTML 检测与处理
- `segmenter.py` 提供 token 预算分段（`segment_text`），支持 CJK 混合内容

### 翻译管线 (`translate/`)

`MultiStageTranslator` 实现 `BaseTranslator` 接口，执行 3 阶段管线：

1. **术语提取** — 从源文档提取双语术语表，保留 HGVS、基因符号等生物医学标识符
2. **多阶段翻译** — 支持全段翻译和分段翻译两种模式，含上下文窗口管理
3. **验证** — 翻译完整性检查、语言验证、图像引用保留验证

关键模块：
- **`language_detector.py`** — 基于 lingua 库的语言检测，CJK 比率启发式，英文回退逻辑
- **`blocks.py`** — `[BLOCK_N]` 标记系统，短关键词合并/拆分，原文覆盖检测
- **`postprocess.py`** — 重复内容修剪、块级翻译映射、双语去重、质量标记、翻译漂移计算
- **`providers.py`** — LLM 客户端工厂（`create_llm`/`create_json_llm`），全局并发信号量（5），指数退避重试

### 翻译验证 (`validator/`)

- **`core.py`** — 翻译完整性验证（文档级/段落级）、非英文输出检测、图像引用保留检查
- **`artifacts.py`** — LLM 输出污染清理：源语言残留、提示回显、术语回显检测
- **`normalize.py`** — CJK 标点规范化、OCR 伪影修复、`[REDACTED]` 边界修正、关键词首字母规范化
- **`redacted.py`** — 缺失值标记（空括号、CJK 间隙检测），作为 LLM 格式化阶段的安全网

## 数据流

```
原始页面 (pages) + 内容块 (content_blocks)
    │
    ▼
MarkdownFormatter.format()
    │  → FormattedDocument (markdown + 句子区域 + 布局漂移)
    ▼
detect_language(text)
    │  → ISO 639-1 语言代码
    │
    ├── 已是英文 → 跳过翻译
    │
    ▼
MultiStageTranslator.translate_to_result()
    │  1. 术语提取 → terminology_map
    │  2. 分段/全段翻译 → translated_text
    │  3. 验证 → 确保质量
    │  → TranslationResult
    ▼
后处理 (postprocess)
    │  → 翻译块映射、去重、漂移计算
    ▼
TranslationResult (含术语表、段落、对齐信息、翻译块)
```

## 使用

```python
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import MarkdownFormatter
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import MultiStageTranslator

# 格式化
formatter = MarkdownFormatter()
formatted = formatter.format(pages, content_blocks=blocks)

# 翻译
translator = MultiStageTranslator(ctx=translation_ctx)
result = await translator.translate_to_result(formatted)
```
