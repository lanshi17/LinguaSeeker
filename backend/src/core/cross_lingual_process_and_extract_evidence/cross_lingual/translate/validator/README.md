# Validator 翻译质量验证

> 翻译输出的质量验证、LLM 产物清理和文本规范化

## 概述

`validator` 模块负责验证翻译输出质量、清理 LLM 生成的伪影/污染、规范化 OCR 文本。是翻译管线的质量保障层，确保下游证据提取接收到高质量的英文文本。

## 结构

```
validator/
├── __init__.py        # 导出所有验证函数
├── core.py            # 翻译质量验证（完整性、语言、图像引用）
├── artifacts.py       # LLM 产物清理（源语言残留、提示回显）
├── normalize.py       # 文本规范化（CJK 标点、OCR 修复、REDACTED 修正）
└── redacted.py        # 缺失值标记（空括号、CJK 间隙检测）
```

## 核心组件

### 质量验证 (`core.py`)

翻译输出的核心质量检查：

| 函数 | 说明 |
|------|------|
| `validate_translation_output(source, translated)` | 端到端验证：长度比率检查（文档级/段落级）、非英文输出检测 |
| `validate_segment(source, translated)` | 单段验证：检查翻译是否为空、是否与原文相同、长度是否合理 |
| `validate_image_references_preserved(source, translated)` | 确保源文本中所有 `![...](...)` 图像引用在翻译中保留 |
| `summarize_validation_error(exc)` | 从验证异常提取简洁摘要 |
| `_source_requires_completeness_check(source, min_chars)` | 判断源文本是否需要完整性检查（长度 + 非英文 + CJK 比率阈值） |

关键阈值：
- 文档级：源文本 ≥ 500 字符，翻译/源比率 ≥ 0.35
- 段落级：源文本 ≥ 220 字符，翻译/源比率 ≥ 0.30

### 产物清理 (`artifacts.py`)

清理 LLM 翻译输出中的伪影：

| 函数 | 说明 |
|------|------|
| `strip_source_contamination(translated, source_language)` | 移除 LLM 输出中的源语言残留文本（基于 CJK/西里尔/平假名/片假名/韩文检测） |
| `strip_prompt_artifacts(text)` | 移除 LLM 回显的提示指令文本 |
| `strip_inline_artifacts(text)` | 移除行内提示注入标记和块分隔符 |
| `strip_prompt_echo(text)` | 通过查找最后一个提示标记定位翻译输出起始位置 |
| `_is_terminology_echo(text)` | 检测 LLM 是否回显了术语表而未执行翻译 |

### 文本规范化 (`normalize.py`)

修复 OCR 和翻译过程中的文本问题：

| 函数 | 说明 |
|------|------|
| `normalize_cjk_punctuation(text)` | CJK 标点转 ASCII 等价符（如 `，`→`,`、`。`→`.`） |
| `normalize_placeholders(text)` | 规范化 OCR/解析占位符伪影 |
| `fix_email_placeholder(text)` | 修复 OCR 缺失邮箱地址导致的冗余冒号 |
| `fix_ocr_truncations(text)` | 修复生物医学文档中常见的 OCR 截断（如 `α-galactosidase A ( , )`） |
| `fix_word_boundary_redacted(text)` | 移除错误插入到英文单词内部的 `[REDACTED]`（如 `Re[REDACTED]ferences`→`References`） |
| `normalize_keywords_capitalization(text)` | 关键词列表首字母大小写规范化为 sentence case |

### 缺失值标记 (`redacted.py`)

在 OCR 处理的文档中标记缺失值：

| 函数 | 说明 |
|------|------|
| `mark_redacted_values(text)` | 两阶段标记：(1) 结构伪影（空括号 `（ ）`→`（[REDACTED]）`） (2) CJK 间隙安全网（检测 CJK 字符间的空白并插入 `[REDACTED]`） |

设计为 LLM 格式化阶段（`get_format_prompt`）的正则安全网，处理 LLM 可能遗漏的模式。

## 数据流

```
LLM 翻译输出
    │
    ▼
strip_source_contamination()   ── 移除源语言残留
strip_prompt_echo()            ── 移除提示回显
strip_inline_artifacts()       ── 移除行内伪影
    │
    ▼
normalize_cjk_punctuation()    ── CJK 标点规范化
normalize_placeholders()       ── 占位符规范化
fix_email_placeholder()        ── 邮箱修复
fix_ocr_truncations()          ── OCR 截断修复
fix_word_boundary_redacted()   ── REDACTED 边界修正
    │
    ▼
validate_translation_output()  ── 翻译质量验证
validate_segment()             ── 段落级验证
validate_image_references_preserved()  ── 图像引用检查
    │
    ▼
标记缺失值
mark_redacted_values()         ── 空括号 + CJK 间隙
    │
    ▼
规范化、验证后的英文文本
```

## 使用

```python
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.validator import (
    strip_source_contamination,
    strip_prompt_artifacts,
    normalize_cjk_punctuation,
    validate_translation_output,
    mark_redacted_values,
)

# 清理 LLM 输出
cleaned = strip_source_contamination(translated_text, source_language="zh")
cleaned = strip_prompt_artifacts(cleaned)

# 规范化
cleaned = normalize_cjk_punctuation(cleaned)

# 验证
validate_translation_output(source_text, cleaned)

# 标记缺失值
marked = mark_redacted_values(cleaned)
```
