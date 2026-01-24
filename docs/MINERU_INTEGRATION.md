# MinerU OCR 集成指南

## 概述

本项目已升级为使用 **MinerU API** 进行 PDF 到 HTML 的转换，替代了之前的 Qwen OCR + HTML 生成方案。MinerU 提供更高质量的文档解析和结构化 HTML 输出。

## 主要特性

### ✨ 核心功能
- **PDF → HTML 直接转换**：MinerU API 直接生成结构化 HTML
- **高质量文本提取**：保持原始格式、排版和结构
- **支持复杂文档**：表格、图像、多列等
- **异步处理**：提交任务后轮询获取结果
- **错误处理**：完整的异常和超时管理

### 📦 服务架构

```
┌─────────────────────────────────────────┐
│      Application Layer                   │
│   ├─ PDFProcessingStep                   │
│   ├─ HTMLProcessingStep                  │
│   └─ PipelineContext                     │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│    Infrastructure Layer                  │
│   ├─ MinerUOCRService  (PDF→HTML)        │
│   ├─ MinerURemoteService (URL→HTML)      │
│   └─ PDFRepositoryImpl                    │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│       MinerU API                         │
│   https://mineru.net/api/v4/extract/task │
└──────────────────────────────────────────┘
```

## 安装和配置

### 1. 环境变量配置（.env.development）

```bash
# ==================== MinerU 配置 ====================
MINERU_MODE="api"
MINERU_API_URL="https://mineru.net/api/v4/extract/task"
MINERU_API_TOKEN="your_token_here"  # 从官网申请
MINERU_TIMEOUT="300"                # 任务超时时间（秒）
MINERU_MAX_FILE_SIZE_MB="100"      # 最大文件大小（MB）
```

### 2. 依赖包

MinerU 集成仅需要 `requests` 库（已在项目中）：

```bash
pip install requests
```

## 使用示例

### 基础用法：本地 PDF → HTML

```python
from src.infrastructure.utils.config import AppConfig
from src.infrastructure.ocr import MinerUOCRService

# 初始化配置和服务
config = AppConfig.from_env()
service = MinerUOCRService(config.llm)

# 转换 PDF
pdf_path = "document.pdf"
html_path = "output/document.html"

html_content = service.pdf_to_html(pdf_path, html_path)
```

### 远程 URL → HTML

```python
from src.infrastructure.ocr import MinerURemoteService

remote_service = MinerURemoteService(config.llm)

# 转换远程 PDF
pdf_url = "https://example.com/document.pdf"
html = remote_service.pdf_to_html_from_url(pdf_url, "output.html")
```

### 通过仓储层使用

```python
from src.infrastructure.repositories import PDFRepositoryImpl

# 使用 MinerU（默认）
pdf_repo = PDFRepositoryImpl(config.llm, use_mineru=True)

# 提取 HTML
html = pdf_repo.extract_html("document.pdf")

# 同时提取文本（从 HTML 或 PDF 本身）
text = pdf_repo.extract_text("document.pdf")
```

### 在管道中集成

```python
from src.application.services import (
    PDFProcessingStep,
    HTMLProcessingStep,
    PipelineContext
)

# 创建上下文
context = PipelineContext()
context.update({
    "pdf_path": "document.pdf",
    "out_dir": "/output",
    "use_mineru": True,  # 启用 MinerU
})

# 执行步骤
pdf_step = PDFProcessingStep(pdf_repo, lang_detector)
pdf_step.execute(context)

html_step = HTMLProcessingStep()
html_step.execute(context)

# 获取输出
html_path = context.get("processed_html_path")
html_content = context.get("processed_html_content")
```

## API 流程

### 1. 提交任务

```python
# 请求
POST https://mineru.net/api/v4/extract/task
Headers:
  Content-Type: application/json
  Authorization: Bearer {token}

Body:
{
  "url": "path/to/file.pdf",  # 本地路径或 URL
  "model_version": "vlm"       # 使用 VLM 模型
}

# 响应
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "task_12345...",
    ...
  }
}
```

### 2. 轮询任务状态

```python
# 请求
GET https://mineru.net/api/v4/extract/task/{task_id}
Headers:
  Authorization: Bearer {token}

# 响应（处理中）
{
  "code": 1,  # 1 表示处理中
  "message": "processing"
}

# 响应（完成）
{
  "code": 0,  # 0 表示成功
  "data": {
    "html_content": "<html>...</html>",
    ...
  }
}
```

## 类和方法参考

### MinerUOCRService

主要类用于本地 PDF 处理。

#### 初始化
```python
service = MinerUOCRService(config)
```

#### 方法

| 方法 | 说明 | 返回值 |
|-----|------|--------|
| `pdf_to_html(pdf_path, output_html_path?)` | 将 PDF 转换为 HTML | HTML 字符串或文件路径 |
| `pdf_to_markdown(pdf_path)` | 将 PDF 转换为 Markdown | Markdown 字符串 |

### MinerURemoteService

处理远程 URL 的 PDF 的子类。

#### 方法

| 方法 | 说明 |
|-----|------|
| `pdf_to_html_from_url(url, output_path?)` | 从 URL 转换 PDF |

### PDFRepositoryImpl

集成 MinerU 的仓储实现。

#### 初始化
```python
# 使用 MinerU
repo = PDFRepositoryImpl(config.llm, use_mineru=True)

# 使用 Qwen（后备）
repo = PDFRepositoryImpl(config.llm, use_mineru=False)
```

#### 新增方法

| 方法 | 说明 |
|-----|------|
| `extract_html(pdf_path)` | 提取 HTML 内容 |

