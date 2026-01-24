# Markdown to HTML Output Migration

## 概述
将项目的输出格式从Markdown（`.md`文件）改为HTML格式。删除了所有与Markdown文件生成相关的代码，现在只输出HTML报告。

## 修改范围

### 1. 数据模型层 (src/application/dto.py)
**变更内容：**
- 移除 `output_markdown` 字段（原来存储翻译后的Markdown路径）
- 移除 `highlight_markdown` 字段（原来存储高亮后的Markdown路径）
- 添加 `output_html` 字段（存储HTML报告路径）

**影响：** ProcessPDFResponse 响应对象的结构已更新

### 2. 管道步骤修改

#### 2.1 PDF处理步骤 (src/application/services/pdf_processing_step.py)
**变更内容：**
- 移除 `translated_doc_path` 上下文变量（不再生成中间Markdown文件）
- 更新docstring，删除关于"保存翻译文档"的说明

**原来的流程：**
```
提取PDF → 保存为_en.md → 检测语言
```

**新的流程：**
```
提取PDF → 检测语言（不保存中间文件）
```

#### 2.2 翻译步骤 (src/application/services/translation_step.py)
**变更内容：**
- 移除保存翻译内容到文件的代码
- 删除 `translated_doc_path` 参数的使用
- 简化rollback逻辑（无需清理Markdown文件）
- 更新docstring

**代码简化：**
```python
# 移除前
if translated_doc_path:
    Path(translated_doc_path).write_text(...)
    
# 移除后
# 直接将内容存在context中，不持久化
```

#### 2.3 高亮步骤 (src/application/services/highlighting_step.py)
**变更内容：**
- 完全移除生成和保存高亮Markdown文件的代码
- 不再创建 `_en_highlight.md` 文件
- 简化rollback逻辑
- 删除 `highlighted_doc_path` 上下文变量

**代码移除：**
```python
# 移除前
highlight_path = str(translated_doc_path).replace("_en.md", "_en_highlight.md")
Path(highlight_path).write_text(...)
highlighted_doc_path = highlight_path

# 移除后
# 仅在context中保持highlighted_markdown，不保存文件
```

#### 2.4 报告生成步骤 (src/application/services/report_generation_step.py)
**变更内容：**
- 更新最终JSON payload，使用 `html_report_path` 替代 `highlight_path` 和 `translated_doc`
- 移除从上下文获取已弃用的Markdown路径变量
- 简化payload结构

**变更详情：**
```python
# 移除前的payload包含
"highlight_path": highlighted_doc_path,
"translated_doc": translated_doc_path,

# 改为
"html_report_path": html_report_path,
```

### 3. 管道配置修改

#### 3.1 结果累加器 (src/application/services/result_accumulator.py)
**变更内容：**
- 移除 `output_markdown` 提取逻辑
- 移除 `highlight_markdown` 提取逻辑
- 添加 `output_html` 字段
- 简化highlighting步骤的结果提取

**转换逻辑更新：**
```python
# 移除前
"output_markdown": pdf_data.get("translated_doc_path"),
"highlight_markdown": highlight_data.get("highlighted_doc_path"),

# 改为
"output_html": report_data.get("html_report_path"),
```

#### 3.2 管道编排器 (src/application/services/refactored_pipeline_orchestrator.py)
**变更内容：**
- 更新步骤输出关键字配置
- 移除 `translated_doc_path` 和 `highlighted_doc_path`
- 移除highlight步骤的 `highlighted_doc_path` 输出
- 更新 `_build_response()` 方法使用 `output_html` 替代Markdown字段

**变更内容：**
```python
# pdf_processing步骤输出中移除
"translated_doc_path",

# highlighting步骤输出中移除
"highlighted_doc_path",

# 响应构建中
output_html=self.context.get("html_report_path", ""),  # 替代output_markdown
```

### 4. 实体模型修改

#### 4.1 管道状态 (src/domain/entities/pipeline_state.py)
**变更内容：**
- 移除 `translated_doc_path` 属性
- 移除 `highlighted_doc_path` 属性
- `to_dict()` 方法中同步更新

