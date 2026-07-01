# Translate 多阶段翻译引擎

> 语言检测、3 阶段 LLM 翻译管线、翻译质量验证与后处理

## 概述

`translate` 模块实现生物医学文档的端到端翻译管线。核心翻译器 `MultiStageTranslator` 执行术语提取 → 翻译 → 验证的 3 阶段流程，支持全段和分段两种翻译模式，并提供完善的翻译质量保障。

## 结构

```
translate/
├── __init__.py            # 导出核心翻译类型
├── base.py                # BaseTranslator 抽象接口
├── translator.py          # MultiStageTranslator 核心实现
├── postprocess.py         # 翻译后处理（映射、去重、漂移）
├── blocks.py              # 块级标记/合并/拆分操作
├── language_detector.py   # 语言检测与跳过逻辑
├── providers.py           # LLM 客户端工厂与重试
├── exceptions.py          # TranslationError
├── prompts/               # LLM 提示模板
└── validator/             # 翻译质量验证
```

## 核心组件

### BaseTranslator (`base.py`)

抽象接口，定义翻译管线契约：

```python
class BaseTranslator(ABC):
    async def run_pipeline(self, formatted) -> Tuple[dict, str, list, list, list]: ...
    async def translate_to_result(self, formatted) -> TranslationResult: ...
```

### MultiStageTranslator (`translator.py`)

核心翻译引擎，实现 3 阶段管线：

1. **术语提取阶段** — 从源文档提取双语术语表（HGVS、基因符号、蛋白名、DOI/PMID 保留规则）
2. **翻译阶段** — 两种模式：
   - **全段翻译** — 文档 ≤ 阈值时一次性翻译
   - **分段翻译** — 超长文档按 token 预算分段，带前后上下文窗口
3. **自审阶段** — 翻译后质量审查和修正

特性：
- 并发分段翻译（asyncio.Semaphore 控制并发度）
- 块标记系统（`[BLOCK_N]` / `«BLK»`）保持内容块结构
- 动态 system prompt 生成（根据文档样本自动优化翻译提示）
- CJK 比率检测决定跳过英文文档

### 语言检测 (`language_detector.py`)

- `detect_language(text)` — 基于 lingua 库的多语言检测，返回 ISO 639-1 代码
- `should_skip_translation(text)` — CJK 比率 > 5% 则需翻译；纯 ASCII + 常见英文词 ≥ 3 则跳过
- 内置 10 种语言映射（en/zh/ja/ko/fr/de/es/pt/ru/ar）

### 块操作 (`blocks.py`)

管理翻译过程中的内容块结构：

- `merge_short_keywords` — 合并相邻短关键词块（1-4 CJK 字符），减少 LLM 调用
- `split_merged_keywords` — 翻译后拆分合并的关键词
- `join_blocks_with_markers` — 用 `[BLOCK_N]` 标记连接文本块
- `split_by_markers` — 按标记拆分 LLM 输出
- `is_predominantly_english` — 检测文本是否以英文为主（跳过英文块）

### 后处理 (`postprocess.py`)

翻译输出的后处理管线：

- `build_translated_blocks` — 将翻译文本映射回原始块结构
- `deduplicate_bilingual_blocks` — 双语文档去重
- `flag_quality_issues` — 标记需人工审核的块
- `compute_translation_drift` — 计算源文本与翻译段落的字符漂移
- `check_block_coverage` — 拒绝仅覆盖摘要的不完整翻译
- `check_block_language` — 检查残留源语言文本
- `trim_repetitive_content` — 移除 LLM 输出中的重复标题块

### LLM 提供者 (`providers.py`)

- `create_llm` / `create_json_llm` — 创建 LLM 客户端适配器，支持密钥池轮换
- `invoke_with_retry` / `invoke_json_with_retry` — 指数退避重试（30s 基础，最多 3 次）
- 全局并发信号量（默认 5）防止上游限流
- 处理 transient 异常（httpx、openai、连接错误等）

## 数据流

```
FormattedDocument
    │
    ▼
术语提取 (get_terminology_prompt)
    │  → terminology_map: dict[str, str]
    ▼
语言检测 + 路由
    │
    ├── 已是英文 → 跳过
    │
    ▼
翻译阶段
    ├── 全段模式 → get_full_document_translate_prompt
    └── 分段模式 → segment_text + get_translate_prompt (每段)
    │  → translated_text
    ▼
自审 (get_self_review_prompt)
    │  → 修正后的翻译
    ▼
后处理
    ├── build_translated_blocks() → 块映射
    ├── deduplicate_bilingual_blocks() → 去重
    ├── check_block_language() → 语言检查
    ├── flag_quality_issues() → 质量标记
    │
    ▼
TranslationResult
```

## 使用

```python
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate import (
    MultiStageTranslator, detect_language, create_llm
)

# 语言检测
lang = detect_language(document_text)

# 创建翻译器并执行
translator = MultiStageTranslator(ctx=config_ctx)
result = await translator.translate_to_result(formatted_doc)
```
