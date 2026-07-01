# Prompts 翻译提示模板

> 翻译管线各阶段的 LLM 提示模板

## 概述

`prompts` 模块集中管理翻译管线的所有 LLM 提示模板，涵盖术语提取、文档格式化、翻译和自审四个阶段。所有函数返回可直接用于 LLM 调用的提示字符串。

## 结构

```
prompts/
├── __init__.py        # 导出所有提示函数
├── terminology.py     # 术语提取与 system prompt 生成
├── format.py          # 文档格式化与缺失值标记
└── translate.py       # 翻译与自审
```

## 核心组件

### 术语提取 (`terminology.py`)

| 函数 | 说明 |
|------|------|
| `get_terminology_prompt(markdown_content)` | 生成术语提取提示，要求 LLM 提取双语术语对和保留规则（HGVS、基因符号、蛋白名、DOI/PMID） |
| `get_system_prompt_generation_prompt(markdown_sample, source_language)` | 元提示：让 LLM 根据文档样本自动生成最优翻译 system prompt。包含严格的翻译约束（直译、不推断缺失值、保留 `[REDACTED]` 标记、variant/mutation 区分） |

### 格式化 (`format.py`)

| 函数 | 说明 |
|------|------|
| `get_prescan_prompt(source_text)` | 预扫描提示：让 LLM 识别并标记所有缺失/空白/脱敏值（年龄、日期、数量、剂量等），插入 `[REDACTED]` |
| `get_format_prompt(markdown_content)` | 3 任务格式化提示：(1) 结构规范化 (2) 标记缺失值 `[REDACTED]` (3) 修复 OCR 截断（如"长 间期"→"长 R-R 间期"） |

### 翻译 (`translate.py`)

| 函数 | 说明 |
|------|------|
| `get_translate_prompt(markdown_segment, terminology, prev_context, next_context)` | 分段翻译提示，包含前后上下文窗口、术语表、翻译指令。支持 `«BLK»` 段落分隔符保留 |
| `get_full_document_translate_prompt(marked_source, terminology, strict=False)` | 全段翻译提示，一次性翻译整个文档。`strict=True` 时添加更严格的翻译约束 |
| `get_self_review_prompt(source_text, translated_text)` | 自审提示：对比源文本和翻译，修正错误、遗漏和术语不一致 |

### 关键翻译约束

所有翻译提示均包含以下核心约束：
- **直译** — 不升级或降级证据强度（"提示"→"suggestive of"，非"confirming"）
- **不推断** — 保留所有 `[REDACTED]` 标记，不补充缺失值
- **保留结构** — Markdown 格式、图像引用、`«BLK»` 分隔符原样保留
- **生物医学标识符** — HGVS、基因符号、蛋白名、DOI/PMID 不翻译
- **variant vs mutation** — 默认用 "variant" 翻译"变异"，仅当原文明确写"突变"时用 "mutation"

## 使用

```python
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.prompts import (
    get_terminology_prompt,
    get_translate_prompt,
    get_self_review_prompt,
    get_system_prompt_generation_prompt,
)

# 术语提取
term_prompt = get_terminology_prompt(markdown_text)

# 分段翻译
translate_prompt = get_translate_prompt(
    segment_text, terminology=term_map_str,
    prev_context=prev, next_context=next
)

# 自审
review_prompt = get_self_review_prompt(source_text, translated_text)
```