### PDFProcessingStep

管道步骤，现已支持 HTML 输出。

#### 新增上下文键

| 键 | 说明 |
|----|------|
| `use_mineru` | 是否使用 MinerU（默认 True） |
| `html_output_path` | HTML 文件输出路径 |
| `html_content` | HTML 内容 |

### HTMLProcessingStep

新增管道步骤，用于后处理 HTML。

#### 功能
- 验证 HTML 结构
- 添加 CSS 样式
- 增强可读性

## 输出格式

### HTML 输出示例

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Document</title>
</head>
<body>
    <h1>文档标题</h1>
    <p>段落内容...</p>
    <table>
        <tr><th>列1</th><th>列2</th></tr>
        <tr><td>数据1</td><td>数据2</td></tr>
    </table>
</body>
</html>
```

### 文件结构

转换后的文件结构：

```
output/
├── document.pdf           # 原始文件
├── document.html          # MinerU 输出的 HTML
├── document_processed.html # 后处理后的 HTML
├── document_en.md         # 可选：英文翻译
└── document_bbox.json     # 可选：边界框元数据
```

## 错误处理

### 常见异常

```python
from src.infrastructure.utils.exceptions import ParsingException

try:
    html = service.pdf_to_html(pdf_path)
except ParsingException as e:
    print(f"PDF 处理失败: {e}")
    # 处理错误：
    # - 重试
    # - 使用备用方案（如 Qwen OCR）
    # - 记录日志
```

### 异常类型

| 异常 | 触发条件 |
|-----|--------|
| `ParsingException` | PDF 不存在、转换失败、超时 |
| `requests.RequestException` | API 请求失败 |
| `TimeoutError` | 任务超时 |

## 性能考虑

### 优化建议

1. **批量处理**：建议每次处理 1-10 个 PDF
2. **异步处理**：对多个 PDF 使用并发轮询
3. **缓存**：缓存已转换的 HTML
4. **超时设置**：根据网络和文件大小调整

### 典型处理时间

| 文件大小 | 预计时间 |
|--------|--------|
| < 1 MB | 10-30 秒 |
| 1-10 MB | 30-60 秒 |
| 10-50 MB | 60-120 秒 |
| > 50 MB | 可能需要调整超时 |

## 故障排除

### 问题：API Token 无效

**解决方案**：
1. 访问 MinerU 官网重新申请 Token
2. 检查 `.env` 文件配置
3. 确保 Token 未过期

### 问题：任务超时

**解决方案**：
1. 增加 `MINERU_TIMEOUT` 值
2. 检查网络连接
3. 减小 PDF 文件大小

### 问题：文件过大

**解决方案**：
1. 检查 `MINERU_MAX_FILE_SIZE_MB` 设置
2. 压缩 PDF 文件
3. 拆分大型 PDF

### 问题：HTML 为空

**解决方案**：
1. 验证 PDF 有效性
2. 尝试其他 PDF 文件
3. 检查日志获取详细错误信息

## 测试

### 运行集成测试

```bash
python -m pytest tests/test_mineru_integration.py -v
```

### 测试覆盖范围

- ✓ MinerU 服务初始化
- ✓ API 连接验证
- ✓ 配置加载
- ✓ 后备方案（Qwen）
- ✓ HTML 提取方法
- ✓ 管道上下文支持

## 与旧实现的兼容性

### 变化总结

| 功能 | 旧实现（Qwen） | 新实现（MinerU） |
|-----|----------------|-----------------|
| PDF → HTML | 多步骤（PDF→图像→OCR→HTML） | 直接 API 调用 |
| 质量 | 中等 | 高（VLM 模型） |
| 速度 | 快 | 中等（包括轮询） |
| 成本 | 按 token 计费 | 按任务计费 |
| 支持格式 | Markdown | HTML/Markdown |

### 后备方案

如果 MinerU 不可用，系统会自动回退到 Qwen OCR：

```python
# 自动后备（推荐）
repo = PDFRepositoryImpl(config.llm, use_mineru=True)

# 强制使用 Qwen
repo = PDFRepositoryImpl(config.llm, use_mineru=False)
```

## 相关文件

### 核心文件

- `src/infrastructure/ocr/mineru_ocr_service.py` - MinerU 服务实现
- `src/application/services/html_processing_step.py` - HTML 处理步骤
- `src/infrastructure/repositories/pdf_repository_impl.py` - 仓储实现

### 示例和测试

- `examples/mineru_ocr_example.py` - 使用示例
- `tests/test_mineru_integration.py` - 集成测试

## 参考资源

- [MinerU 官方网站](https://mineru.net)
- [API 文档](https://mineru.net/docs/api)
- [项目文档](./README.md)

## 常见问题 (FAQ)

**Q: MinerU 支持哪些文件格式？**
A: 主要支持 PDF。其他格式可根据官方文档查询。

**Q: HTML 输出可以直接用于渲染吗？**
A: 可以。MinerU 输出的 HTML 结构完整，可直接在浏览器中渲染。

**Q: 如何处理多国语言文档？**
A: MinerU 支持多语言识别。语言检测由 `LanguageDetectorService` 负责。

**Q: 可以并发处理多个 PDF 吗？**
A: 可以，但建议控制并发数量（3-5 个）以避免 API 限制。

**Q: HTML 可以转换为其他格式吗？**
A: 可以。可使用 `pypandoc` 或类似库将 HTML 转换为 Word、PDF 等。

---

**最后更新**: 2026年1月24日  
**版本**: 2.1.0
