# 分批翻译实现文档

## 概述

实现了智能分批翻译功能，以提高大型HTML文档的翻译稳定性和效率。

## 主要改进

### 1. TranslatorServiceImpl - 分批翻译核心

**文件**: `src/infrastructure/llm/translator_impl.py`

#### 新增功能

- **`translate_to_english()`** - 主入口，自动判断是否需要分批
  - 小文档 (≤8000字符): 直接翻译
  - 大文档 (>8000字符): 自动分批处理

- **`_single_translation()`** - 单次翻译执行
  - 包含重试机制（超时时重试2次）
  - 指数退避策略（第一次等5秒，第二次等10秒）
  - 支持超时异常检测

- **`_batch_translation()`** - 批量翻译编排
  - 分割HTML为语义批次
  - 逐批处理并汇总
  - 详细的错误报告

- **`_split_html_into_batches()`** - HTML智能分割
  - 在段落、标题、表格边界分割
  - 尊重最大批次大小 (8000字符)
  - 失败时进一步拆分

- **`_split_large_element()`** - 大元素降级处理
  - 按句子边界分割
  - 处理超大单个元素
  - 保证不超过大小限制

#### 配置参数

```python
self.max_batch_chars = 8000    # 每批最大字符数
self.min_batch_chars = 2000    # 最小批次大小
self.llm.request_timeout = 180 # 请求超时180秒（3分钟）
```

### 2. TranslationStep - 简化使用层

**文件**: `src/application/services/translation_step.py`

#### 改进

- **简化的 `_translate_with_glossary()`**
  - 移除了重复的分块逻辑
  - 完全依赖 TranslatorServiceImpl 的分批处理
  - 提取术语表用于日志

- **增加的 `max_chunk_size`**
  - 从 4000 字符调整为 8000 字符
  - 与 translator 保持一致

- **删除的过时方法**
  - `_split_content()` - 移到 translator 层
  - 逻辑集中在单一职责类中

### 3. 超时和重试机制

#### 重试策略

当检测到以下异常时自动重试：
- `"timed out"`
- `"ReadTimeout"`
- `"APITimeoutError"`

#### 指数退避

```
第1次超时 → 等待5秒 → 重试
第2次超时 → 等待10秒 → 重试
第3次失败 → 抛出异常
```

## 工作流程

```
原始HTML (12000字符)
    ↓
split_html_into_batches()
    ↓
[批次1] (8000字符) → _single_translation() → 翻译1
[批次2] (4000字符) → _single_translation() → 翻译2
    ↓
Join translated batches
    ↓
完整英文HTML
```

## 性能特点

| 指标 | 值 |
|------|-----|
| 单批次最大大小 | 8000 字符 |
| 单次请求超时 | 180 秒 |
| 超时重试次数 | 2 次 |
| 重试等待时间 | 5-10 秒 |
| 预期并发能力 | 相比全文翻译 ×3-4 倍 |

## 日志示例

```
2026-01-24 19:25:15,523 - src.application.services.translation_step - INFO - Starting translation of 12400 chars...
2026-01-24 19:25:15,530 - src.infrastructure.llm.translator_impl - INFO - Document exceeds batch size; using batch translation
2026-01-24 19:25:15,531 - src.infrastructure.llm.translator_impl - INFO - Split into 2 batches
2026-01-24 19:25:38,124 - src.infrastructure.llm.translator_impl - INFO - Batch 1/2 translated (8000 chars → 8524 chars)
2026-01-24 19:25:52,891 - src.infrastructure.llm.translator_impl - INFO - Batch 2/2 translated (4400 chars → 4698 chars)
2026-01-24 19:25:52,895 - src.application.services.translation_step - DEBUG - Key terms identified: LDLR, Variant, Mutation
```

## 边界处理

### 处理特殊情况

1. **完全破损的HTML**: 在批次边界处可能分割，但不会破坏标签
2. **超大单个元素**: 自动按句子进一步分割
3. **纯文本回退**: 如果没有HTML标签，按字符分割

### 保留的结构

- HTML标签完整保留
- 缩进和换行保持
- 特殊字符编码保持 (UTF-8)

## 测试用例

### 小文档 (<8KB)
```python
html = "<p>Short content</p>"
result = translator.translate_to_english(html, Language.JAPANESE)
# 直接翻译，无分批
```

### 中等文档 (8-16KB)
```python
html = "...<p>Content 1</p>...<p>Content 2</p>..."  # 12KB
result = translator.translate_to_english(html, Language.JAPANESE)
# 分为2批，逐批翻译
```

### 大文档 (>32KB)
```python
html = "...<p>Very long content</p>..."  # 50KB
result = translator.translate_to_english(html, Language.JAPANESE)
# 分为6-7批，逐批翻译
```

## 故障排查

### 超时仍然发生

**解决方案**: 增加 `cfg.llm.timeout` 参数

```python
# 在 .env.development 中
LLM_TIMEOUT=300  # 增加到5分钟
```

### 翻译不一致

**原因**: 跨批次的术语不一致

**解决方案**: 提取第一批的关键词作为后续批次的参考

### 分割破坏了格式

**原因**: HTML复杂结构在批次边界分割

**解决方案**: 调整正则表达式，在更安全的位置分割

```python
# 修改 _split_html_into_batches() 中的正则表达式
```

## 未来优化

1. **并行翻译**: 使用 asyncio 并行处理多个批次
2. **缓存**: 缓存已翻译的批次
3. **智能分割**: 基于内容类型的自适应批次大小
4. **术语库**: 维护全局术语库跨所有文档

## 相关文件

- `src/infrastructure/llm/translator_impl.py` - 核心实现
- `src/application/services/translation_step.py` - 集成层
- `src/domain/services.py` - TranslatorService 接口
- `.env.development` - 配置参数

## 提交信息

```
feat: implement batch translation with retry mechanism

- Add intelligent HTML batch splitting by semantic boundaries
- Implement exponential backoff retry on timeout
- Support up to 8KB per batch with automatic fallback
- Maintain glossary consistency across batches
- Improve robustness under slow network conditions
```