**属性变更：**
```python
# 移除
self.translated_doc_path: Optional[str] = None
self.highlighted_doc_path: Optional[str] = None

# to_dict()中也相应移除这两个字段
```

### 5. 工具函数修改

#### 5.1 管道工具 (src/infrastructure/utils/pipeline_utils.py)
**变更内容：**
- 更新 `build_output_paths_payload()` 方法
- 改为返回 `output_html` 而非 `output_markdown` 和 `highlight_markdown`
- 简化返回字典结构

**方法变更：**
```python
# 移除前
"output_markdown": context_dict.get("translated_doc_path"),
"highlight_markdown": context_dict.get("highlighted_doc_path"),

# 改为
"output_html": context_dict.get("html_report_path"),
```

### 6. 主入口修改

#### 6.1 应用入口 (src/app.py)
**变更内容：**
- 更新输出信息显示
- 移除Markdown输出文件的打印
- 添加或强化HTML报告路径的显示

**输出变更：**
```python
# 移除前
print(f"  - Markdown: {result['output_markdown']}")
print(f"  - Highlight: {result['highlight_markdown']}")

# 改为
if result.get('output_html'):
    print(f"  - 📄 HTML Report: {result['output_html']}")
elif result.get('html_report_path'):
    print(f"  - 📊 HTML Report: {result['html_report_path']}")
```

### 7. 测试文件更新

#### 7.1 性能监控测试 (test_performance_monitoring.py)
**变更内容：**
- 更新结果显示逻辑
- 改为显示HTML输出路径

**变更内容：**
```python
# 移除前
print(f"✓ 输出Markdown: {result['output_markdown']}")
print(f"✓ 输出高亮: {result['highlight_markdown']}")

# 改为
print(f"✓ 输出HTML: {result.get('output_html') or result.get('html_report_path')}")
```

## 输出流程对比

### 迁移前
```
PDF输入
  ↓
文本提取 + 语言检测
  ↓
翻译 → 保存为 _en.md
  ↓
高亮 → 保存为 _en_highlight.md
  ↓
证据提取
  ↓
HTML生成
  ↓
输出：多个.md文件 + HTML报告
```

### 迁移后
```
PDF输入
  ↓
文本提取 + 语言检测
  ↓
翻译（仅在内存中）
  ↓
高亮（仅在内存中）
  ↓
证据提取
  ↓
HTML生成 → 保存为 _report.html
  ↓
输出：仅HTML报告 + JSON元数据
```

## 优势

1. **减少中间文件** - 不再生成临时的Markdown文件
2. **简化流程** - 代码逻辑更直接，无需文件I/O
3. **统一输出** - 所有用户都获得HTML格式的报告
4. **性能提升** - 减少磁盘I/O操作
5. **清晰的API** - 响应对象中不再有冗余字段

## 向后兼容性

- 新的 `output_html` 字段替代了 `output_markdown` 和 `highlight_markdown`
- 现有代码需要更新以使用 `output_html` 而非旧字段
- HTML报告包含了所有翻译和高亮信息

## 测试建议

1. 验证PDF处理不再生成 `_en.md` 文件
2. 验证不生成 `_en_highlight.md` 文件
3. 验证HTML报告正确生成
4. 验证ProcessPDFResponse中包含 `output_html` 字段
5. 验证管道性能（应该有所改进）

## 文件列表

修改的文件（共16个）：
1. src/application/dto.py
2. src/application/services/pdf_processing_step.py
3. src/application/services/translation_step.py
4. src/application/services/highlighting_step.py
5. src/application/services/report_generation_step.py
6. src/application/services/result_accumulator.py
7. src/application/services/refactored_pipeline_orchestrator.py
8. src/domain/entities/pipeline_state.py
9. src/infrastructure/utils/pipeline_utils.py
10. src/app.py
11. test_performance_monitoring.py

## 注意事项

- 保留的Markdown库导入仅用于HTML生成（bilingual_html_generator.py中）
- HTML生成器继续使用markdown库将内容转换为HTML
- 所有的翻译和高亮逻辑仍然保留，只是不再保存为Markdown文件
